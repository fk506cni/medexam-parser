
import argparse
import json
import os
import time
import datetime
from pathlib import Path
import google.generativeai as genai
from PIL import Image
import re

def get_exam_id_from_stem(pdf_stem: str) -> str:
    """ファイル名から共通の試験ID (例: tp240424-01) を抽出する"""
    # "tp240424-01a_01" -> "tp240424-01"
    match = re.match(r"(tp\d{6}-\d{2})", pdf_stem)
    if match:
        return match.group(1)
    return pdf_stem

# --- Constants ---
DEFAULT_RETRY = 3
DEFAULT_RATE_LIMIT_WAIT = 10.0  # seconds
DEFAULT_NUM_RUNS = 1
DEFAULT_OUTPUT_DIR = "output/step7_solved"
PROMPT_TEMPLATE_PATH = Path(__file__).parent / "step7_prompt.txt"

# --- LLM API Call ---
def call_llm_api(model, prompt, images, retry, rate_limit_wait):
    """Calls the LLM API with retry logic."""
    for i in range(retry):
        try:
            contents = [prompt] + images
            response = model.generate_content(contents)
            return response.text
        except Exception as e:
            print(f"API call failed (attempt {i+1}/{retry}): {e}")
            if i < retry - 1:
                time.sleep(rate_limit_wait)
    return None

def clean_question_for_prompt(question_data):
    """Removes answer key from question data to create a clean prompt."""
    if "answer" in question_data:
        del question_data["answer"]
    return question_data

def run(args):
    """Main function to solve problems using LLM."""
    # --- Initialization ---
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    model = genai.GenerativeModel(args.model_name)
    
    output_dir = Path(DEFAULT_OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    final_json_dir = Path("output/json")
    image_base_dir = Path("output/images")

    if not final_json_dir.exists():
        print(f"Error: Final JSON directory not found at '{final_json_dir}'")
        return

    # --- File Processing ---
    files_to_process = []
    if args.files:
        # main.pyの--files引数はPDFファイル名。そこからexam_idを抽出し、対応するJSONファイル名を作成する。
        exam_ids = {get_exam_id_from_stem(Path(f).stem) for f in args.files}
        files_to_process = [final_json_dir / f"{eid}.json" for eid in exam_ids]
    else:
        # 指定がない場合はoutput/json内のすべてのJSONを対象とする
        files_to_process = list(final_json_dir.glob("*.json"))

    # 存在しないファイルをリストから除去
    files_to_process = [f for f in files_to_process if f.exists()]

    if not files_to_process:
        print("No JSON files found to process.")
        return

    prompt_template = PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")

    # --- Main Loop ---
    for file_path in files_to_process:
        exam_id = file_path.stem
        output_file = output_dir / f"{exam_id}.jsonl"
        
        print(f"Processing file: {file_path.name}")
        
        with file_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        for question in data:
            question_id = question.get("id")
            print(f"  Solving question: {question_id}")

            # Prepare images if they exist
            images_to_send = []
            if "images" in question and question["images"]:
                for img_info in sorted(question["images"], key=lambda x: x.get("id")):
                    try:
                        image_path = image_base_dir / img_info["path"]
                        if image_path.exists():
                            images_to_send.append(Image.open(image_path))
                        else:
                            print(f"Warning: Image not found at {image_path}")
                    except Exception as e:
                        print(f"Warning: Could not load image {img_info.get('path')}: {e}")


            # Clean question and create prompt
            cleaned_question = clean_question_for_prompt(question.copy())
            prompt = prompt_template.format(question_json=json.dumps(cleaned_question, ensure_ascii=False, indent=2))

            for i in range(args.num_runs):
                print(f"    Run {i+1}/{args.num_runs}...")
                
                llm_response_text = call_llm_api(
                    model, 
                    prompt, 
                    images_to_send,
                    args.retry_step7, 
                    args.rate_limit_wait
                )

                # Parse LLM response
                llm_answer = None
                if llm_response_text:
                    try:
                        # Extract JSON part from the response
                        json_part = llm_response_text.strip().split('```json\n')[1].split('\n```')[0]
                        llm_answer = json.loads(json_part)
                    except (json.JSONDecodeError, IndexError) as e:
                        print(f"      Error parsing LLM response: {e}")
                        print(f"      Raw response: {llm_response_text}")
                        llm_answer = {"error": "Failed to parse JSON", "raw_response": llm_response_text}
                else:
                    llm_answer = {"error": "No response from LLM after retries."}

                # --- Save Result ---
                result_entry = {
                    "exam_id": exam_id,
                    "question_id": question_id,
                    "run_index": i + 1,
                    "timestamp": datetime.datetime.now().isoformat(),
                    "llm_response": llm_answer
                }

                with output_file.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(result_entry, ensure_ascii=False) + "\n")
                
                # Wait before the next API call (if it's not the last run)
                if i < args.num_runs - 1:
                    time.sleep(args.rate_limit_wait)

        print(f"Finished processing {file_path.name}. Results saved to {output_file}")
