import json
from pathlib import Path
import shutil
from PIL import Image

def finalize_output(
    integrated_json_path: Path,
    output_json_dir: Path,
    output_image_dir: Path,
    intermediate_dir: Path
) -> Path:
    """
    統合済みJSONを最終出力形式に変換し、画像を整理して出力する。
    Converts the integrated JSON to the final output format and organizes/outputs images.
    """
    print(f"  [Step 6] Finalizing output for {integrated_json_path.name}...")

    try:
        with open(integrated_json_path, 'r', encoding='utf-8') as f:
            problems = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"  [Step 6] Error reading or parsing integrated JSON file: {e}")
        return None

    output_json_dir.mkdir(parents=True, exist_ok=True)
    output_image_dir.mkdir(parents=True, exist_ok=True)

    exam_id = integrated_json_path.parent.name # e.g., tp240424-01

    final_problems = []
    for problem_data in problems:
        # This script currently only handles 'single' format.
        # The combined list of single and consecutive problems will be created in step5b in the future.
        # このスクリプトは現在 'single' 形式のみを扱う。
        # 将来的に、単一問題と連続問題の結合リストはstep5bで作成される。
        new_problem_structure = {
            "id": problem_data.get("id"),
            "problem_format": "single",
            "problem": problem_data
        }

        problem_obj = new_problem_structure["problem"]

        if "images" in problem_obj and isinstance(problem_obj.get("images"), list) and problem_obj["images"]:
            new_image_info_list = []
            for img_info in problem_obj["images"]:
                if not isinstance(img_info, dict) or 'path' not in img_info or 'id' not in img_info:
                    continue

                img_relative_path_str = img_info['path']
                image_id = img_info['id']
                img_relative_path = Path(img_relative_path_str)

                try:
                    pdf_stem_from_filename = img_relative_path.name.split('_p')[0]
                except IndexError:
                    print(f"  [Step 6] Warning: Could not determine source PDF stem from image filename: {img_relative_path.name}. Skipping.")
                    continue

                original_image_path = intermediate_dir / pdf_stem_from_filename / img_relative_path
                
                if not original_image_path.exists():
                    print(f"  [Step 6] Warning: Image file not found: {original_image_path}. Skipping.")
                    continue

                new_image_filename = f"{exam_id}-{problem_obj.get('join_key', 'unknown')}-{image_id}.webp"
                new_image_path_abs = output_image_dir / new_image_filename

                try:
                    img_pil = Image.open(original_image_path)
                    img_pil.save(new_image_path_abs, format="WebP", lossless=True)
                    
                    new_image_info_list.append({
                        "id": image_id,
                        "path": new_image_filename
                    })
                except Exception as e:
                    print(f"  [Step 6] Error processing image {original_image_path}: {e}. Skipping.")
                    continue
            
            problem_obj["images"] = new_image_info_list
        
        final_problems.append(new_problem_structure)

    final_json_output_path = output_json_dir / f"{exam_id}.json"
    try:
        with open(final_json_output_path, 'w', encoding='utf-8') as f:
            json.dump(final_problems, f, ensure_ascii=False, indent=2)
        print(f"  [Step 6] Completed. Final JSON output: {final_json_output_path}")
    except IOError as e:
        print(f"  [Step 6] Error writing final JSON output: {e}")
        return None

    return final_json_output_path