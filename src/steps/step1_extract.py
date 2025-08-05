import fitz  # PyMuPDF
import json
from pathlib import Path
from PIL import Image
import io
import math

def calculate_centroid(bbox):
    """Calculate the centroid (center point) of a bounding box."""
    x0, y0, x1, y1 = bbox
    return (x0 + x1) / 2, (y0 + y1) / 2

def calculate_distance(point1, point2):
    """Calculate the Euclidean distance between two points."""
    return math.sqrt((point1[0] - point2[0])**2 + (point1[1] - point2[1])**2)

def extract_raw_data(pdf_path: Path, intermediate_dir: Path, debug: bool = False):
    """
    PDFからテキスト、画像、およびそれらの座標情報を抽出し、中間ファイルとして保存する。
    ファイル名に 'seitou' が含まれる場合は、ページごとにプレーンテキストを抽出する。
    画像ブロックに最も近いテキストブロックを関連付ける。
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

    if debug:
        print(f"  [Step 1 Debug] Starting page iteration. Total pages: {len(doc)}")
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        if debug:
            print(f"  [Step 1 Debug] Processing page {page_num + 1}/{len(doc)}...")
        
        if "seitou" in pdf_path.name:
            # 正答値表はページごとのプレーンテキスト
            page_text = page.get_text("text")
            page_data = {"page_number": page_num + 1, "text": page_text}
        else:
            # 通常の問題PDFは詳細な構造
            raw_text_blocks = page.get_text("dict").get("blocks", [])
            
            # テキストブロックを整形し、画像ブロックの 'image' キーを削除
            text_blocks_on_page = []
            for block in raw_text_blocks:
                if block["type"] == 0: # type 0 is text block
                    text_blocks_on_page.append({
                        "bbox": block["bbox"],
                        "text": "".join([span["text"] for line in block["lines"] for span in line["spans"]])
                    })
            if debug:
                print(f"  [Step 1 Debug] Page {page_num + 1}: Found {len(text_blocks_on_page)} text blocks.")

            image_list = page.get_images(full=True)
            if debug:
                print(f"  [Step 1 Debug] Page {page_num + 1}: Found {len(image_list)} images.")

            page_data = {
                "page_number": page_num + 1,
                "text_blocks": text_blocks_on_page, # 整形したテキストブロック
                "images": []
            }
            
            # 画像保存用のディレクトリを作成
            image_output_dir = step_output_dir / "images"
            image_output_dir.mkdir(exist_ok=True)

            for img_index, img in enumerate(image_list):
                if debug:
                    print(f"  [Step 1 Debug] Page {page_num + 1}: Processing image {img_index + 1}/{len(image_list)}...")
                xref = img[0]
                base_image = doc.extract_image(xref)

                img_rects = page.get_image_rects(xref)
                
                if img_rects:
                    bbox = list(img_rects[0]) 
                    
                    image_filename = f"{pdf_stem}_p{page_num+1}_img{img_index+1}.webp"
                    image_path_abs = image_output_dir / image_filename
                    
                    try:
                        pix = fitz.Pixmap(doc, xref)
                        if pix.alpha:
                            pix = fitz.Pixmap(fitz.csRGBA, pix)
                            mode = "RGBA"
                        else:
                            pix = fitz.Pixmap(fitz.csRGB, pix)
                            mode = "RGB"
                        
                        img_pil = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
                        img_pil.save(image_path_abs, format="WebP", lossless=True)
                        pix = None
                        if debug:
                            print(f"  [Step 1 Debug] Page {page_num + 1}, Image {img_index + 1}: Image saved to {image_path_abs.name}")

                        # --- 画像に最も近いテキストを関連付けるロジック ---
                        if debug:
                            print(f"  [Step 1 Debug] Page {page_num + 1}, Image {img_index + 1}: Finding associated text...")
                        image_centroid = calculate_centroid(bbox)
                        closest_text = ""
                        min_distance = float('inf')

                        for text_block in text_blocks_on_page:
                            # "DK"で始まるテキストは関連付けの候補から除外
                            if text_block["text"].strip().startswith("DK"):
                                continue
                            text_centroid = calculate_centroid(text_block["bbox"])
                            distance = calculate_distance(image_centroid, text_centroid)
                            
                            text_bbox_bottom = float(text_block["bbox"][3])
                            image_bbox_top = float(bbox[1])
                            text_bbox_left = float(text_block["bbox"][0])
                            image_bbox_left = float(bbox[0])
                            text_bbox_right = float(text_block["bbox"][2])
                            image_bbox_right = float(bbox[2])

                            if text_bbox_bottom < image_bbox_top and \
                                max(text_bbox_left, image_bbox_left) < min(text_bbox_right, image_bbox_right):
                                distance = abs(text_bbox_bottom - image_bbox_top) * 0.5 + distance * 0.5
                            
                            if distance < min_distance:
                                min_distance = distance
                                closest_text = text_block["text"]
                        if debug:
                            print(f"  [Step 1 Debug] Page {page_num + 1}, Image {img_index + 1}: Associated text found: '{closest_text[:30]}...' ")
                        # --------------------------------------------------
                        
                        page_data["images"].append({
                            "image_index": img_index,
                            "bbox": bbox,
                            "filename": image_filename,
                            "image_path": str(image_path_abs.relative_to(step_output_dir)),
                            "associated_text": closest_text
                        })
                    except Exception as e:
                        print(f"  [Step 1] Warning: Could not save image {image_filename}: {e}")
                        continue
                else:
                    if debug:
                        print(f"  [Step 1 Debug] Page {page_num + 1}, Image {img_index + 1}: No bounding box found for image. Skipping.")

        all_data.append(page_data)
        if debug:
            print(f"  [Step 1 Debug] Finished processing page {page_num + 1}.")

    output_path = step_output_dir / "step1_raw_extraction.json"
    if debug:
        print(f"  [Step 1 Debug] Writing final output to {output_path}...")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    print(f"Successfully extracted raw data to {output_path}")
    return output_path
