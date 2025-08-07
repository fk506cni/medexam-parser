import re
import json
from pathlib import Path
import logging

def chunk_consecutive_questions(input_path: Path, output_path: Path, pdf_stem: str):
    """
    Reads step2_reordered_text.txt, detects consecutive question blocks,
    and outputs them as chunks.
    Triggered by sentences in the format "次の文を読み、XX～YY の問いに答えよ。".
    (step2_reordered_text.txtを読み込み、連続問題を検知してチャンクとして出力する。
    「次の文を読み、XX～YY の問いに答えよ。」という形式の文をトリガーとする。)
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Starting Step 3b: Chunking consecutive questions from {input_path}")

    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            full_text = f.read()
    except FileNotFoundError:
        logger.error(f"Input file not found: {input_path}")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump([], f)
        return

    # --- Pre-processing ---
    # Keep page break markers for more precise chunking
    text_content = re.sub(r'DKIX-01-CH-\d+\d*\n?', '', full_text)
    text_content = re.sub(r'◎指示があるまで開かないこと.\n', '', text_content)
    text_content = re.sub(r'（令和\s+年\s+月\s+日\s+時\s+分\s+～\s+時\s+分）\n', '', text_content)
    text_content = re.sub(r'注意事項\n', '', text_content)
    text_content = re.sub(r'52416001830117C\n', '', text_content)
    text_content = re.sub(r'52416001830117\nC\n', '', text_content)
    # Remove lines that are just numbers (likely page footers)
    text_content = re.sub(r'^\d+\n', '', text_content, flags=re.MULTILINE)
    # Remove example sections
    text_content = re.sub(r'（例\d+\).+?（例\d+\）の正解は.+?\n', '', text_content, flags=re.DOTALL)
    text_content = re.sub(r'（例\d+\).+?すればよい。\n', '', text_content, flags=re.DOTALL)
    text_content = re.sub(r'答案用紙①の場合、.+?或\n', '', text_content, flags=re.DOTALL)
    text_content = re.sub(r'\n{3,}', '\n\n', text_content) # Normalize newlines

    # --- Chunking Logic ---
    consecutive_chunks = []
    # Regex to find the start of a consecutive block, supporting '～' and '、'
    start_pattern = re.compile(r"(次の文を読み、(\d+)(?:、|～)(\d+) の問いに答えよ。)")
    
    matches = list(start_pattern.finditer(text_content))

    if not matches:
        logger.info("No consecutive question blocks found.")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump([], f)
        return

    for i, match in enumerate(matches):
        start_pos = match.start()
        start_q_num = int(match.group(2))
        end_q_num = int(match.group(3))
        next_q_num_after_block = end_q_num + 1

        # Determine the end of the current consecutive block
        # Find the start of the *next* consecutive block, or take the rest of the file
        end_pos = len(text_content)
        if i + 1 < len(matches):
            end_pos = matches[i + 1].start()
        
        # Get the text of the current potential block
        current_block_text = text_content[start_pos:end_pos]

        # Refine the end position by looking for the start of the next single question
        # that logically follows the current consecutive block.
        final_chunk_text = current_block_text
        
        # A more specific pattern to find the start of the next question
        # This looks for the question number at the start of a line, preceded by a page break or newline.
        next_question_pattern = re.compile(f"((?:--- Page \d+ ---\n|\n){re.escape(str(next_q_num_after_block))}\u3000)")
        next_q_match = next_question_pattern.search(current_block_text)

        if next_q_match:
            # If we find the start of the next question, cut the chunk right before it.
            final_chunk_text = current_block_text[:next_q_match.start()]
            logger.debug(f"Refined end position for questions {start_q_num}-{end_q_num} by finding start of question {next_q_num_after_block}.")

        # Clean up the final text by removing page markers
        chunk_text_cleaned = re.sub(r'--- Page \d+ ---\n', '', final_chunk_text).strip()
        question_numbers = list(range(start_q_num, end_q_num + 1))

        chunk_data = {
            "source_pdf": f"{pdf_stem}.pdf",
            "type": "consecutive",
            "question_numbers": question_numbers,
            "text": chunk_text_cleaned
        }
        consecutive_chunks.append(chunk_data)
        logger.info(f"Extracted consecutive chunk for questions: {question_numbers}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(consecutive_chunks, f, ensure_ascii=False, indent=2)
        
    logger.info(f"Successfully saved {len(consecutive_chunks)} consecutive chunks to {output_path}")