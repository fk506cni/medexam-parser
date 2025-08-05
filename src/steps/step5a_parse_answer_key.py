from pathlib import Path
import json
import time
import re
import os
import google.generativeai as genai

# LLMクライアントのセットアップ
# Set up LLM client
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY environment variable not set.")
genai.configure(api_key=api_key)

def call_llm(prompt: str, model_name: str):
    """LLMを呼び出して結果を返す / Calls the LLM and returns the result."""
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"  [LLM Error] {e}")
        return None

def extract_json_from_llm_response(response_text: str):
    """LLMの応答からJSON部分を抽出する / Extracts the JSON part from the LLM's response."""
    # トリプルクォートを使い、複数行の正規表現を正しく扱う
    # Use triple quotes to correctly handle multi-line regular expressions
    match = re.search(r'''```json
(.*?)
```''', response_text, re.DOTALL)
    if match:
        return match.group(1)
    return response_text # JSONが直接返された場合 / If JSON is returned directly


def parse_answer_key(
    answer_key_extraction_path: Path, 
    intermediate_dir: Path, 
    model_name: str, 
    rate_limit_wait: float,
    max_retries: int = 3
):
    print(f"  [Step 5a] Parsing answer key from {answer_key_extraction_path.name} using {model_name}...")

    try:
        with open(answer_key_extraction_path, 'r', encoding='utf-8') as f:
            pages_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"  [Step 5a] Error reading or parsing file: {e}")
        return None

    # プロンプトを読み込む / Load the prompt
    prompt_template_path = Path(__file__).parent / "step5a_prompt.txt"
    with open(prompt_template_path, 'r', encoding='utf-8') as f:
        prompt_template = f.read()

    all_answers = {}
    for page in pages_data:
        page_text = page.get('text', '')
        if not page_text.strip():
            continue

        print(f"    - Processing page {page['page_number']}...")
        prompt = prompt_template.format(page_text=page_text)
        
        llm_response = None
        for attempt in range(max_retries):
            llm_response = call_llm(prompt, model_name)
            if llm_response is not None:
                break
            print(f"    - API call failed. Retrying ({attempt+1}/{max_retries})...")
            time.sleep(rate_limit_wait)

        if not llm_response:
            print(f"    - Failed to get response from LLM for page {page['page_number']} after {max_retries} retries.")
            continue

        json_str = extract_json_from_llm_response(llm_response)
        try:
            parsed_answers = json.loads(json_str)
            all_answers.update(parsed_answers)
        except json.JSONDecodeError:
            print(f"    - Failed to parse JSON from LLM response for page {page['page_number']}.")
            print(f"      LLM Response: {json_str}")

    if not all_answers:
        print("  [Step 5a] Could not parse any answers from the document.")
        return None

    # 出力パスは、入力ファイルと同じディレクトリに保存する / Output path is saved in the same directory as the input file.
    output_dir = answer_key_extraction_path.parent
    output_path = output_dir / "step5a_parsed_answer_key.json"

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_answers, f, ensure_ascii=False, indent=2)
    print(f"  [Step 5a] Completed. Output: {output_path}")
    return output_path
