import google.generativeai as genai
import os
import json
import re
from pathlib import Path
from dotenv import load_dotenv
import time
from typing import List, Dict, Optional

# .envファイルから環境変数を読み込む
load_dotenv()

# --- LLMとプロンプトのパス設定 ---
API_KEY = os.getenv("GOOGLE_API_KEY")
MODEL_NAME = "gemini-1.5-flash-latest"
PROMPT_FILE = Path(__file__).parent / "step3_prompt.txt"

def _load_prompt_template() -> str:
    """プロンプトファイルを読み込む"""
    try:
        with open(PROMPT_FILE, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: Prompt file not found at {PROMPT_FILE}")
        raise

PROMPT_TEMPLATE = _load_prompt_template()

def _create_text_chunks(text: str, chunk_size: int, overlap: int) -> List[str]:
    """テキストを指定されたサイズとオーバーラップで分割する"""
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks

def _call_gemini_api(chunk_text: str) -> Optional[List[Dict]]:
    """LLMを呼び出し、パースされたJSONを返す"""
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        prompt = PROMPT_TEMPLATE.format(text_content=chunk_text)
        response = model.generate_content(prompt)
        
        # ```json ... ``` で囲まれていても、いなくてもJSON配列を抽出する正規表現
        match = re.search(r"```json\s*(\[.*\])\s*```|(\[.*\])", response.text, re.DOTALL)
        
        if not match:
            print(f"Warning: LLM did not return a valid JSON array from response: {response.text[:200]}...")
            return []

        # マッチした部分（キャプチャグループ1または2）からJSONテキストを取得
        json_text = match.group(1) or match.group(2)

        if not json_text:
            print(f"Warning: Regex matched but no JSON content found in response: {response.text[:200]}...")
            return []

        return json.loads(json_text)

    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from LLM response: {e}")
        print(f"Raw response text: {response.text[:500]}...")
        return []
    except Exception as e:
        print(f"An unexpected error occurred in _call_gemini_api: {e}")
        time.sleep(5)
        return None

def chunk_text_by_problem(step2_output_path: Path, intermediate_dir: Path) -> Optional[Path]:
    """LLMを使ってテキストを問題ごとにチャンク化し、JSONファイルとして保存する"""
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

    if not text.strip():
        print(f"Warning: Input file {step2_output_path.name} is empty. Skipping.")
        chunks = []
    else:
        text_chunks = _create_text_chunks(text, chunk_size=15000, overlap=500)
        
        all_problems = {}
        for i, chunk in enumerate(text_chunks):
            print(f"  - Processing chunk {i+1}/{len(text_chunks)}...")
            parsed_json = _call_gemini_api(chunk)
            
            if parsed_json is None:
                print(f"  - Chunk {i+1} failed due to API error. Skipping.")
                continue
            
            for problem in parsed_json:
                if isinstance(problem, dict) and "problem_number" in problem:
                    all_problems[problem["problem_number"]] = problem
                else:
                    print(f"Warning: Invalid item in LLM response: {problem}")

        chunks = sorted(list(all_problems.values()), key=lambda p: p["problem_number"])

    output_path = step_output_dir / "step3_problem_chunks.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    print(f"Successfully chunked text using LLM and saved to {output_path} ({len(chunks)} chunks)")
    return output_path

if __name__ == '__main__':
    print("This script is a module and is meant to be imported.")