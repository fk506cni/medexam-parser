import argparse
import json
import re
from pathlib import Path
import sys

# srcディレクトリをsys.pathに追加して、stepsモジュールをインポート可能にする
sys.path.append(str(Path(__file__).parent))

from steps.step1_extract import extract_raw_data
from steps.step2_reorder import reorder_text
from steps.step3_chunk import chunk_text_by_problem
from steps.step4_structure import structure_problems
from steps.step5a_parse_answer_key import parse_answer_key
from steps.step5b_integrate_answers import integrate_answers

# --- パス設定 ---
PROJECT_ROOT = Path(__file__).parent.parent
INPUT_DIR = PROJECT_ROOT / "input"
OUTPUT_DIR = PROJECT_ROOT / "output"
INTERMEDIATE_DIR = PROJECT_ROOT / "intermediate"

def setup_directories():
    """必要なディレクトリを作成する"""
    INPUT_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    INTERMEDIATE_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / "json").mkdir(exist_ok=True)
    (OUTPUT_DIR / "images").mkdir(exist_ok=True)

def get_exam_id_from_stem(pdf_stem: str) -> str:
    """ファイル名から共通の試験ID (例: tp240424-01) を抽出する"""
    # "tp240424-01a_01" -> "tp240424-01"
    match = re.match(r"(tp\d{6}-\d{2})", pdf_stem)
    if match:
        return match.group(1)
    # マッチしない場合 (例: 118a) は、そのまま返すか、エラー処理を行う
    # ここでは、ファイル名からアルファベットとそれに続く数字を除去するロジックを一旦削除し、
    # 命名規則に厳密に従うことを前提とする
    return pdf_stem

def run_step1(pdf_path: Path):
    """Step 1: PDFから生データを抽出する"""
    print(f"  [Step 1] Running Raw Extraction for {pdf_path.name}...")
    result_path = extract_raw_data(pdf_path, INTERMEDIATE_DIR)
    if result_path:
        print(f"  [Step 1] Completed. Output: {result_path}")
    else:
        print(f"  [Step 1] Failed for {pdf_path.name}.")
    return result_path

def run_step2(step1_output_path: Path):
    """Step 2: テキストの順序を再構成する"""
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

def run_step3(step2_output_path: Path, rate_limit_wait: float, model_name: str, max_retries: int):
    """Step 3: 問題ごとにテキストをチャンク化する"""
    if not step2_output_path or not step2_output_path.exists():
        print(f"  [Step 3] Skipped: Input file not found: {step2_output_path}")
        return None
    print(f"  [Step 3] Running Problem Chunking for {step2_output_path.parent.name} using {model_name}...")
    result_path = chunk_text_by_problem(
        step2_output_path=step2_output_path, 
        intermediate_dir=INTERMEDIATE_DIR, 
        rate_limit_wait=rate_limit_wait,
        model_name=model_name,
        max_retries=max_retries
    )
    if result_path:
        print(f"  [Step 3] Completed. Output: {result_path}")
    else:
        print(f"  [Step 3] Failed for {step2_output_path.parent.name}.")
    return result_path

def run_step4(step3_output_path: Path, model_name: str, rate_limit_wait: float, batch_size: int, max_batches: int, max_retries: int):
    """Step 4: 問題を構造化する"""
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

def run_step5b(exam_id: str, structured_problem_paths: list[Path], parsed_answer_key_path: Path):
    """Step 5b: 複数の問題JSONを統合し、正解情報を結合する"""
    if not structured_problem_paths:
        print(f"  [Step 5b] Skipped for {exam_id}: No structured problem files found.")
        return None
    if not parsed_answer_key_path or not parsed_answer_key_path.exists():
        print(f"  [Step 5b] Skipped for {exam_id}: Parsed answer key file not found: {parsed_answer_key_path}")
        # 解答キーがなくても、問題ファイルの統合は行う
        pass

    # 複数の問題JSONファイルを1つに統合する
    all_problems = []
    for problem_path in structured_problem_paths:
        try:
            with open(problem_path, 'r', encoding='utf-8') as f:
                problems = json.load(f)
                if isinstance(problems, list):
                    all_problems.extend(problems)
                else:
                    print(f"  [Step 5b] Warning: Expected a list in {problem_path.name}, but got {type(problems)}. Skipping.")
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"  [Step 5b] Warning: Could not read or parse {problem_path.name}: {e}")
            continue
    
    if not all_problems:
        print(f"  [Step 5b] Skipped for {exam_id}: No valid problems to process after combining files.")
        return None

    # 統合した問題リストを一時ファイルに保存
    combined_dir = INTERMEDIATE_DIR / exam_id
    combined_dir.mkdir(exist_ok=True)
    combined_path = combined_dir / "step4_structured_problems_combined.json"
    with open(combined_path, 'w', encoding='utf-8') as f:
        json.dump(all_problems, f, ensure_ascii=False, indent=2)
    print(f"  [Step 5b] Combined {len(all_problems)} problems for exam {exam_id} into {combined_path.name}")

    # 正解情報を統合
    print(f"  [Step 5b] Running Answer Integration for exam {exam_id}...")
    result_path = integrate_answers(
        structured_problems_path=combined_path,
        parsed_answer_key_path=parsed_answer_key_path,
        intermediate_dir=INTERMEDIATE_DIR
    )
    if result_path:
        print(f"  [Step 5b] Completed. Output: {result_path}")
    else:
        print(f"  [Step 5b] Failed for exam {exam_id}.")
    return result_path


def run_step5a(answer_key_extraction_path: Path, model_name: str, rate_limit_wait: float, max_retries: int):
    """Step 5a: 正答値表を解析する"""
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

def main():
    """
    コマンドライン引数に基づいて、指定されたステップとファイルで解析処理を実行する。
    """
    parser = argparse.ArgumentParser(description="医師国家試験PDFを解析し、JSONと画像を生成します。")
    parser.add_argument(
        "--steps",
        nargs='+',
        type=str, # 5a, 5bを扱えるようにstr型に変更
        default=[str(i) for i in range(1, 7)], # デフォルトは全ステップ
        help="実行するステップ番号をスペース区切りで指定します (例: 1 2 5a 5b)。"
    )
    parser.add_argument(
        "--files",
        nargs='+',
        type=str,
        help="処理対象のPDFファイル名をスペース区切りで指定します (例: 118a.pdf 118b.pdf)。指定しない場合はinputディレクトリ内の全PDFが対象です。"
    )
    parser.add_argument(
        "--rate-limit-wait",
        type=float,
        default=10.0,
        help="LLM API呼び出し間の待機時間（秒）を指定します。デフォルトは10秒です。"
    )
    parser.add_argument(
        "--model-name",
        type=str,
        default="gemini-1.5-flash",
        help="使用するLLMモデル名を指定します。"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5,
        help="Step 4でLLMに一度に送信する問題数を指定します。"
    )
    parser.add_argument(
        "--max-batches",
        type=int,
        default=0,
        help="Step 4で処理する最大のバッチ数を指定します。0の場合は全バッチを処理します。デバッグ用。"
    )
    parser.add_argument(
        "--retry-step3",
        type=int,
        default=3,
        help="Step 3のリトライ回数を指定します。"
    )
    parser.add_argument(
        "--retry-step4",
        type=int,
        default=3,
        help="Step 4のリトライ回数を指定します。"
    )
    parser.add_argument(
        "--retry-step5a",
        type=int,
        default=3,
        help="Step 5aのリトライ回数を指定します。"
    )
    args = parser.parse_args()

    setup_directories()
    
    # --- 処理対象ファイルの決定 ---
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

    # ステップの正規化
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

    # --- ステップ実行 ---
    # 試験IDごとに中間ファイルのパスを管理
    exam_intermediate_files = {}

    for pdf_path in pdf_files:
        print(f"Processing PDF: {pdf_path.name}")
        pdf_stem = pdf_path.stem
        exam_id = get_exam_id_from_stem(pdf_stem)

        if exam_id not in exam_intermediate_files:
            exam_intermediate_files[exam_id] = {"step4_outputs": [], "answer_key_extraction_output": None, "parsed_answer_key_output": None}

        # ファイル名からファイルタイプを判定
        file_type = "text"
        if pdf_path.name.endswith("_02.pdf"):
            file_type = "image"
        elif "seitou" in pdf_path.name:
            file_type = "answer"

        # 実行するステップを決定
        executable_steps = set()
        if file_type == "answer":
            if '5a' in target_steps: executable_steps.add('1') # 5aには1が必要
            executable_steps.update(target_steps.intersection({'5a'}))
        elif file_type == "image":
            # 画像PDFはStep1（画像抽出）のみ実行
            executable_steps.update(target_steps.intersection({'1'}))
        else: # text
            # テキストPDFはテキスト処理ステップを実行
            executable_steps.update(target_steps.intersection({'1', '2', '3', '4'}))


        # 各ステップの出力を管理
        step_outputs = {}

        if '1' in executable_steps:
            step_outputs[1] = run_step1(pdf_path)
            if file_type == "answer":
                exam_intermediate_files[exam_id]["answer_key_extraction_output"] = step_outputs[1]


        if '2' in executable_steps:
            step1_output = step_outputs.get(1) or INTERMEDIATE_DIR / pdf_stem / "step1_raw_extraction.json"
            step_outputs[2] = run_step2(step1_output)

        if '3' in executable_steps:
            step2_output = step_outputs.get(2) or INTERMEDIATE_DIR / pdf_stem / "step2_reordered_text.txt"
            step_outputs[3] = run_step3(step2_output, args.rate_limit_wait, args.model_name, args.retry_step3)

        if '4' in executable_steps:
            step3_output = step_outputs.get(3) or INTERMEDIATE_DIR / pdf_stem / "step3_problem_chunks.json"
            step_outputs[4] = run_step4(
                step3_output, args.model_name, args.rate_limit_wait, args.batch_size, args.max_batches, args.retry_step4
            )
            if step_outputs.get(4):
                 exam_intermediate_files[exam_id]["step4_outputs"].append(step_outputs[4])
        
        print("-" * 30)

    # --- 後続ステップの実行 ---
    if '5a' in target_steps or '5b' in target_steps:
        print("--- Running Post-processing Steps ---")
        for exam_id, files in exam_intermediate_files.items():
            print(f"Post-processing for exam: {exam_id}")
            
            # --- Step 5a: 正答値表の解析 ---
            if '5a' in target_steps:
                # 実行時に生成されたパス、または中間ディレクトリのデフォルトパス
                answer_key_extraction_path = files.get("answer_key_extraction_output") \
                    or INTERMEDIATE_DIR / f"{exam_id}seitou" / "step1_raw_extraction.json"
                
                if answer_key_extraction_path and answer_key_extraction_path.exists():
                    parsed_answer_key_path = run_step5a(answer_key_extraction_path, args.model_name, args.rate_limit_wait, args.retry_step5a)
                    if parsed_answer_key_path:
                        files["parsed_answer_key_output"] = parsed_answer_key_path
                else:
                    print(f"  [Step 5a] Skipped for {exam_id}: No answer key extraction file found.")

            # --- Step 5b: 正解情報の統合 ---
            if '5b' in target_steps:
                # 5aで生成されたパス、または中間ディレクトリのデフォルトパスを探す
                # 正答ファイル名は "{exam_id}seitou.pdf" と想定
                answer_key_pdf_stem = f"{exam_id}seitou"
                final_parsed_answer_key_path = files.get("parsed_answer_key_output") \
                    or INTERMEDIATE_DIR / answer_key_pdf_stem / "step5a_parsed_answer_key.json"

                # Step4の出力パスを収集
                step4_outputs = files.get("step4_outputs", [])
                if not step4_outputs:
                    # `tp240424-01`のようなIDにマッチする全問題PDFの中間ディレクトリを探す
                    for pdf_path in pdf_files:
                        if pdf_path.stem.startswith(exam_id) and 'seitou' not in pdf_path.stem:
                            step4_path = INTERMEDIATE_DIR / pdf_path.stem / "step4_structured_problems.json"
                            if step4_path.exists():
                                step4_outputs.append(step4_path)
                
                run_step5b(exam_id, step4_outputs, final_parsed_answer_key_path)

            print("-" * 30)


    print("All specified tasks finished.")

if __name__ == "__main__":
    main()
