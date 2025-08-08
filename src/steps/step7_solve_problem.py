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
DEFAULT_RATE_LIMIT_LIMIT_WAIT = 10.0  # seconds
DEFAULT_NUM_RUNS = 1
DEFAULT_OUTPUT_DIR = "output/step7_solved"
SINGLE_PROMPT_PATH = Path(__file__).parent / "step7_prompt.txt"
CONSECUTIVE_PROMPT_PATH = Path(__file__).parent / "step7_consecutive_prompt.txt"

def get_exam_id_from_stem(pdf_stem: str) -> str:
    """Extracts a common exam ID (e.g., tp240424-01) from a filename stem."""
    match = re.match(r"(tp\d{6}-\d{2})", pdf_stem)
    if match:
        return match.group(1)
    return pdf_stem

def call_and_parse_llm_api(model, prompt_parts: List[Any], retry: int, rate_limit_wait: float) -> Dict[str, Any]:
    """Calls the LLM API, parses the response as a JSON array, and retries on failure."""
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
            
            if not isinstance(parsed_json, list):
                raise TypeError(f"Expected a JSON array (list), but got {type(parsed_json)}")
                
            return parsed_json
        except (json.JSONDecodeError, IndexError, TypeError) as e:
            print(f"      Error parsing LLM response (attempt {i+1}/{retry}): {e}")
            print(f"      Raw response: {response_text}")
            if i < retry - 1:
                time.sleep(rate_limit_wait)

    return [{"error": "Failed to get and parse LLM response after retries.", "raw_response": response_text}]

def clean_question_for_prompt(question_data: Dict[str, Any]) -> Dict[str, Any]:
    """Removes the answer key from question data to create a clean prompt."""
    if "answer" in question_data:
        del question_data["answer"]
    if "sub_questions" in question_data:
        for sub_q in question_data["sub_questions"]:
            clean_question_for_prompt(sub_q)
    return question_data

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

def solve_single_problem(model, problem_data: Dict[str, Any], prompt_template: str, image_base_dir: Path, args: argparse.Namespace):
    """Handles the logic for solving a single problem."""
    problem_core = problem_data.get("problem", {})
    if not problem_core:
        return None

    question_id = problem_core.get("id")
    print(f"  Solving single question: {question_id}")

    images_to_send = get_images(problem_core.get("images", []), image_base_dir)
    
    cleaned_question = clean_question_for_prompt(problem_core.copy())
    prompt = prompt_template.format(question_json=json.dumps(cleaned_question, ensure_ascii=False, indent=2))

    if args.debug:
        print(f"--- LLM Prompt for {question_id} ---")
        print(prompt)
        print("--- End of LLM Prompt ---")

    llm_answers = call_and_parse_llm_api(
        model, [prompt] + images_to_send, args.retry_step7, args.rate_limit_wait
    )
    
    llm_answer = llm_answers[0] if llm_answers else {"error": "LLM returned an empty list."}

    return {
        "question_id": question_id,
        "llm_response": llm_answer
    }

def solve_consecutive_problem(model, problem_data: Dict[str, Any], prompt_template: str, image_base_dir: Path, args: argparse.Namespace):
    """Handles the logic for solving a consecutive problem."""
    problem_data_cleaned = json.loads(json.dumps(problem_data))
    clean_question_for_prompt(problem_data_cleaned)

    case_presentation = problem_data_cleaned.get("case_presentation", {})
    sub_questions = problem_data_cleaned.get("sub_questions", [])
    if not case_presentation or not sub_questions:
        return []

    print(f"  Solving consecutive problem: {problem_data.get('id')}")

    case_images = get_images(case_presentation.get("images", []), image_base_dir)
    
    case_text = case_presentation.get("text", "")
    case_images_prompt = "\n## 症例提示の画像\n" + "\n".join([f"- 画像 {img.get('id', '')}" for img in case_presentation.get("images", [])]) if case_images else ""

    sub_questions_prompt_parts = []
    for sub_q in sub_questions:
        sub_q_text = f"### 設問 {sub_q.get('problem_number')}\n{sub_q.get('text', '')}"
        if sub_q.get("images"):
            sub_q_text += "\n（この設問に紐づく画像があります）"
        sub_q_text += "\n\n**選択肢:**\n" + "\n".join([f"{c.get('id')}. {c.get('text')}" for c in sub_q.get("choices", [])])
        sub_questions_prompt_parts.append(sub_q_text)

    prompt = prompt_template.format(
        case_text=case_text,
        case_images_prompt=case_images_prompt,
        sub_questions_prompt="\n\n---\n\n".join(sub_questions_prompt_parts),
        first_sub_question_number=sub_questions[0].get("problem_number", ""),
        second_sub_question_number=sub_questions[1].get("problem_number", "") if len(sub_questions) > 1 else ""
    )

    all_images = case_images
    for sub_q in sub_questions:
        all_images.extend(get_images(sub_q.get("images", []), image_base_dir))

    if args.debug:
        print(f"--- LLM Prompt for {problem_data.get('id')} ---")
        print(prompt)
        print("--- End of LLM Prompt ---")

    llm_answers = call_and_parse_llm_api(
        model, [prompt] + all_images, args.retry_step7, args.rate_limit_wait
    )

    results = []
    if isinstance(llm_answers, list) and len(llm_answers) == len(sub_questions):
        for i, sub_q in enumerate(sub_questions):
            results.append({
                "question_id": sub_q.get("id"),
                "llm_response": llm_answers[i]
            })
    else:
        print(f"      Warning: LLM returned {len(llm_answers) if isinstance(llm_answers, list) else 'non-list'} answers, but expected {len(sub_questions)}. Storing raw response.")
        results.append({
            "question_id": sub_questions[0].get("id"),
            "llm_response": llm_answers
        })

    return results

def run(args):
    """Main function to solve problems using LLM."""
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    model = genai.GenerativeModel(args.model_name)
    
    output_dir = Path(DEFAULT_OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    final_json_dir = Path("output/json")
    image_base_dir = Path("output/images")

    if not final_json_dir.exists():
        print(f"Error: Final JSON directory not found at '{final_json_dir}'")
        return

    files_to_process = [f for f in final_json_dir.glob("*.json") if f.exists()]
    if not files_to_process:
        print("No JSON files found to process.")
        return

    single_prompt_template = SINGLE_PROMPT_PATH.read_text(encoding="utf-8")
    consecutive_prompt_template = CONSECUTIVE_PROMPT_PATH.read_text(encoding="utf-8")

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
                    result = solve_single_problem(model, problem_data, single_prompt_template, image_base_dir, args)
                    if result: results_to_save.append(result)
                
                elif problem_format == 'consecutive':
                    results = solve_consecutive_problem(model, problem_data, consecutive_prompt_template, image_base_dir, args)
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
                        "llm_response": res["llm_response"]
                    }
                    with output_file.open("a", encoding="utf-8") as f:
                        f.write(json.dumps(result_entry, ensure_ascii=False) + "\n")
                
                if results_to_save:
                    time.sleep(args.rate_limit_wait)

        print(f"Finished processing {file_path.name}. Results saved to {output_file}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Solve problems in JSON files using an LLM.")
    parser.add_argument("--model-name", type=str, default="gemini-1.5-pro-latest", help="LLM model name.")
    parser.add_argument("--rate-limit-wait", type=float, default=DEFAULT_RATE_LIMIT_WAIT, help="Wait time between API calls.")
    parser.add_argument("--retry-step7", type=int, default=DEFAULT_RETRY, help="Retries for Step 7.")
    parser.add_argument("--num-runs", type=int, default=DEFAULT_NUM_RUNS, help="Number of runs per question.")
    parser.add_argument("--debug", action="store_true", help="Enable debug messages.")
    parser.add_argument("--files", nargs='+', type=str, help=argparse.SUPPRESS)
    args = parser.parse_args()
    
    run(args)
