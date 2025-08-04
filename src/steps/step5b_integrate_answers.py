from pathlib import Path
import json
from typing import List, Dict, Any, Optional

def format_answer_info(answer_list: List[str]) -> Dict[str, Any]:
    """
    解答リストを、問題JSONに統合するための辞書形式に変換する。
    例: ["B"] -> {"choices": ["b"]}
    例: ["B", "E"] -> {"choices": ["b", "e"]}
    例: ["600"] -> {"value": 600, "unit": null}
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
        # 解答の選択肢IDを小文字に変換する
        formatted_choices = [str(ans).lower() for ans in answer_list]
        return {"choices": formatted_choices}

def integrate_answers(
    structured_problems_path: Path, 
    parsed_answer_key_path: Path, 
    intermediate_dir: Path
) -> Optional[Path]:
    """
    パースされた正解情報を構造化された問題データに統合する。
    """
    print(f"  [Step 5b] Integrating answers from {parsed_answer_key_path.name} into {structured_problems_path.name}")

    try:
        with open(structured_problems_path, 'r', encoding='utf-8') as f:
            problems: List[Dict[str, Any]] = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"  [Step 5b] Error reading or parsing structured problems file: {e}")
        return None

    try:
        with open(parsed_answer_key_path, 'r', encoding='utf-8') as f:
            answer_key: Dict[str, List[str]] = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"  [Step 5b] Error reading or parsing parsed answer key file: {e}")
        answer_key = {}
        print("  [Step 5b] Warning: Proceeding without answer key data.")

    not_found_count = 0
    integrated_count = 0
    for problem in problems:
        join_key = problem.get("join_key")
        if not join_key:
            not_found_count += 1
            if "answer" not in problem:
                problem["answer"] = {}
            continue

        answer_list = answer_key.get(join_key)
        
        if answer_list:
            answer_info = format_answer_info(answer_list)
            if "answer" not in problem:
                problem["answer"] = {}
            problem["answer"].update(answer_info)
            integrated_count += 1
        else:
            not_found_count += 1
            if "answer" not in problem:
                 problem["answer"] = {}

    print(f"  [Step 5b] Successfully integrated answers for {integrated_count} problems.")
    if not_found_count > 0:
        print(f"  [Step 5b] Warning: Could not find answers for {not_found_count} problems.")

    # 出力パスを生成
    exam_id_part = structured_problems_path.parent.name
    output_dir = intermediate_dir / exam_id_part
    output_dir.mkdir(exist_ok=True, parents=True)
    output_path = output_dir / "step5b_integrated_answers.json"
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(problems, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"  [Step 5b] Error writing output file: {e}")
        return None
        
    return output_path
