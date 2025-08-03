import fitz  # PyMuPDF
import json
from pathlib import Path

def extract_raw_data(pdf_path: Path, intermediate_dir: Path):
    """
    PDFからテキスト、画像、およびそれらの座標情報を抽出し、中間ファイルとして保存する。

    Args:
        pdf_path (Path): 入力PDFファイルのパス。
        intermediate_dir (Path): 中間ファイル群を保存する親ディレクトリ。
    """
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"Error opening or processing {pdf_path}: {e}")
        return None

    # PDF名に基づいた中間出力ディレクトリを作成 (例: intermediate/118a/)
    pdf_stem = pdf_path.stem
    step_output_dir = intermediate_dir / pdf_stem
    step_output_dir.mkdir(parents=True, exist_ok=True)

    all_data = []

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        
        # テキストを詳細な構造(座標含む)で抽出
        raw_text_blocks = page.get_text("dict").get("blocks", [])
        
        # JSONシリアライズできない画像バイナリを削除する
        text_blocks = []
        for block in raw_text_blocks:
            if block["type"] == 1 and "image" in block:
                # 画像ブロックからバイナリデータを削除し、メタデータのみ保持
                del block["image"]
            text_blocks.append(block)
        
        # 画像情報を抽出
        image_list = page.get_images(full=True)
        
        page_data = {
            "page_number": page_num + 1,
            "text_blocks": text_blocks,
            "images": []
        }

        for img_index, img in enumerate(image_list):
            xref = img[0]
            
            # ページ上の画像の表示矩形を取得
            img_rects = page.get_image_rects(xref)

            if img_rects:
                page_data["images"].append({
                    "image_index": img_index,
                    "xref": xref,
                    # fitz.Rect オブジェクトはJSON化できないためリストに変換
                    "rects": [list(rect) for rect in img_rects],
                })

        all_data.append(page_data)

    # 中間ファイルに保存
    output_path = step_output_dir / "step1_raw_extraction.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    print(f"Successfully extracted raw data to {output_path}")
    return output_path

if __name__ == '__main__':
    # このファイルはモジュールとして利用されることを想定しています。
    # 例: python -m src.steps.step1_extract
    print("This script is a module and is meant to be imported.")
