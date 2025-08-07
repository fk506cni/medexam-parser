
import json
import re
from pathlib import Path
from typing import List, Dict, Any

def create_consecutive_join_key(pdf_stem: str, start_q: int, end_q: int) -> str:
    """
    Create a join key for consecutive questions, e.g., 'C-60-62'.
    """
    # e.g., tp220502-01c_01 -> C
    match = re.search(r'-(\d{2})([a-zA-Z])_', pdf_stem)
    if match:
        block_char = match.group(2).upper()
    else:
        # Fallback for unexpected formats, though the regex should be robust
        block_char = "X" 
    return f"{block_char}-{start_q}-{end_q}"

def map_consecutive_images(
    step1_path: Path,
    step3b_path: Path,
    output_path: Path
):
    """
    Maps images to consecutive question blocks based on associated text.
    """
    print(f"  [Step 4d] Running Consecutive Image-Question Mapping...")
    print(f"  [Step 4d] Reading raw data from: {step1_path}")
    print(f"  [Step 4d] Reading consecutive chunks from: {step3b_path}")

    try:
        with open(step1_path, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
        with open(step3b_path, 'r', encoding='utf-8') as f:
            consecutive_chunks = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"  [Step 4d] Error reading input files: {e}")
        return

    image_mapping = {}
    
    # Regex to find patterns like (問題60〜62) or (問題 60, 61, 62)
    pattern = re.compile(r'問題\s?(\d+)(?:〜|、|,|\s)+(\d+)')

    # Extract all images from the raw data
    all_images = []
    for page in raw_data:
        for image in page.get("images", []):
            all_images.append(image)

    for chunk in consecutive_chunks:
        q_numbers = chunk.get("question_numbers", [])
        if not q_numbers or len(q_numbers) < 2:
            continue
        
        start_q, end_q = q_numbers[0], q_numbers[-1]
        join_key = create_consecutive_join_key(step3b_path.parent.name, start_q, end_q)
        
        matched_images = []

        for image in all_images:
            associated_text = image.get("associated_text", "")
            match = pattern.search(associated_text)
            if match:
                img_start_q, img_end_q = int(match.group(1)), int(match.group(2))
                # Check if the question range in the image text matches the chunk's range
                if img_start_q == start_q and img_end_q == end_q:
                    matched_images.append({
                        "image_path": image.get("image_path"),
                        "source_page": image.get("source_page", raw_data.index(page) + 1),
                        "source_text": associated_text,
                    })

        if matched_images:
            # Sort images by path and assign IDs (A, B, C...)
            matched_images.sort(key=lambda x: x.get("image_path", ""))
            for i, img_info in enumerate(matched_images):
                img_info["image_id"] = chr(ord('A') + i)
            
            image_mapping[join_key] = matched_images
            print(f"  [Step 4d] Mapped {len(matched_images)} images to join_key: {join_key}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(image_mapping, f, ensure_ascii=False, indent=2)

    print(f"  [Step 4d] Completed. Output: {output_path}")
