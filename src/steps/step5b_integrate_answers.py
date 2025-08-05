from pathlib import Path
import json
from typing import List, Dict, Any, Optional

def format_answer_info(answer_list: List[str]) -> Dict[str, Any]:
    """
    解答リストを、問題JSONに統合するための辞書形式に変換する。
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

def integrate_answers(
    structured_problems_path: Path, 
    parsed_answer_key_path: Optional[Path], 
    image_mapping_paths: List[Path],
    intermediate_dir: Path
) -> Optional[Path]:
    """
    構造化された問題データに、パースされた正解情報と画像マッピング情報を統合する。
    """
    print(f"  [Step 5b] Integrating data for {structured_problems_path.name}")

    try:
        with open(structured_problems_path, 'r', encoding='utf-8') as f:
            problems: List[Dict[str, Any]] = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"  [Step 5b] Error reading or parsing structured problems file: {e}")
        return None

    # --- 正解キーの読み込み ---
    answer_key: Dict[str, List[str]] = {}
    if parsed_answer_key_path and parsed_answer_key_path.exists():
        try:
            with open(parsed_answer_key_path, 'r', encoding='utf-8') as f:
                answer_key = json.load(f)
            print(f"  [Step 5b] Loaded answer key from {parsed_answer_key_path.name}")
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"  [Step 5b] Warning: Could not read or parse answer key file: {e}")
    else:
        print("  [Step 5b] Warning: Answer key file not provided or not found. Proceeding without answer data.")

    # --- 画像マッピングの読み込み ---
    image_mappings: Dict[str, List[Dict[str, Any]]] = {}
    for mapping_path in image_mapping_paths:
        if mapping_path and mapping_path.exists():
            try:
                with open(mapping_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for key, value in data.items():
                        if key in image_mappings:
                            # 重複を避けながら結合
                            existing_paths = {img['image_path'] for img in image_mappings[key]}
                            for img_info in value:
                                if img_info['image_path'] not in existing_paths:
                                    image_mappings[key].append(img_info)
                        else:
                            image_mappings[key] = value
                print(f"  [Step 5b] Loaded and merged image mappings from {mapping_path.name}")
            except (FileNotFoundError, json.JSONDecodeError) as e:
                print(f"  [Step 5b] Warning: Could not read or parse image mapping file {mapping_path.name}: {e}")

    # --- 問題データへの統合処理 ---
    integrated_answers_count = 0
    integrated_images_count = 0
    unmatched_problems_count = 0

    for problem in problems:
        join_key = problem.get("join_key")
        if not join_key:
            unmatched_problems_count += 1
            continue

        # 正解情報の統合
        answer_list = answer_key.get(join_key)
        if answer_list:
            answer_info = format_answer_info(answer_list)
            problem["answer"] = answer_info
            integrated_answers_count += 1
        
        # 画像情報の統合
        image_info_list = image_mappings.get(join_key)
        if image_info_list:
            # 既存のimagesリストを初期化または取得
            if "images" not in problem or not isinstance(problem["images"], list):
                problem["images"] = []
            
            # 新しい画像情報を追加（重複を避ける）
            existing_paths = {img.get('path') for img in problem["images"] if isinstance(img, dict)}
            for new_img_info in image_info_list:
                if new_img_info.get('image_path') not in existing_paths:
                    problem["images"].append({
                        "id": new_img_info.get('image_id'),
                        "path": new_img_info.get('image_path')
                    })
            
            # パスでソートして順序を安定させる
            problem["images"].sort(key=lambda x: x.get('path', ''))
            integrated_images_count += 1

    print(f"  [Step 5b] Integrated answers for {integrated_answers_count} problems.")
    print(f"  [Step 5b] Integrated images for {integrated_images_count} problems.")
    if unmatched_problems_count > 0:
        print(f"  [Step 5b] Warning: {unmatched_problems_count} problems without a join_key were skipped.")

    # 出力パスを生成
    exam_id_part = structured_problems_path.parent.name
    output_dir = intermediate_dir / exam_id_part
    output_dir.mkdir(exist_ok=True, parents=True)

    # --- どの解答キーが使われなかったかを特定 ---
    used_join_keys = {p.get("join_key") for p in problems if p.get("join_key")}
    unmatched_answers = [
        {"join_key": k, "answer": v} for k, v in answer_key.items() if k not in used_join_keys
    ]
    if unmatched_answers:
        print(f"  [Step 5b] Warning: {len(unmatched_answers)} answer keys were not matched to any problem.")
        unmatched_answers_path = output_dir / "step5b_unmatched_answers.json"
        try:
            with open(unmatched_answers_path, 'w', encoding='utf-8') as f:
                json.dump(unmatched_answers, f, ensure_ascii=False, indent=2)
            print(f"  [Step 5b] Saved unmatched answer keys to: {unmatched_answers_path}")
        except IOError as e:
            print(f"  [Step 5b] Error writing unmatched answers file: {e}")

    output_path = output_dir / "step5b_integrated_answers.json"
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(problems, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"  [Step 5b] Error writing output file: {e}")
        return None
        
    return output_path