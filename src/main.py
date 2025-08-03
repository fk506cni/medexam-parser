import argparse
from pathlib import Path
import sys

# srcディレクトリをsys.pathに追加して、stepsモジュールをインポート可能にする
sys.path.append(str(Path(__file__).parent))

from steps.step1_extract import extract_raw_data
from steps.step2_reorder import reorder_text
from steps.step3_chunk import chunk_text_by_problem

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

def run_step3(step2_output_path: Path):
    """Step 3: 問題ごとにテキストをチャンク化する"""
    if not step2_output_path or not step2_output_path.exists():
        print(f"  [Step 3] Skipped: Input file not found: {step2_output_path}")
        return None
    print(f"  [Step 3] Running Problem Chunking for {step2_output_path.parent.name}...")
    result_path = chunk_text_by_problem(step2_output_path, INTERMEDIATE_DIR)
    if result_path:
        print(f"  [Step 3] Completed. Output: {result_path}")
    else:
        print(f"  [Step 3] Failed for {step2_output_path.parent.name}.")
    return result_path

def main():
    """
    コマンドライン引数に基づいて、指定されたステップとファイルで解析処理を実行する。
    """
    parser = argparse.ArgumentParser(description="医師国家試験PDFを解析し、JSONと画像を生成します。")
    parser.add_argument(
        "--steps",
        nargs='+',
        type=int,
        default=list(range(1, 7)), # デフォルトは全ステップ
        help="実行するステップ番号をスペース区切りで指定します (例: 1 2)。"
    )
    parser.add_argument(
        "--files",
        nargs='+',
        type=str,
        help="処理対象のPDFファイル名をスペース区切りで指定します (例: 118a.pdf 118b.pdf)。指定しない場合はinputディレクトリ内の全PDFが対象です。"
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

    print("--- Processing Configuration ---")
    print(f"Target Steps: {sorted(args.steps)}")
    print(f"Target Files: {[p.name for p in pdf_files]}")
    print("-" * 30)

    # --- ステップ実行 ---
    for pdf_path in pdf_files:
        print(f"Processing PDF: {pdf_path.name}")
        pdf_stem = pdf_path.stem
        
        # 各ステップの出力を管理
        step_outputs = {}

        if 1 in args.steps:
            step_outputs[1] = run_step1(pdf_path)

        if 2 in args.steps:
            # Step 2はStep 1の出力に依存する
            step1_output = step_outputs.get(1)
            if not step1_output:
                # Step 1が実行されていない場合、中間ファイルのパスを推測
                step1_output = INTERMEDIATE_DIR / pdf_stem / "step1_raw_extraction.json"
            
            step_outputs[2] = run_step2(step1_output)

        if 3 in args.steps:
            # Step 3はStep 2の出力に依存する
            step2_output = step_outputs.get(2)
            if not step2_output:
                step2_output = INTERMEDIATE_DIR / pdf_stem / "step2_reordered_text.txt"
            step_outputs[3] = run_step3(step2_output)
        
        # (ここに後続ステップの呼び出しを追加)

        print("-" * 30)

    print("All specified tasks finished.")

if __name__ == "__main__":
    main()