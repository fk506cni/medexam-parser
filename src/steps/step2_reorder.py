import json
from pathlib import Path

def reorder_text(step1_output_path: Path, intermediate_dir: Path) -> Path:
    """
    Step1で抽出した生データからテキストブロックを抽出し、
    人間が読む順序（上から下、左から右）に並べ替えてテキストファイルとして保存する。

    Args:
        step1_output_path (Path): Step1の出力JSONファイルのパス。
        intermediate_dir (Path): 中間ファイルを保存する親ディレクトリ。

    Returns:
        Path: 生成されたテキストファイルのパス。
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
        blocks = page_data.get("text_blocks", [])
        
        # テキストブロックを行ごとにグループ化し、座標情報も保持
        lines = {}
        for block in blocks:
            if block.get("type") == 0: # 0はテキストブロック
                for line in block.get("lines", []):
                    # y0をキーとして行をグループ化
                    y0 = round(line["bbox"][1])
                    if y0 not in lines:
                        lines[y0] = []
                    
                    # 行に属するスパン（テキスト片）とx座標を追加
                    for span in line.get("spans", []):
                        lines[y0].append((span["bbox"][0], span["text"]))

        # y座標でソートされた行キーを取得
        sorted_y = sorted(lines.keys())

        # 各行内でx座標でスパンをソートし、テキストを結合
        reordered_page_text = ""
        for y in sorted_y:
            # 同じ行にあるテキスト片をx座標でソート
            line_spans = sorted(lines[y], key=lambda item: item[0])
            reordered_page_text += "".join(span[1] for span in line_spans) + "\n"
        
        full_text += f"--- Page {page_data.get('page_number', 'N/A')} ---\n"
        full_text += reordered_page_text
        full_text += "\n"

    # 並べ替えたテキストをファイルに保存
    output_path = step_output_dir / "step2_reordered_text.txt"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(full_text)
        
    print(f"Successfully reordered text and saved to {output_path}")
    return output_path

if __name__ == '__main__':
    print("This script is a module and is meant to be imported.")
