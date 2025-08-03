import fitz  # PyMuPDF
import json
from pathlib import Path

def extract_raw_data(pdf_path: Path, intermediate_dir: Path):
    """
    PDFからテキスト、画像、およびそれらの座標情報を抽出し、中間ファイルとして保存する。
    ファイル名に 'seitou' が含まれる場合は、ページごとにプレーンテキストを抽出する。
    """
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"Error opening or processing {pdf_path}: {e}")
        return None

    pdf_stem = pdf_path.stem
    step_output_dir = intermediate_dir / pdf_stem
    step_output_dir.mkdir(parents=True, exist_ok=True)

    all_data = []

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        
        if "seitou" in pdf_path.name:
            # 正答値表はページごとのプレーンテキスト
            page_text = page.get_text("text")
            page_data = {"page_number": page_num + 1, "text": page_text}
        else:
            # 通常の問題PDFは詳細な構造
            raw_text_blocks = page.get_text("dict").get("blocks", [])
            text_blocks = []
            for block in raw_text_blocks:
                if block["type"] == 1 and "image" in block:
                    del block["image"]
                text_blocks.append(block)
            
            image_list = page.get_images(full=True)
            page_data = {
                "page_number": page_num + 1,
                "text_blocks": text_blocks,
                "images": []
            }
            for img_index, img in enumerate(image_list):
                xref = img[0]
                img_rects = page.get_image_rects(xref)
                if img_rects:
                    page_data["images"].append({
                        "image_index": img_index,
                        "xref": xref,
                        "rects": [list(rect) for rect in img_rects],
                    })

        all_data.append(page_data)

    output_path = step_output_dir / "step1_raw_extraction.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    print(f"Successfully extracted raw data to {output_path}")
    return output_path