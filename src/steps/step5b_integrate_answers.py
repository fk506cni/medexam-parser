from pathlib import Path
import json

def integrate_answers(structured_problems_path: Path, parsed_answer_key_path: Path, intermediate_dir: Path):
    """
    正答値表の情報を構造化された問題データに統合する。

    Args:
        structured_problems_path (Path): Step 4で生成された構造化問題JSONファイルのパス。
        answer_key_extraction_path (Path): Step 1で正答値表PDFから抽出された生データJSONのパス。
        intermediate_dir (Path): 中間ファイルを保存するディレクトリ。

    Returns:
        Path: 統合後のデータが保存されたJSONファイルのパス。
    """
    print(f"  [Step 5] Integrating answers from {answer_key_extraction_path.name} into {structured_problems_path.name}")

    # Step4の出力を読み込む
    try:
        with open(structured_problems_path, 'r', encoding='utf-8') as f:
            problems = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"  [Step 5] Error reading structured problems file: {e}")
        return None

    # 正答値表の抽出データを読み込む (実際のパース処理は後ほど実装)
    try:
        with open(answer_key_extraction_path, 'r', encoding='utf-8') as f:
            answer_data = json.load(f)
        # ここでanswer_dataをパースして、問題ごとの正解をマッピングするロジックが必要
        print(f"  [Step 5] Successfully loaded answer key data.")

    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"  [Step 5] Error reading answer key extraction file: {e}")
        return None

    # TODO: 正解情報を問題データに結合するロジックをここに実装
    # 現時点では、入力された問題データをそのまま出力する
    
    # 出力パスを生成
    output_dir = intermediate_dir / structured_problems_path.parent.name
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "step5_integrated_answers.json"
    
    # 統合後のデータを書き出す
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(problems, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"  [Step 5] Error writing output file: {e}")
        return None
        
    return output_path
