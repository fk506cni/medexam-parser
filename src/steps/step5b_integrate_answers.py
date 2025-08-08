import re
from pathlib import Path
import json
from typing import List, Dict, Any, Optional

def format_answer_info(answer_list: List[str]) -> Dict[str, Any]:
    """
    Converts a list of answers into a dictionary format for integration into the problem JSON.
    """
    if not answer_list:
        return {}
    first_answer = answer_list[0]
    try:
        float_val = float(first_answer)
        int_val = int(float_val)
        value = int_val if int_val == float_val else float_val
        return {"value": value, "unit": None}
    except (ValueError, TypeError):
        formatted_choices = [str(ans).lower() for ans in answer_list]
        return {"choices": formatted_choices}

def _integrate_data_into_problem(problem: Dict[str, Any], answer_key: Dict[str, List[str]], image_mappings: Dict[str, List[Dict[str, Any]]]):
    """
    Integrates answer and image data into a single problem dictionary (or a sub-question).
    """
    join_key = problem.get("join_key")
    if not join_key:
        return

    # Integrate answer information
    if answer_key and join_key in answer_key:
        problem["answer"] = format_answer_info(answer_key[join_key])

    # Integrate image information
    if image_mappings and join_key in image_mappings:
        if "images" not in problem or not isinstance(problem.get("images"), list):
            problem["images"] = []
        
        existing_paths = {img.get('path') for img in problem["images"] if isinstance(img, dict)}
        for new_img_info in image_mappings[join_key]:
            img_path = new_img_info.get('image_path') 
            if img_path not in existing_paths:
                problem["images"].append({
                    "id": new_img_info.get('image_id'),
                    "path": img_path
                })
        problem["images"].sort(key=lambda x: x.get('path', ''))

def _get_sort_key(join_key: str):
    """
    Generates a sortable key from a join_key (e.g., 'A-1', 'C-60-62').
    Sorts by the character part first, then by the first number.
    Example: 'A-1' -> ('A', 1), 'C-60-62' -> ('C', 60)
    """
    if not isinstance(join_key, str):
        return ('', float('inf')) # Return a default for non-string inputs

    match = re.match(r"([A-Za-z]+)-(\d+)", join_key)
    if match:
        char_part = match.group(1)
        num_part = int(match.group(2))
        return (char_part, num_part)
    
    # Fallback for keys that don't match (e.g., just a letter)
    return (join_key, float('inf'))

def integrate_answers(
    exam_id: str,
    single_problem_paths: List[Path],
    consecutive_problem_paths: List[Path],
    parsed_answer_key_path: Optional[Path],
    image_mapping_paths: List[Path],
    intermediate_dir: Path
) -> Optional[Path]:
    """
    Integrates all structured data (single, consecutive, answers, images) for a given exam ID.
    """
    print(f"  [Step 5b] Starting integration for exam ID: {exam_id}")
    # --- Load all problem data with de-duplication ---
    print("  [Step 5b] Identifying question numbers from consecutive blocks...")
    consecutive_q_numbers = set()
    consecutive_problems_data = []
    for path in consecutive_problem_paths:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    consecutive_problems_data.extend(data)
                    for problem_block in data:
                        for sub_q in problem_block.get("sub_questions", []):
                            if "problem_number" in sub_q:
                                consecutive_q_numbers.add(sub_q["problem_number"])
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"  [Step 5b] Warning: Could not read or parse consecutive file {path.name}: {e}")
    
    print(f"  [Step 5b] Found {len(consecutive_q_numbers)} questions within consecutive blocks: {sorted(list(consecutive_q_numbers))}")

    all_problems = list(consecutive_problems_data) # Start with all consecutive problems

    print("  [Step 5b] Loading single problems and filtering out duplicates...")
    for path in single_problem_paths:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    for problem in data:
                        problem_num = problem.get("problem_number")
                        if problem_num is not None and problem_num not in consecutive_q_numbers:
                            all_problems.append({
                                "id": problem.get("id"),
                                "problem_format": "single",
                                "problem": problem
                            })
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"  [Step 5b] Warning: Could not read or parse single problem file {path.name}: {e}")

    if not all_problems:
        print(f"  [Step 5b] No problems found for exam {exam_id} after filtering. Aborting.")
        return None

    # --- Load Answer Key ---
    answer_key = {}
    if parsed_answer_key_path and parsed_answer_key_path.exists():
        try:
            with open(parsed_answer_key_path, 'r', encoding='utf-8') as f:
                answer_key = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"  [Step 5b] Warning: Could not read or parse answer key file: {e}")

    # --- Load and Merge Image Mappings ---
    image_mappings = {}
    for path in image_mapping_paths:
        if path and path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for key, value in data.items():
                        if key not in image_mappings:
                            image_mappings[key] = []
                        image_mappings[key].extend(value)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                print(f"  [Step 5b] Warning: Could not read or parse image mapping file {path.name}: {e}")

    # --- Integrate data into each problem ---
    used_join_keys = set()
    for problem_obj in all_problems:
        if problem_obj.get("problem_format") == "single":
            problem_core = problem_obj.get("problem", {})
            _integrate_data_into_problem(problem_core, answer_key, image_mappings)
            if problem_core.get("join_key"): used_join_keys.add(problem_core.get("join_key"))
        
        elif problem_obj.get("problem_format") == "consecutive":
            case_presentation = problem_obj.get("case_presentation", {})
            _integrate_data_into_problem(case_presentation, {}, image_mappings)
            if problem_obj.get("join_key"): used_join_keys.add(problem_obj.get("join_key"))

            for sub_q in problem_obj.get("sub_questions", []):
                _integrate_data_into_problem(sub_q, answer_key, image_mappings)
                if sub_q.get("join_key"): used_join_keys.add(sub_q.get("join_key"))

    # --- Sort problems by join_key ---
    print(f"  [Step 5b] Sorting {len(all_problems)} problems by join_key.")
    def get_sort_key_for_problem(problem_obj):
        if problem_obj.get("problem_format") == "single":
            return _get_sort_key(problem_obj.get("problem", {}).get("join_key"))
        elif problem_obj.get("problem_format") == "consecutive":
            # Use the main join_key of the consecutive block for sorting
            return _get_sort_key(problem_obj.get("join_key"))
        return ('', float('inf')) # Fallback for unexpected formats
    
    all_problems.sort(key=get_sort_key_for_problem)

    # --- Unmatched Answer Key Check ---
    unmatched_answers = {k: v for k, v in answer_key.items() if k not in used_join_keys}
    if unmatched_answers:
        print(f"  [Step 5b] Warning: {len(unmatched_answers)} answer keys were not matched.")
        unmatched_path = intermediate_dir / exam_id / "step5b_unmatched_answers.json"
        unmatched_path.parent.mkdir(exist_ok=True, parents=True)
        with open(unmatched_path, 'w', encoding='utf-8') as f:
            # unmatched_answers is a dict, but we only need to save the keys (join_key)
            json.dump(list(unmatched_answers.keys()), f, ensure_ascii=False, indent=2)

    # --- Save Final Integrated File ---
    output_path = intermediate_dir / exam_id / "step5b_integrated.json"
    output_path.parent.mkdir(exist_ok=True, parents=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_problems, f, ensure_ascii=False, indent=2)

    print(f"  [Step 5b] Integration complete for {exam_id}. Output: {output_path}")
    return output_path