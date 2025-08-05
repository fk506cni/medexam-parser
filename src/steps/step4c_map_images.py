
import json
import re
from pathlib import Path
from typing import Dict, Any, Optional, List

def map_images_to_questions(
    step1_output_path: Path,
    structured_problem_path: Path, # この引数は現在未使用だが、将来的な拡張のために残す
    intermediate_dir: Path,
) -> Optional[Path]:
    """
    画像PDFの生データ(step1)に含まれるassociated_textをルールベースで解析し、
    問題(join_key)と画像の対応関係をマッピングする。
    """
    print(f"  [Step 4c] Mapping images from {step1_output_path.name} using rule-based approach...")

    # --- 1. 入力ファイルの読み込み ---
    try:
        with open(step1_output_path, 'r', encoding='utf-8') as f:
            raw_data_per_page = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"  [Step 4c] Error reading or parsing image extraction file: {e}")
        return None

    # --- 2. ルールベースのマッピング処理 ---
    all_image_mappings: Dict[str, List[Dict[str, Any]]] = {}

    # 正規表現パターンを修正: 「(A 問題20)」のような、最も信頼できる部分のみを抽出する
    pattern = re.compile(r"[（(]([A-ZＡ-Ｚ])[\s　]*問題[\s　]*(\d+)[\s　]*[)）]")

    for page_data in raw_data_per_page:
        page_num = page_data.get("page_number", "N/A")
        images_on_page = page_data.get("images", [])

        if not images_on_page:
            continue

        images_on_page.sort(key=lambda img: img.get("bbox", [0, 0, 0, 0])[1])

        for image_info in images_on_page:
            associated_text = image_info.get("associated_text", "")
            image_path = image_info.get("image_path")

            if not associated_text or not image_path:
                continue

            matches = pattern.findall(associated_text)
            
            if matches:
                question_block, question_number = matches[-1]
                join_key = f"{question_block}-{question_number}"

                if join_key not in all_image_mappings:
                    all_image_mappings[join_key] = []

                if not any(img['image_path'] == image_path for img in all_image_mappings[join_key]):
                    all_image_mappings[join_key].append({
                        "image_path": image_path,
                        "source_page": page_num,
                        "source_text": associated_text
                    })
            else:
                print(f"    - [Warning] Could not parse join_key from associated_text on page {page_num}: '{associated_text}'")

    # --- 3. 項番の付与 ---
    for join_key in all_image_mappings:
        # 画像リストをimage_pathでソートして、A, B, C...の順序を安定させる
        image_list = sorted(all_image_mappings[join_key], key=lambda x: x['image_path'])
        
        for i, image_info in enumerate(image_list):
            image_info['image_id'] = chr(ord('A') + i)
        
        all_image_mappings[join_key] = image_list

    # --- 4. 出力ファイルの保存 ---
    pdf_stem = step1_output_path.parent.name
    output_dir = intermediate_dir / pdf_stem
    output_dir.mkdir(exist_ok=True, parents=True)
    output_path = output_dir / "step4c_image_mapping.json"

    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(all_image_mappings, f, ensure_ascii=False, indent=2)
        print(f"  [Step 4c] Completed. Output: {output_path}")
    except IOError as e:
        print(f"  [Step 4c] Error writing output file: {e}")
        return None

    return output_path
