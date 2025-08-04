# src/steps/step4_structure.py

import google.generativeai as genai
import os
import json
import re
from pathlib import Path
from dotenv import load_dotenv
import time
from typing import List, Dict, Optional, Any

# .envファイルから環境変数を読み込む
load_dotenv()

# --- LLMとプロンプトのパス設定 ---
API_KEY = os.getenv("GOOGLE_API_KEY")
PROMPT_FILE = Path(__file__).parent / "step4_prompt.txt"

def _load_prompt_template() -> str:
    """プロンプトファイルを読み込む"""
    try:
        with open(PROMPT_FILE, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: Prompt file not found at {PROMPT_FILE}")
        raise

PROMPT_TEMPLATE = _load_prompt_template()

def _call_gemini_api(batch_json_str: str, model_name: str) -> Optional[List[Dict]]:
    """LLMを呼び出し、パースされたJSONを返す"""
    try:
        model = genai.GenerativeModel(model_name)
        # .format() を使わず、単純な置換でプロンプトを組み立てる
        prompt = PROMPT_TEMPLATE.replace("{problem_batch_json}", batch_json_str)
        response = model.generate_content(prompt)
        
        match = re.search(r"```json\s*(\[.*\])\s*```|(\[.*\])", response.text, re.DOTALL)
        
        if not match:
            print(f"Warning: LLM did not return a valid JSON array. Response: {response.text[:200]}...")
            return None

        json_text = match.group(1) or match.group(2)
        if not json_text:
            print(f"Warning: Regex matched but no JSON content found. Response: {response.text[:200]}...")
            return None

        return json.loads(json_text)

    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from LLM response: {e}")
        print(f"Raw response text: {response.text[:500]}...")
        return None
    except Exception as e:
        print(f"An unexpected error occurred in _call_gemini_api: {e}")
        return None

def structure_problems(
    step3_output_path: Path, 
    intermediate_dir: Path, 
    model_name: str, 
    rate_limit_wait: float, 
    batch_size: int,
    max_batches: int,
    max_retries: int = 3
) -> Optional[Path]:
    """問題チャンクのテキストを構造化されたJSONに変換する"""
    if not API_KEY:
        print("Error: GOOGLE_API_KEY is not set. Skipping Step 4.")
        return None
    genai.configure(api_key=API_KEY)

    pdf_stem = step3_output_path.parent.name
    step_output_dir = intermediate_dir / pdf_stem
    step_output_dir.mkdir(parents=True, exist_ok=True)

    try:
        with open(step3_output_path, "r", encoding="utf-8") as f:
            problem_chunks = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading or parsing {step3_output_path}: {e}")
        return None

    if not problem_chunks:
        print(f"Warning: No problem chunks found in {step3_output_path.name}. Skipping Step 4.")
        # 空のファイルを作成して正常終了とする
        output_path = step_output_dir / "step4_structured_problems.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump([], f)
        return output_path

    all_structured_problems = []
    
    total_batches = -(-len(problem_chunks) // batch_size)
    batches_to_process = total_batches
    if max_batches > 0:
        batches_to_process = min(total_batches, max_batches)
        print(f"Info: Processing only the first {batches_to_process} of {total_batches} batches due to --max-batches limit.")

    # バッチ処理
    for i in range(0, len(problem_chunks), batch_size):
        current_batch_num = i // batch_size
        if max_batches > 0 and current_batch_num >= max_batches:
            break

        batch = problem_chunks[i:i + batch_size]
        print(f"  - Processing batch {current_batch_num + 1}/{batches_to_process} (problems {i+1}-{i+len(batch)})... ")

        batch_input = {
            "pdf_stem": pdf_stem,
            "problems": batch
        }
        batch_json_str = json.dumps(batch_input, ensure_ascii=False, indent=2)

        structured_batch = None
        for attempt in range(max_retries):
            structured_batch = _call_gemini_api(batch_json_str, model_name)
            if structured_batch is not None:
                break
            print(f"    ...API call failed. Retrying ({attempt+1}/{max_retries})...")
            time.sleep(rate_limit_wait)

        if structured_batch:
            all_structured_problems.extend(structured_batch)
            print(f"    ...Success, {len(structured_batch)} problems structured.")
        else:
            print(f"    ...Failed after {max_retries} retries. Skipping this batch.")

        # 次のAPI呼び出しの前に待機
        if (current_batch_num + 1) < batches_to_process:
            time.sleep(rate_limit_wait)

    output_path = step_output_dir / "step4_structured_problems.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_structured_problems, f, ensure_ascii=False, indent=2)

    print(f"Successfully structured {len(all_structured_problems)} problems and saved to {output_path}")
    return output_path
