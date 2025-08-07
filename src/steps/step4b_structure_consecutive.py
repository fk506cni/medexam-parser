import json
import logging
import time
import re
from pathlib import Path
from typing import List, Dict, Any

import google.generativeai as genai
import os
from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")

logger = logging.getLogger(__name__)

def structure_consecutive_problems(
    step3b_output_path: Path,
    intermediate_dir: Path,
    model_name: str,
    rate_limit_wait: float,
    max_retries: int,
    debug: bool = False
) -> Path:
    """
    Parses consecutive problem chunks from step3b using an LLM.
    (LLMを使用して、step3bからの連続問題チャンクを解析する。)

    Args:
        step3b_output_path: Path to the step3b_consecutive_chunks.json file.
        intermediate_dir: The main intermediate directory.
        model_name: The name of the LLM model to use.
        rate_limit_wait: Seconds to wait between API calls.
        max_retries: Maximum number of retries for API calls.
        debug: If True, enables debug logging.

    Returns:
        Path to the generated structured JSON file.
    """
    pdf_stem = step3b_output_path.parent.name
    output_path = intermediate_dir / pdf_stem / "step4b_structured_consecutive.json"
    prompt_template_path = Path(__file__).parent / "step4b_prompt.txt"

    try:
        with open(step3b_output_path, 'r', encoding='utf-8') as f:
            chunks = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"[Step 4b] Could not read or parse {step3b_output_path}: {e}")
        return None

    if not chunks:
        logger.info(f"[Step 4b] No consecutive chunks to process for {pdf_stem}. Creating empty file.")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump([], f)
        return output_path

    if not API_KEY:
        logger.error("[Step 4b] GOOGLE_API_KEY is not set. Aborting.")
        return None
    genai.configure(api_key=API_KEY)

    try:
        with open(prompt_template_path, 'r', encoding='utf-8') as f:
            prompt_template = f.read()
    except FileNotFoundError:
        logger.error(f"[Step 4b] Prompt template not found at {prompt_template_path}")
        return None

    model = genai.GenerativeModel(model_name)
    structured_data_list = []

    for i, chunk in enumerate(chunks):
        text_to_parse = chunk.get("text", "")
        if not text_to_parse:
            continue

        # Pass the pdf_stem to the prompt
        prompt = prompt_template.replace("{{text}}", text_to_parse)
        prompt = prompt.replace("{{pdf_stem}}", pdf_stem)
        
        if debug:
            logger.debug(f"--- PROMPT for chunk {i+1} ---\n{prompt}\n--------------------------")

        logger.info(f"[Step 4b] Structuring consecutive problem chunk {i+1}/{len(chunks)} for {pdf_stem}...")

        for attempt in range(max_retries):
            try:
                response = model.generate_content(prompt)
                response_text = response.text.strip()
                
                cleaned_response_text = re.sub(r'^```json\n', '', response_text)
                cleaned_response_text = re.sub(r'\n```$', '', cleaned_response_text)
                
                structured_data = json.loads(cleaned_response_text)

                # --- Rule-based join_key generation ---
                block_char_match = re.search(r'-(\d{2})([a-zA-Z])_', pdf_stem)
                block_char = block_char_match.group(2).upper() if block_char_match else "X"

                sub_qs = structured_data.get("sub_questions", [])
                q_numbers = [q.get("problem_number") for q in sub_qs if q.get("problem_number") is not None]

                if q_numbers:
                    structured_data["problem_format"] = "consecutive"
                    structured_data["join_key"] = f"{block_char}-{min(q_numbers)}-{max(q_numbers)}"
                    
                    if "case_presentation" in structured_data and "images" not in structured_data["case_presentation"]:
                        structured_data["case_presentation"]["images"] = []

                    for sub_q in sub_qs:
                        if sub_q.get("problem_number"):
                            sub_q["join_key"] = f"{block_char}-{sub_q.get('problem_number')}"
                        if "images" not in sub_q:
                            sub_q["images"] = []
                # --- End of rule-based generation ---

                # Add original chunk info for context
                structured_data['source_pdf'] = chunk.get('source_pdf')
                structured_data['original_question_numbers'] = chunk.get('question_numbers')
                
                structured_data_list.append(structured_data)
                logger.info(f"[Step 4b] Successfully structured chunk {i+1}.")
                break  # Success, exit retry loop

            except Exception as e:
                logger.warning(f"[Step 4b] Attempt {attempt + 1}/{max_retries} failed for chunk {i+1}. Error: {e}")
                if attempt + 1 == max_retries:
                    logger.error(f"[Step 4b] Failed to structure chunk {i+1} after {max_retries} attempts.")
                    structured_data_list.append({"error": "Failed to parse", "chunk": chunk})
                else:
                    time.sleep(rate_limit_wait)
        
        if i < len(chunks) - 1:
            time.sleep(rate_limit_wait)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(structured_data_list, f, ensure_ascii=False, indent=2)

    logger.info(f"[Step 4b] Completed. Output: {output_path}")
    return output_path