import json
from pathlib import Path
import shutil
from PIL import Image
from typing import List, Dict, Any

def _process_image_list(
    image_list: List[Dict[str, Any]], 
    join_key: str, 
    exam_id: str, 
    output_image_dir: Path, 
    intermediate_dir: Path
) -> List[Dict[str, Any]]:
    """Processes a list of images, copies them, and returns the new image info."""
    if not isinstance(image_list, list):
        return []

    new_image_info_list = []
    for img_info in image_list:
        if not isinstance(img_info, dict) or 'path' not in img_info or 'id' not in img_info:
            continue

        # The path in step5b is relative to the intermediate directory, 
        # e.g., "images/tp220502-01c_02_p01_img0.webp"
        # It needs to be combined with the intermediate dir and the pdf_stem part.
        img_relative_path_str = img_info['path']
        image_id = img_info['id']
        
        # Extract pdf_stem from the image filename itself, e.g., "tp220502-01c_02"
        try:
            pdf_stem_from_filename = Path(img_relative_path_str).name.split('_p')[0]
        except IndexError:
            print(f"  [Step 6] Warning: Could not determine source PDF stem from image filename: {img_relative_path_str}. Skipping.")
            continue

        # Construct the full path to the source image in the intermediate directory
        original_image_path = intermediate_dir / pdf_stem_from_filename / img_relative_path_str
        
        if not original_image_path.exists():
            print(f"  [Step 6] Warning: Image file not found: {original_image_path}. Skipping.")
            continue

        new_image_filename = f"{exam_id}-{join_key}-{image_id}.webp"
        new_image_path_abs = output_image_dir / new_image_filename

        try:
            # Copying the file is sufficient as it's already in WebP format.
            shutil.copy(original_image_path, new_image_path_abs)
            
            new_image_info_list.append({
                "id": image_id,
                "path": f"images/{new_image_filename}" # Path relative to output/json/
            })
        except Exception as e:
            print(f"  [Step 6] Error processing image {original_image_path}: {e}. Skipping.")
            continue
            
    return new_image_info_list

def finalize_output(
    integrated_json_path: Path,
    output_json_dir: Path,
    output_image_dir: Path,
    intermediate_dir: Path
) -> Path:
    """
    Converts the integrated JSON to the final output format and organizes/outputs images.
    Handles both 'single' and 'consecutive' problem formats.
    """
    print(f"  [Step 6] Finalizing output for {integrated_json_path.name}...")

    try:
        with open(integrated_json_path, 'r', encoding='utf-8') as f:
            all_problem_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"  [Step 6] Error reading or parsing integrated JSON file: {e}")
        return None

    output_json_dir.mkdir(parents=True, exist_ok=True)
    output_image_dir.mkdir(parents=True, exist_ok=True)

    exam_id = integrated_json_path.parent.name

    for problem_data in all_problem_data:
        problem_format = problem_data.get("problem_format")

        if problem_format == "single":
            problem_core = problem_data.get("problem", {})
            if problem_core.get("images"):
                join_key = problem_core.get("join_key", "unknown")
                problem_core["images"] = _process_image_list(
                    problem_core["images"], join_key, exam_id, output_image_dir, intermediate_dir
                )
        
        elif problem_format == "consecutive":
            # Process images in case presentation
            case_presentation = problem_data.get("case_presentation", {})
            if case_presentation.get("images"):
                join_key = problem_data.get("join_key", "unknown-case")
                case_presentation["images"] = _process_image_list(
                    case_presentation["images"], join_key, exam_id, output_image_dir, intermediate_dir
                )

            # Process images in each sub-question
            for sub_q in problem_data.get("sub_questions", []):
                if sub_q.get("images"):
                    join_key = sub_q.get("join_key", "unknown-sub")
                    sub_q["images"] = _process_image_list(
                        sub_q["images"], join_key, exam_id, output_image_dir, intermediate_dir
                    )

    final_json_output_path = output_json_dir / f"{exam_id}.json"
    try:
        with open(final_json_output_path, 'w', encoding='utf-8') as f:
            json.dump(all_problem_data, f, ensure_ascii=False, indent=2)
        print(f"  [Step 6] Completed. Final JSON output: {final_json_output_path}")
    except IOError as e:
        print(f"  [Step 6] Error writing final JSON output: {e}")
        return None

    return final_json_output_path
