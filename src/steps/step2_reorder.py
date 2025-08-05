import json
from pathlib import Path
from typing import List, Dict, Any, Optional

def reorder_text(step1_output_path: Path, intermediate_dir: Path) -> Optional[Path]:
    """
    Step1で抽出した生データからテキストブロックを抽出し、人間が読む順序
    （y座標優先、次にx座標）に並べ替えてテキストファイルとして保存する。
    シンプルなBBoxベースのソートを行う。

    Args:
        step1_output_path (Path): Step1の出力JSONファイルのパス。
        intermediate_dir (Path): 中間ファイルを保存する親ディレクトリ。

    Returns:
        Path: 生成されたテキストファイルのパス。エラーの場合はNone。
    """
    pdf_stem = step1_output_path.parent.name
    step_output_dir = intermediate_dir / pdf_stem
    step_output_dir.mkdir(parents=True, exist_ok=True)

    try:
        with open(step1_output_path, "r", encoding="utf-8") as f:
            all_pages_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading or parsing {step1_output_path}: {e}")
        return None

    full_text = ""
    for page_data in all_pages_data:
        page_num = page_data.get('page_number', 'N/A')
        text_blocks: List[Dict[str, Any]] = page_data.get("text_blocks", [])

        if not text_blocks:
            continue

        # テキストブロックをy座標(bbox[1])、次にx座標(bbox[0])でソート
        try:
            sorted_blocks = sorted(text_blocks, key=lambda b: (b["bbox"][1], b["bbox"][0]))
        except (KeyError, IndexError) as e:
            print(f"Warning: Could not sort blocks on page {page_num} due to unexpected block format: {e}")
            # ソートに失敗した場合は、元の順序で処理を試みる
            sorted_blocks = text_blocks

        reordered_page_text = "\n".join([block.get("text", "") for block in sorted_blocks])
        
        full_text += f"--- Page {page_num} ---\n"

        full_text += reordered_page_text
        full_text += "\n\n"

    # 並べ替えたテキストをファイルに保存
    output_path = step_output_dir / "step2_reordered_text.txt"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(full_text)
        
    print(f"Successfully reordered text and saved to {output_path}")
    return output_path

if __name__ == '__main__':
    print("This script is a module and is meant to be imported.")