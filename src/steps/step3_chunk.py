import google.generativeai as genai
import os
import json
import re
from pathlib import Path
from dotenv import load_dotenv
import time
from typing import List, Dict, Optional

# .envファイルから環境変数を読み込む
# Load environment variables from the .env file
load_dotenv()

# --- LLMとプロンプトのパス設定 / LLM and Prompt Path Settings ---
API_KEY = os.getenv("GOOGLE_API_KEY")
PROMPT_FILE = Path(__file__).parent / "step3_prompt.txt"

def _load_prompt_template() -> str:
    """プロンプトファイルを読み込む / Loads the prompt file."""
    try:
        with open(PROMPT_FILE, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: Prompt file not found at {PROMPT_FILE}")
        raise

PROMPT_TEMPLATE = _load_prompt_template()

def _create_text_chunks(text: str, chunk_size: int, overlap: int) -> List[str]:
    """テキストを指定されたサイズとオーバーラップで分割する / Splits text into chunks of specified size and overlap."""
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks

def _call_gemini_api(chunk_text: str, model_name: str, debug: bool = False) -> Optional[List[Dict]]:
    """LLMを呼び出し、パースされたJSONを返す / Calls the LLM and returns the parsed JSON."""
    try:
        model = genai.GenerativeModel(model_name)
        prompt = PROMPT_TEMPLATE.format(text_content=chunk_text)

        if debug:
            print("--- DEBUG: LLM Prompt for Step 3 ---")
            print(prompt)
            print("--------------------------------------")

        response = model.generate_content(prompt)
        raw_response_text = response.text

        if debug:
            print("--- DEBUG: LLM Raw Response from Step 3 ---")
            print(raw_response_text)
            print("-------------------------------------------")

        # ```json ... ``` で囲まれていても、いなくてもJSON配列を抽出する正規表現
        # Regex to extract JSON array, whether or not it's enclosed in ```json ... ```
        match = re.search(r"```json\s*(\[.*\])\s*```|(\[.*\])", raw_response_text, re.DOTALL)
        
        if not match:
            print(f"Warning: LLM did not return a parsable JSON array. Raw response: {raw_response_text[:300]}...")
            # パース失敗時はNoneを返してリトライさせる
            # Return None to trigger a retry on parsing failure
            return None

        # マッチした部分（キャプチャグループ1または2）からJSONテキストを取得
        # Get JSON text from the matched part (capture group 1 or 2)
        json_text = match.group(1) or match.group(2)

        if not json_text:
            print(f"Warning: Regex matched but no JSON content found in response: {response.text[:200]}...")
            # パース失敗時はNoneを返してリトライさせる
            # Return None to trigger a retry on parsing failure
            return None

        # JSONデコードを試行
        # Attempt to decode JSON
        return json.loads(json_text)

    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from LLM response: {e}")
        # 発生した例外が`response`にアクセスできるか確認
        # Check if the exception has access to `response`
        try:
            raw_text = raw_response_text
        except NameError:
            raw_text = "Raw response text is not available."
        print(f"Raw response text: {raw_text[:500]}...")
        # パース失敗時はNoneを返してリトライさせる
        # Return None to trigger a retry on parsing failure
        return None
    except Exception as e:
        print(f"An unexpected error occurred in _call_gemini_api: {e}")
        # APIエラー発生時はNoneを返して呼び出し元でリトライなどを判断させる
        return None

def chunk_text_by_problem(
    step2_output_path: Path, 
    intermediate_dir: Path, 
    rate_limit_wait: float, 
    model_name: str,
    max_retries: int = 3,
    debug: bool = False
) -> Optional[Path]:
    """
    LLMを使ってテキストを問題ごとにチャンク化し、JSONファイルとして保存する。
    Chunks text by problem using an LLM and saves it as a JSON file.
    """
    if not API_KEY:
        print("Error: GOOGLE_API_KEY is not set. Skipping Step 3.")
        return None
    genai.configure(api_key=API_KEY)

    pdf_stem = step2_output_path.parent.name
    step_output_dir = intermediate_dir / pdf_stem
    step_output_dir.mkdir(parents=True, exist_ok=True)

    try:
        with open(step2_output_path, "r", encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        print(f"Error: Input file not found at {step2_output_path}")
        return None

    all_problems = {}
    if text.strip():
        text_chunks = _create_text_chunks(text, chunk_size=15000, overlap=500)
        
        for i, chunk in enumerate(text_chunks):
            print(f"  - Processing chunk {i+1}/{len(text_chunks)}...")
            parsed_json = None
            for attempt in range(max_retries):
                parsed_json = _call_gemini_api(chunk, model_name, debug)
                if parsed_json is not None:
                    break
                print(f"  - API call failed. Retrying ({attempt+1}/{max_retries})...")
                time.sleep(rate_limit_wait)
            
            if parsed_json is None:
                print(f"  - Chunk {i+1} failed after {max_retries} retries. Skipping.")
                continue
            
            for problem in parsed_json:
                if isinstance(problem, dict) and "problem_number" in problem:
                    all_problems[problem["problem_number"]] = problem
                else:
                    print(f"Warning: Invalid item in LLM response: {problem}")
            
            # 次のAPI呼び出しの前に指定された時間だけ待機
            # Wait for the specified time before the next API call
            if i < len(text_chunks) - 1:
                time.sleep(rate_limit_wait)

    chunks = sorted(list(all_problems.values()), key=lambda p: p.get("problem_number", 0))

    output_path = step_output_dir / "step3_problem_chunks.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    print(f"Successfully chunked text using LLM and saved to {output_path} ({len(chunks)} chunks)")
    return output_path

if __name__ == '__main__':
    print("This script is a module and is meant to be imported.")
