import argparse
import json
import os
import time
import datetime
from pathlib import Path
import google.generativeai as genai
from PIL import Image
import re
from typing import List, Dict, Any, Optional

# --- Constants ---
DEFAULT_RETRY = 3
DEFAULT_RATE_LIMIT_WAIT = 10.0  # seconds
DEFAULT_NUM_RUNS = 1
DEFAULT_OUTPUT_DIR = "output/step8_analysis"
ANALYSIS_PROMPT_PATH = Path(__file__).parent / "step8_prompt.txt"

def get_exam_id_from_stem(pdf_stem: str) -> str:
    """Extracts a common exam ID (e.g., tp240424-01) from a filename stem."""
    match = re.match(r"(tp\d{6}-\d{2})", pdf_stem)
    if match:
        return match.group(1)
    return pdf_stem

def call_and_parse_llm_api(model, prompt_parts: List[Any], retry: int, rate_limit_wait: float) -> Dict[str, Any]:
    """Calls the LLM API, parses the response as JSON, and retries on failure."""
    response_text = "No response"
    for i in range(retry):
        try:
            response = model.generate_content(prompt_parts)
            response_text = response.text
        except Exception as e:
            print(f"      API call failed (attempt {i+1}/{retry}): {e}")
            if i < retry - 1:
                time.sleep(rate_limit_wait)
            continue

        try:
            match = re.search(r"```json\s*([\s\S]*?)\s*```", response_text)
            if not match:
                raise json.JSONDecodeError("No JSON code block found", response_text, 0)
            
            json_text = match.group(1)
            parsed_json = json.loads(json_text)
            
            if not isinstance(parsed_json, dict):
                raise TypeError(f"Expected a JSON object (dict), but got {type(parsed_json)}")
                
            return parsed_json
        except (json.JSONDecodeError, IndexError, TypeError) as e:
            print(f"      Error parsing LLM response (attempt {i+1}/{retry}): {e}")
            print(f"      Raw response: {response_text}")
            if i < retry - 1:
                time.sleep(rate_limit_wait)

    return {"error": "Failed to get and parse LLM response after retries.", "raw_response": response_text}

def get_images(image_list: List[Dict[str, str]], image_base_dir: Path) -> List[Image.Image]:
    """Loads images from a list of image info dictionaries."""
    images_to_send = []
    if image_list:
        for img_info in sorted(image_list, key=lambda x: x.get("id")):
            try:
                image_path = image_base_dir / img_info["path"]
                if image_path.exists():
                    images_to_send.append(Image.open(image_path))
                else:
                    print(f"Warning: Image not found at {image_path}")
            except Exception as e:
                print(f"Warning: Could not load image {img_info.get('path')}: {e}")
    return images_to_send

def analyze_single_problem(model, problem_data: Dict[str, Any], prompt_template: str, image_base_dir: Path, args: argparse.Namespace):
    """Analyzes the difficulty and category of a single problem."""
    problem_core = problem_data.get("problem", {})
    if not problem_core:
        return None

    question_id = problem_core.get("id")
    print(f"  Analyzing single question: {question_id}")

    images_to_send = get_images(problem_core.get("images", []), image_base_dir)
    
    # Include the correct answer in the analysis
    prompt = prompt_template.format(question_json=json.dumps(problem_core, ensure_ascii=False, indent=2))

    if args.debug:
        print(f"--- LLM Prompt for {question_id} (Length: {len(prompt)} chars) ---")
        print(prompt)
        print("--- End of LLM Prompt ---")
        if images_to_send:
            print(f"--- Images to send: {len(images_to_send)} images ---")

    # step8用のリトライ回数を取得（main.pyから呼ばれた場合のために）
    retry_count = getattr(args, 'retry_step8', DEFAULT_RETRY)
    llm_analysis = call_and_parse_llm_api(
        model, [prompt] + images_to_send, retry_count, args.rate_limit_wait
    )

    return {
        "question_id": question_id,
        "analysis": llm_analysis
    }

def analyze_consecutive_problem(model, problem_data: Dict[str, Any], prompt_template: str, image_base_dir: Path, args: argparse.Namespace):
    """Analyzes the difficulty and category of consecutive problems."""
    case_presentation = problem_data.get("case_presentation", {})
    sub_questions = problem_data.get("sub_questions", [])
    if not case_presentation or not sub_questions:
        return []

    print(f"  Analyzing consecutive problem: {problem_data.get('id')}")

    # Extract the exam and part ID from the problem data
    source_pdf = problem_data.get("source_pdf", "")
    exam_id = get_exam_id_from_stem(source_pdf.replace(".pdf", ""))
    
    case_images = get_images(case_presentation.get("images", []), image_base_dir)
    
    case_text = case_presentation.get("text", "")
    case_images_prompt = "\n## 症例提示の画像\n" + "\n".join([f"- 画像 {img.get('id', '')}" for img in case_presentation.get("images", [])]) if case_images else ""

    results = []
    
    # Analyze each sub-question individually
    for sub_q in sub_questions:
        question_id = f"{exam_id}-{sub_q.get('problem_number')}"
        print(f"    Analyzing sub-question: {question_id}")
        
        sub_q_images = get_images(sub_q.get("images", []), image_base_dir)
        all_images = case_images + sub_q_images
        
        # Create individual analysis prompt for each sub-question
        sub_q_data = {
            "case_presentation": case_presentation,
            "sub_question": sub_q
        }
        
        prompt = prompt_template.format(question_json=json.dumps(sub_q_data, ensure_ascii=False, indent=2))

        if args.debug:
            print(f"--- LLM Prompt for {question_id} (Length: {len(prompt)} chars) ---")
            print(prompt)
            print("--- End of LLM Prompt ---")
            if all_images:
                print(f"--- Images to send: {len(all_images)} images ---")

        # step8用のリトライ回数を取得（main.pyから呼ばれた場合のために）
        retry_count = getattr(args, 'retry_step8', DEFAULT_RETRY)
        llm_analysis = call_and_parse_llm_api(
            model, [prompt] + all_images, retry_count, args.rate_limit_wait
        )
        
        results.append({
            "question_id": question_id,
            "analysis": llm_analysis
        })
        
        # Wait between sub-questions to respect rate limits
        if len(results) < len(sub_questions):
            time.sleep(args.rate_limit_wait)

    return results

def run(args):
    """Main function to analyze problems using LLM."""
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    model = genai.GenerativeModel(args.model_name)
    
    output_dir = Path(DEFAULT_OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    final_json_dir = Path("output/json")
    image_base_dir = Path("output")

    if not final_json_dir.exists():
        print(f"Error: Final JSON directory not found at '{final_json_dir}'")
        return

    files_to_process = [f for f in final_json_dir.glob("*.json") if f.exists()]
    if not files_to_process:
        print("No JSON files found to process.")
        return

    if not ANALYSIS_PROMPT_PATH.exists():
        print(f"Error: Analysis prompt file not found at '{ANALYSIS_PROMPT_PATH}'")
        return

    analysis_prompt_template = ANALYSIS_PROMPT_PATH.read_text(encoding="utf-8")

    # step8用のリトライ回数を取得（main.pyから呼ばれた場合のために）
    retry_count = getattr(args, 'retry_step8', DEFAULT_RETRY)

    for file_path in files_to_process:
        exam_id = file_path.stem
        output_file = output_dir / f"{exam_id}.jsonl"
        
        print(f"Processing file: {file_path.name}")
        
        with file_path.open("r", encoding="utf-8") as f:
            all_problem_data = json.load(f)

        for problem_data in all_problem_data:
            for i in range(args.num_runs):
                print(f"    Run {i+1}/{args.num_runs}...")
                
                results_to_save = []
                problem_format = problem_data.get("problem_format")

                if problem_format == 'single':
                    result = analyze_single_problem(model, problem_data, analysis_prompt_template, image_base_dir, args)
                    if result: results_to_save.append(result)
                
                elif problem_format == 'consecutive':
                    results = analyze_consecutive_problem(model, problem_data, analysis_prompt_template, image_base_dir, args)
                    results_to_save.extend(results)
                
                else:
                    print(f"  Warning: Unknown problem_format '{problem_format}' for problem ID {problem_data.get('id')}. Skipping.")
                    continue

                for res in results_to_save:
                    result_entry = {
                        "exam_id": exam_id,
                        "question_id": res["question_id"],
                        "run_index": i + 1,
                        "timestamp": datetime.datetime.now().isoformat(),
                        "analysis": res["analysis"]
                    }
                    with output_file.open("a", encoding="utf-8") as f:
                        f.write(json.dumps(result_entry, ensure_ascii=False) + "\n")
                
                if results_to_save and problem_format == 'single':
                    time.sleep(args.rate_limit_wait)

        print(f"Finished processing {file_path.name}. Results saved to {output_file}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Analyze difficulty and categorization of problems in JSON files using an LLM.")
    parser.add_argument("--model-name", type=str, default="gemini-1.5-pro-latest", help="LLM model name.")
    parser.add_argument("--rate-limit-wait", type=float, default=DEFAULT_RATE_LIMIT_WAIT, help="Wait time between API calls.")
    parser.add_argument("--retry-step8", type=int, default=DEFAULT_RETRY, help="Retries for Step 8.")
    parser.add_argument("--num-runs", type=int, default=DEFAULT_NUM_RUNS, help="Number of runs per question.")
    parser.add_argument("--debug", action="store_true", help="Enable debug messages.")
    parser.add_argument("--files", nargs='+', type=str, help=argparse.SUPPRESS)
    args = parser.parse_args()
    
    run(args)