import json
from pathlib import Path
from collections import Counter

def create_summary(integrated_json_path: Path, output_summary_path: Path):
    """
    統合済みJSONファイルを読み込み、詳細な統計情報を集計してJSONファイルとして出力する。

    Loads an integrated JSON file, aggregates detailed statistical information, and outputs it as a JSON file.

    Args:
        integrated_json_path (Path): Step 5bで生成された統合済みJSONファイルのパス。/ Path to the integrated JSON file generated in Step 5b.
        output_summary_path (Path): 出力するサマリーJSONファイルのパス。/ Path to the output summary JSON file.
    """
    if not integrated_json_path.exists():
        print(f"Error: Integrated JSON file not found at {integrated_json_path}")
        return

    with open(integrated_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # --- 基本集計 ---
    # --- Basic Aggregation ---
    total_questions = len(data)
    questions_with_images = sum(1 for item in data if item.get('images'))
    # 総画像数をカウント（imagesがオブジェクトのリストであることを考慮）
    # Count total images (considering images as a list of objects)
    total_images = sum(len(item.get('images', [])) for item in data)

    # --- 問題タイプ別集計 ---
    # --- Aggregation by Question Type ---
    question_type_counts = Counter(item.get('question_type', 'unknown') for item in data)

    # --- 問題グループ別集計 (join_keyのプレフィックスを利用) ---
    # --- Aggregation by Question Group (using join_key prefix) ---
    group_counts = Counter()
    for item in data:
        join_key = item.get('join_key', 'unknown-')
        group = join_key.split('-')[0]
        group_counts[group] += 1

    # --- 正解連携エラーの集計 ---
    # --- Aggregation of Answer Linkage Errors ---
    unmatched_questions = [item['id'] for item in data if 'answer' not in item or item['answer'] is None]
    
    unmatched_answers = []
    unmatched_answers_path = integrated_json_path.parent / "step5b_unmatched_answers.json"
    if unmatched_answers_path.exists():
        with open(unmatched_answers_path, 'r', encoding='utf-8') as f:
            unmatched_data = json.load(f)
            unmatched_answers = [item.get('join_key', 'unknown') for item in unmatched_data]

    # --- サマリー作成 ---
    # --- Create Summary ---
    summary = {
        "total_questions": total_questions,
        "questions_with_images": questions_with_images,
        "total_images": total_images, # 総画像数を追加
        "question_type_counts": dict(question_type_counts),
        "question_group_counts": dict(group_counts),
        "unmatched_summary": {
            "unmatched_questions_count": len(unmatched_questions),
            "unmatched_answers_count": len(unmatched_answers),
        },
        "unmatched_lists": {
            "unmatched_questions": unmatched_questions,
            "unmatched_answers": unmatched_answers,
        }
    }

    output_summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"Successfully created detailed summary file at: {output_summary_path}")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Create a detailed summary from an integrated JSON file.")
    parser.add_argument("integrated_file", type=Path, help="Path to the integrated JSON file from step5b.")
    parser.add_argument("summary_file", type=Path, help="Path to output the summary JSON file.")
    args = parser.parse_args()

    create_summary(args.integrated_file, args.summary_file)
