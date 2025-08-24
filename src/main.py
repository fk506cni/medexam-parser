import argparse
import json
import re
from pathlib import Path
import sys

# srcディレクトリをsys.pathに追加して、stepsモジュールをインポート可能にする
# Add the src directory to sys.path to allow importing the steps module
sys.path.append(str(Path(__file__).parent))

from steps.step1_extract import extract_raw_data
from steps.step2_reorder import reorder_text
from steps.step3_chunk import chunk_text_by_problem
from steps.step3b_chunk_consecutive import chunk_consecutive_questions
from steps.step4_structure import structure_problems
from steps.step4b_structure_consecutive import structure_consecutive_problems
from steps.step4c_map_images import map_images_to_questions
from steps.step4d_map_consecutive_images import map_consecutive_images
from steps.step5a_parse_answer_key import parse_answer_key
from steps.step5b_integrate_answers import integrate_answers
from steps.step5_5_create_summary import create_summary
from steps.step6_finalize import finalize_output
from steps.step7_solve_problem import run as run_step7
from steps.step8_analyze_difficulty import run as run_step8

# --- パス設定 / Path Settings ---
PROJECT_ROOT = Path(__file__).parent.parent
INPUT_DIR = PROJECT_ROOT / "input"
OUTPUT_DIR = PROJECT_ROOT / "output"
INTERMEDIATE_DIR = PROJECT_ROOT / "intermediate"

def setup_directories():
    """必要なディレクトリを作成する / Create necessary directories"""
    INPUT_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    INTERMEDIATE_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / "json").mkdir(exist_ok=True)
    (OUTPUT_DIR / "images").mkdir(exist_ok=True)

def get_exam_id_from_stem(pdf_stem: str) -> str:
    """ファイル名から共通の試験ID (例: tp240424-01) を抽出する
    Extracts a common exam ID (e.g., tp240424-01) from a filename stem.
    """
    # "tp240424-01a_01" -> "tp240424-01"
    match = re.match(r"(tp\d{6}-\d{2})", pdf_stem)
    if match:
        return match.group(1)
    # マッチしない場合 (例: 118a) は、そのまま返すか、エラー処理を行う
    # ここでは、ファイル名からアルファベットとそれに続く数字を除去するロジックを一旦削除し、
    # 命名規則に厳密に従うことを前提とする
    # If no match (e.g., 118a), return as is or handle error.
    # Here, the logic to remove alphabets and subsequent numbers is removed,
    # assuming strict adherence to the naming convention.
    return pdf_stem

def run_step1(pdf_path: Path, debug: bool):
    """Step 1: PDFから生データを抽出する / Extract raw data from PDF."""
    print(f"  [Step 1] Running Raw Extraction for {pdf_path.name}...")
    result_path = extract_raw_data(pdf_path, INTERMEDIATE_DIR, debug)
    if result_path:
        print(f"  [Step 1] Completed. Output: {result_path}")
    else:
        print(f"  [Step 1] Failed for {pdf_path.name}.")
    return result_path

def run_step2(step1_output_path: Path):
    """Step 2: テキストの順序を再構成する / Reorder text sequence."""
    if not step1_output_path or not step1_output_path.exists():
        print(f"  [Step 2] Skipped: Input file not found: {step1_output_path}")
        return None
    print(f"  [Step 2] Running Text Reordering for {step1_output_path.parent.name}...")
    result_path = reorder_text(step1_output_path, INTERMEDIATE_DIR)
    if result_path:
        print(f"  [Step 2] Completed. Output: {result_path}")
    else:
        print(f"  [Step 2] Failed for {step1_output_path.parent.name}.")
    return result_path

def run_step3(step2_output_path: Path, rate_limit_wait: float, model_name: str, max_retries: int, debug: bool):
    """Step 3: 問題ごとにテキストをチャンク化する / Chunk text by problem."""
    if not step2_output_path or not step2_output_path.exists():
        print(f"  [Step 3] Skipped: Input file not found: {step2_output_path}")
        return None
    print(f"  [Step 3] Running Problem Chunking for {step2_output_path.parent.name} using {model_name}...")
    result_path = chunk_text_by_problem(
        step2_output_path=step2_output_path, 
        intermediate_dir=INTERMEDIATE_DIR, 
        rate_limit_wait=rate_limit_wait,
        model_name=model_name,
        max_retries=max_retries,
        debug=debug
    )
    if result_path:
        print(f"  [Step 3] Completed. Output: {result_path}")
    else:
        print(f"  [Step 3] Failed for {step2_output_path.parent.name}.")
    return result_path

def run_step3b(step2_output_path: Path):
    """Step 3b: 連続問題をチャンク化する / Chunk consecutive problems."""
    if not step2_output_path or not step2_output_path.exists():
        print(f"  [Step 3b] Skipped: Input file not found: {step2_output_path}")
        return None
    pdf_stem = step2_output_path.parent.name
    output_path = INTERMEDIATE_DIR / pdf_stem / "step3b_consecutive_chunks.json"
    print(f"  [Step 3b] Running Consecutive Problem Chunking for {pdf_stem}...")
    chunk_consecutive_questions(step2_output_path, output_path, pdf_stem)
    if output_path.exists():
        print(f"  [Step 3b] Completed. Output: {output_path}")
        return output_path
    else:
        print(f"  [Step 3b] Failed for {pdf_stem}.")
        return None

def run_step4(step3_output_path: Path, model_name: str, rate_limit_wait: float, batch_size: int, max_batches: int, max_retries: int):
    """Step 4: 問題を構造化する / Structure problems."""
    if not step3_output_path or not step3_output_path.exists():
        print(f"  [Step 4] Skipped: Input file not found: {step3_output_path}")
        return None
    print(f"  [Step 4] Running Structure Parsing for {step3_output_path.parent.name}...")
    result_path = structure_problems(
        step3_output_path=step3_output_path,
        intermediate_dir=INTERMEDIATE_DIR,
        model_name=model_name,
        rate_limit_wait=rate_limit_wait,
        batch_size=batch_size,
        max_batches=max_batches,
        max_retries=max_retries
    )
    if result_path:
        print(f"  [Step 4] Completed. Output: {result_path}")
    else:
        print(f"  [Step 4] Failed for {step3_output_path.parent.name}.")
    return result_path

def run_step4b(step3b_output_path: Path, model_name: str, rate_limit_wait: float, max_retries: int, debug: bool):
    """Step 4b: 連続問題を構造化する / Structure consecutive problems."""
    if not step3b_output_path or not step3b_output_path.exists():
        print(f"  [Step 4b] Skipped: Input file not found: {step3b_output_path}")
        return None
    print(f"  [Step 4b] Running Consecutive Structure Parsing for {step3b_output_path.parent.name}...")
    result_path = structure_consecutive_problems(
        step3b_output_path=step3b_output_path,
        intermediate_dir=INTERMEDIATE_DIR,
        model_name=model_name,
        rate_limit_wait=rate_limit_wait,
        max_retries=max_retries,
        debug=debug
    )
    if result_path:
        print(f"  [Step 4b] Completed. Output: {result_path}")
    else:
        print(f"  [Step 4b] Failed for {step3b_output_path.parent.name}.")
    return result_path

def run_step4c(step1_output_path: Path, structured_problem_path: Path):
    """Step 4c: 画像と問題をマッピングする / Map images to questions."""
    if not step1_output_path or not step1_output_path.exists():
        print(f"  [Step 4c] Skipped: Input file not found: {step1_output_path}")
        return None
    if not structured_problem_path or not structured_problem_path.exists():
        print(f"  [Step 4c] Skipped: Corresponding structured problem file not found: {structured_problem_path}")
        return None
        
    print(f"  [Step 4c] Running Image-Question Mapping for {step1_output_path.parent.name}...")
    result_path = map_images_to_questions(
        step1_output_path=step1_output_path,
        structured_problem_path=structured_problem_path,
        intermediate_dir=INTERMEDIATE_DIR,
    )
    if result_path:
        print(f"  [Step 4c] Completed. Output: {result_path}")
    else:
        print(f"  [Step 4c] Failed for {step1_output_path.parent.name}.")
    return result_path

def run_step4d(step1_output_path: Path, step3b_output_path: Path):
    """Step 4d: 連続問題の画像をマッピングする / Map images for consecutive questions."""
    if not step1_output_path or not step1_output_path.exists():
        print(f"  [Step 4d] Skipped: Input file not found: {step1_output_path}")
        return None
    if not step3b_output_path or not step3b_output_path.exists():
        print(f"  [Step 4d] Skipped: Corresponding consecutive chunk file not found: {step3b_output_path}")
        return None

    pdf_stem = step1_output_path.parent.name
    output_path = INTERMEDIATE_DIR / pdf_stem / "step4d_consecutive_image_mapping.json"
    print(f"  [Step 4d] Running Consecutive Image-Question Mapping for {pdf_stem}...")
    map_consecutive_images(step1_output_path, step3b_output_path, output_path)
    if output_path.exists():
        print(f"  [Step 4d] Completed. Output: {output_path}")
        return output_path
    else:
        print(f"  [Step 4d] Failed for {pdf_stem}.")
        return None

def run_step5b(exam_id: str, single_problem_paths: list[Path], consecutive_problem_paths: list[Path], parsed_answer_key_path: Path, image_mapping_paths: list[Path]):
    """Step 5b: 複数の問題JSONを統合し、正解と画像情報を結合する / Combine multiple problem JSONs, and integrate answers and image information."""
    if not single_problem_paths and not consecutive_problem_paths:
        print(f"  [Step 5b] Skipped for {exam_id}: No structured problem files found.")
        return None

    print(f"  [Step 5b] Running Integration for exam {exam_id}...")
    result_path = integrate_answers(
        exam_id=exam_id,
        single_problem_paths=single_problem_paths,
        consecutive_problem_paths=consecutive_problem_paths,
        parsed_answer_key_path=parsed_answer_key_path,
        image_mapping_paths=image_mapping_paths,
        intermediate_dir=INTERMEDIATE_DIR
    )

    if result_path:
        print(f"  [Step 5b] Completed. Output: {result_path}")
    else:
        print(f"  [Step 5b] Failed for exam {exam_id}.")
    return result_path


def run_step5a(answer_key_extraction_path: Path, model_name: str, rate_limit_wait: float, max_retries: int):
    """Step 5a: 正答値表を解析する / Parse the answer key table."""
    if not answer_key_extraction_path or not answer_key_extraction_path.exists():
        print(f"  [Step 5a] Skipped: Input file not found: {answer_key_extraction_path}")
        return None
    
    print(f"  [Step 5a] Running Answer Key Parsing for {answer_key_extraction_path.parent.name}...")
    result_path = parse_answer_key(
        answer_key_extraction_path=answer_key_extraction_path,
        intermediate_dir=INTERMEDIATE_DIR,
        model_name=model_name,
        rate_limit_wait=rate_limit_wait,
        max_retries=max_retries
    )
    if result_path:
        print(f"  [Step 5a] Completed. Output: {result_path}")
    else:
        print(f"  [Step 5a] Failed for {answer_key_extraction_path.parent.name}.")
    return result_path

def run_step5_5(integrated_json_path: Path):
    """Step 5.5: 集計情報を作成する / Create summary information."""
    if not integrated_json_path or not integrated_json_path.exists():
        print(f"  [Step 5.5] Skipped: Input file not found: {integrated_json_path}")
        return None
    
    print(f"  [Step 5.5] Running Create Summary for {integrated_json_path.name}...")
    summary_path = integrated_json_path.parent / "step5_5_summary.json"
    create_summary(integrated_json_path, summary_path)
    return summary_path

def run_step6(integrated_json_path: Path):
    """Step 6: 最終生成を行う / Perform final generation."""
    if not integrated_json_path or not integrated_json_path.exists():
        print(f"  [Step 6] Skipped: Input file not found: {integrated_json_path}")
        return None
    
    print(f"  [Step 6] Running Finalization for {integrated_json_path.name}...")
    final_json_path = finalize_output(
        integrated_json_path=integrated_json_path,
        output_json_dir=OUTPUT_DIR / "json",
        output_image_dir=OUTPUT_DIR / "images",
        intermediate_dir=INTERMEDIATE_DIR
    )
    if final_json_path:
        print(f"  [Step 6] Completed. Output: {final_json_path}")
    else:
        print(f"  [Step 6] Failed for {integrated_json_path.name}.")
    return final_json_path

def main():
    """
    コマンドライン引数に基づいて、指定されたステップとファイルで解析処理を実行する。
    Runs the parsing process for specified steps and files based on command-line arguments.
    """
    parser = argparse.ArgumentParser(description="医師国家試験PDFを解析し、JSONと画像を生成します。/ Parses National Medical Examination PDFs to generate JSON and images.")
    parser.add_argument(
        "--steps",
        nargs='+',
        type=str, # 5a, 5b, 5.5, 6を扱えるようにstr型に変更 / Change to str to handle 5a, 5b, 5.5, 6
        default=['1', '2', '3', '3b', '4', '4b', '4c', '5a', '5b', '5.5', '6'], # デフォルトは全ステップ / Default is all steps
        help="実行するステップ番号をスペース区切りで指定します (例: 1 2 5a 5b 5.5 6)。/ Specify step numbers to run, separated by spaces (e.g., 1 2 5a 5b 5.5 6)."
    )
    parser.add_argument(
        "--files",
        nargs='+',
        type=str,
        help="処理対象のPDFファイル名をスペース区切りで指定します (例: 118a.pdf 118b.pdf)。指定しない場合はinputディレクトリ内の全PDFが対象です。/ Specify target PDF filenames separated by spaces (e.g., 118a.pdf 118b.pdf). If not specified, all PDFs in the input directory are targeted."
    )
    parser.add_argument(
        "--rate-limit-wait",
        type=float,
        default=10.0,
        help="LLM API呼び出し間の待機時間（秒）を指定します。デフォルトは10秒です。/ Specify the wait time (in seconds) between LLM API calls. Default is 10 seconds."
    )
    parser.add_argument(
        "--model-name",
        type=str,
        default="gemini-2.5-flash-lite",
        help="使用するLLMモデル名を指定します。/ Specify the LLM model name to use."
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5,
        help="Step 4でLLMに一度に送信する問題数を指定します。/ Specify the number of problems to send to the LLM at once in Step 4."
    )
    parser.add_argument(
        "--max-batches",
        type=int,
        default=0,
        help="Step 4で処理する最大のバッチ数を指定します。0の場合は全バッチを処理します。デバッグ用。/ Specify the maximum number of batches to process in Step 4. If 0, all batches are processed. For debugging."
    )
    parser.add_argument(
        "--retry-step3",
        type=int,
        default=3,
        help="Step 3のリトライ回数を指定します。/ Specify the number of retries for Step 3."
    )
    parser.add_argument(
        "--retry-step4",
        type=int,
        default=3,
        help="Step 4のリトライ回数を指定します。/ Specify the number of retries for Step 4."
    )
    parser.add_argument(
        "--retry-step4b",
        type=int,
        default=3,
        help="Step 4bのリトライ回数を指定します。/ Specify the number of retries for Step 4b."
    )
    
    parser.add_argument(
        "--retry-step5a",
        type=int,
        default=3,
        help="Step 5aのリトライ回数を指定します。/ Specify the number of retries for Step 5a."
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="デバッグメッセージを有効にします。/ Enable debug messages."
    )
    parser.add_argument(
        "--retry-step7",
        type=int,
        default=3,
        help="Step 7のリトライ回数を指定します。/ Specify the number of retries for Step 7."
    )
    parser.add_argument(
        "--num-runs",
        type=int,
        default=1,
        help="Step 7で同じ問題を複数回解く回数を指定します。/ Specify the number of times to solve the same problem in Step 7."
    )
    parser.add_argument(
        "--retry-step8",
        type=int,
        default=3,
        help="Step 8のリトライ回数を指定します。/ Specify the number of retries for Step 8."
    )
    
    args = parser.parse_args()

    setup_directories()
    
    # --- 処理対象ファイルの決定 / Determine target files ---
    if args.files:
        pdf_files = [INPUT_DIR / f for f in args.files if (INPUT_DIR / f).exists()]
        missing_files = set(args.files) - {p.name for p in pdf_files}
        if missing_files:
            print(f"Warning: The following files were not found in the input directory: {', '.join(missing_files)}")
    else:
        pdf_files = sorted(list(INPUT_DIR.glob("*.pdf")))

    if not pdf_files:
        print("No PDF files to process.")
        return

    # ステップの正規化 / Normalize steps
    target_steps = set(args.steps)

    print("--- Processing Configuration ---")
    print(f"Target Steps: {sorted(list(target_steps))}")
    print(f"Target Files: {[p.name for p in pdf_files]}")
    print(f"LLM Model: {args.model_name}")
    print(f"LLM API Wait: {args.rate_limit_wait}s")
    print(f"LLM Batch Size: {args.batch_size}")
    if args.max_batches > 0:
        print(f"LLM Max Batches: {args.max_batches}")
    print("-" * 30)

    # --- ステップ実行 / Execute Steps ---
    # 試験IDごとに中間ファイルのパスを管理
    # Manage intermediate file paths for each exam ID
    exam_intermediate_files = {}

    for pdf_path in pdf_files:
        print(f"Processing PDF: {pdf_path.name}")
        pdf_stem = pdf_path.stem
        exam_id = get_exam_id_from_stem(pdf_stem)

        if exam_id not in exam_intermediate_files:
            exam_intermediate_files[exam_id] = {
                "step4_outputs": [], 
                "step4b_outputs": [],
                "answer_key_extraction_output": None, 
                "parsed_answer_key_output": None,
                "image_extraction_outputs": [],
                "image_mapping_outputs": []
            }

        # ファイル名からファイルタイプを判定
        # Determine file type from filename
        file_type = "text"
        if pdf_path.name.endswith("_02.pdf"):
            file_type = "image"
        elif "seitou" in pdf_path.name:
            file_type = "answer"

        # 実行するステップを決定
        # Determine which steps to execute
        executable_steps = set()
        if file_type == "answer":
            if '5a' in target_steps: executable_steps.add('1') # 5aには1が必要 / Step 1 is required for 5a
            executable_steps.update(target_steps.intersection({'5a'}))
        elif file_type == "image":
            # 画像PDFはStep1（画像抽出）とStep4c（画像マッピング）を実行
            # Image PDFs run Step 1 (image extraction) and Step 4c (image mapping)
            executable_steps.update(target_steps.intersection({'1', '4c', '4d'}))
        else: # text
            # テキストPDFはテキスト処理ステップを実行
            # Text PDFs run text processing steps
            executable_steps.update(target_steps.intersection({'1', '2', '3', '3b', '4', '4b'}))


        # 各ステップの出力を管理
        # Manage the output of each step
        step_outputs = {}

        if '1' in executable_steps:
            step_outputs[1] = run_step1(pdf_path, args.debug)
            if file_type == "answer":
                exam_intermediate_files[exam_id]["answer_key_extraction_output"] = step_outputs[1]
            elif file_type == "image":
                exam_intermediate_files[exam_id]["image_extraction_outputs"].append(step_outputs[1])

        if '4c' in executable_steps:
            # step4cは、問題PDFと画像PDFの両方の情報が必要
            # Step 4c requires information from both the question PDF and the image PDF.
            # 1. 画像PDFのstep1生データ
            # 1. Step 1 raw data from the image PDF
            step1_output = step_outputs.get(1) or INTERMEDIATE_DIR / pdf_stem / "step1_raw_extraction.json"

            # 2. 対応する問題PDFのstep4構造化データを見つける
            # 2. Find the corresponding Step 4 structured data for the question PDF.
            # 例: tp240424-01a_02.pdf -> tp240424-01a_01.pdf
            # e.g., tp240424-01a_02.pdf -> tp240424-01a_01.pdf
            problem_pdf_stem = pdf_stem.replace('_02', '_01')
            structured_problem_path = INTERMEDIATE_DIR / problem_pdf_stem / "step4_structured_problems.json"
            
            # もし実行キャッシュに見つかればそれを使う
            # Use from execution cache if found
            if not structured_problem_path.exists():
                for path in exam_intermediate_files[exam_id].get("step4_outputs", []):
                    if problem_pdf_stem in str(path):
                        structured_problem_path = path
                        break

            step_outputs['4c'] = run_step4c(
                step1_output, 
                structured_problem_path,
            )
            if step_outputs.get('4c'):
                exam_intermediate_files[exam_id]["image_mapping_outputs"].append(step_outputs['4c'])

        if '4d' in executable_steps:
            # step4dは、画像PDFのstep1と問題PDFのstep3bが必要
            step1_output = step_outputs.get(1) or INTERMEDIATE_DIR / pdf_stem / "step1_raw_extraction.json"
            problem_pdf_stem = pdf_stem.replace('_02', '_01')
            step3b_output_path = INTERMEDIATE_DIR / problem_pdf_stem / "step3b_consecutive_chunks.json"
            
            step_outputs['4d'] = run_step4d(
                step1_output,
                step3b_output_path,
            )
            if step_outputs.get('4d'):
                exam_intermediate_files[exam_id]["image_mapping_outputs"].append(step_outputs['4d'])

        if '2' in executable_steps:
            step1_output = step_outputs.get(1) or INTERMEDIATE_DIR / pdf_stem / "step1_raw_extraction.json"
            step_outputs[2] = run_step2(step1_output)

        if '3' in executable_steps:
            step2_output = step_outputs.get(2) or INTERMEDIATE_DIR / pdf_stem / "step2_reordered_text.txt"
            step_outputs[3] = run_step3(step2_output, args.rate_limit_wait, args.model_name, args.retry_step3, args.debug)

        if '3b' in executable_steps:
            step2_output = step_outputs.get(2) or INTERMEDIATE_DIR / pdf_stem / "step2_reordered_text.txt"
            step_outputs['3b'] = run_step3b(step2_output)

        if '4' in executable_steps:
            step3_output = step_outputs.get(3) or INTERMEDIATE_DIR / pdf_stem / "step3_problem_chunks.json"
            step_outputs[4] = run_step4(
                step3_output, args.model_name, args.rate_limit_wait, args.batch_size, args.max_batches, args.retry_step4
            )
            if step_outputs.get(4):
                 exam_intermediate_files[exam_id]["step4_outputs"].append(step_outputs[4])
        
        if '4b' in executable_steps:
            step3b_output = step_outputs.get('3b') or INTERMEDIATE_DIR / pdf_stem / "step3b_consecutive_chunks.json"
            step_outputs['4b'] = run_step4b(
                step3b_output, args.model_name, args.rate_limit_wait, args.retry_step4b, args.debug
            )
            if step_outputs.get('4b'):
                exam_intermediate_files[exam_id]["step4b_outputs"].append(step_outputs['4b'])
        
        print("-" * 30)

    # --- 後続ステップの実行 / Execute Subsequent Steps ---
    if '5a' in target_steps or '5b' in target_steps:
        print("--- Running Post-processing Steps ---")
        for exam_id, files in exam_intermediate_files.items():
            print(f"Post-processing for exam: {exam_id}")
            
            # --- Step 5a: 正答値表の解析 / Parse Answer Key Table ---
            if '5a' in target_steps:
                # 実行時に生成されたパス、または中間ディレクトリのデフォルトパス
                # Path generated at runtime, or the default path in the intermediate directory
                answer_key_extraction_path = files.get("answer_key_extraction_output") \
                    or INTERMEDIATE_DIR / f"{exam_id}seitou" / "step1_raw_extraction.json"
                
                if answer_key_extraction_path and answer_key_extraction_path.exists():
                    parsed_answer_key_path = run_step5a(answer_key_extraction_path, args.model_name, args.rate_limit_wait, args.retry_step5a)
                    if parsed_answer_key_path:
                        files["parsed_answer_key_output"] = parsed_answer_key_path
                else:
                    print(f"  [Step 5a] Skipped for {exam_id}: No answer key extraction file found.")

            # --- Step 5b: 正解情報の統合 / Integrate Answer Information ---
            if '5b' in target_steps:
                # 5aで生成されたパス、または中間ディレクトリのデフォルトパスを探す
                answer_key_pdf_stem = f"{exam_id}seitou"
                final_parsed_answer_key_path = files.get("parsed_answer_key_output") \
                    or INTERMEDIATE_DIR / answer_key_pdf_stem / "step5a_parsed_answer_key.json"

                # Step4, 4b, 4c, 4dの出力パスを収集 (キャッシュがなければ探索)
                step4_outputs = files.get("step4_outputs", [])
                if not step4_outputs:
                    for p in INTERMEDIATE_DIR.glob(f"{exam_id}*/step4_structured_problems.json"):
                        step4_outputs.append(p)
                
                step4b_outputs = files.get("step4b_outputs", [])
                if not step4b_outputs:
                     for p in INTERMEDIATE_DIR.glob(f"{exam_id}*/step4b_structured_consecutive.json"):
                        step4b_outputs.append(p)

                image_mapping_paths = files.get("image_mapping_outputs", [])
                if not image_mapping_paths:
                    for p in INTERMEDIATE_DIR.glob(f"{exam_id}*/step4c_image_mapping.json"):
                        image_mapping_paths.append(p)
                    for p in INTERMEDIATE_DIR.glob(f"{exam_id}*/step4d_consecutive_image_mapping.json"):
                        image_mapping_paths.append(p)

                run_step5b(exam_id, step4_outputs, step4b_outputs, final_parsed_answer_key_path, image_mapping_paths)

            # --- Step 5.5: 集計情報の作成 / Create Summary Information ---
            if '5.5' in target_steps:
                integrated_json_path = INTERMEDIATE_DIR / exam_id / "step5b_integrated.json"
                run_step5_5(integrated_json_path)

            # --- Step 6: 最終生成 / Final Generation ---
            if '6' in target_steps:
                integrated_json_path = INTERMEDIATE_DIR / exam_id / "step5b_integrated.json"
                run_step6(integrated_json_path)

            print("-" * 30)

    if '7' in target_steps:
        print("--- Running Step 7: Solve Problems ---")
        run_step7(args)
        print("-" * 30)

    if '8' in target_steps:
        print("--- Running Step 8: Analyze Difficulty ---")
        run_step8(args)
        print("-" * 30)

    print("All specified tasks finished.")

if __name__ == "__main__":
    main()
