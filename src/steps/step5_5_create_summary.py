import json
from pathlib import Path
from collections import Counter

def create_summary(integrated_json_path: Path, output_summary_path: Path):
    """
    統合済みJSONファイルを読み込み、新しいデータ構造（一問一答・連続問題）に対応した
    詳細な統計情報を集計してJSONファイルとして出力する。

    Loads an integrated JSON file, supporting the new data structure (single and consecutive questions),
    aggregates detailed statistical information, and outputs it as a JSON file.

    Args:
        integrated_json_path (Path): Step 5bで生成された統合済みJSONファイルのパス。
        output_summary_path (Path): 出力するサマリーJSONファイルのパス。
    """
    if not integrated_json_path.exists():
        print(f"Error: Integrated JSON file not found at {integrated_json_path}")
        return

    with open(integrated_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    total_questions = 0
    questions_with_images = 0
    total_images = 0
    question_type_counts = Counter()
    group_counts = Counter()
    unmatched_questions = []
    
    # problem_formatごとの問題ブロック数を集計
    # Count the number of problem blocks for each problem_format
    problem_format_counts = Counter(item.get('problem_format', 'unknown') for item in data)

    for item in data:
        problem_format = item.get('problem_format')

        if problem_format == 'single':
            problem = item.get('problem', {})
            if not problem: continue

            # 総設問数をカウント
            # Count the total number of sub-questions
            total_questions += 1
            
            images = problem.get('images', [])
            if images:
                questions_with_images += 1
                total_images += len(images)
            
            question_type_counts[problem.get('question_type', 'unknown')] += 1
            
            join_key = problem.get('join_key', 'unknown-')
            group = join_key.split('-')[0]
            group_counts[group] += 1
            
            if 'answer' not in problem or problem.get('answer') is None:
                unmatched_questions.append(problem.get('id', 'unknown_id'))

        elif problem_format == 'consecutive':
            sub_questions = item.get('sub_questions', [])
            # 総設問数をカウント
            # Count the total number of sub-questions
            total_questions += len(sub_questions)

            # 症例提示文の画像を処理
            # Process images for the case presentation
            case_presentation = item.get('case_presentation', {})
            case_images = case_presentation.get('images', [])
            has_case_images = len(case_images) > 0
            if has_case_images:
                total_images += len(case_images)

            # 各設問を処理
            # Process each sub-question
            for sub_q in sub_questions:
                # 設問または症例提示文に画像があれば「画像あり問題」としてカウント
                # Count as a question with images if the sub-question or case presentation has images
                sub_q_images = sub_q.get('images', [])
                if has_case_images or len(sub_q_images) > 0:
                    questions_with_images += 1

                total_images += len(sub_q_images)
                
                question_type_counts[sub_q.get('question_type', 'unknown')] += 1
                
                join_key = sub_q.get('join_key', 'unknown-')
                group = join_key.split('-')[0]
                group_counts[group] += 1

                if 'answer' not in sub_q or sub_q.get('answer') is None:
                    unmatched_questions.append(sub_q.get('id', 'unknown_id'))
        else:
            # 予期しないフォーマットの警告
            # Warning for unexpected formats
            print(f"Warning: Unknown problem_format found: {problem_format} for item ID {item.get('id')}")


    # --- 正解連携エラーの集計 (外部ファイル) ---
    # --- Aggregation of Answer Linkage Errors (External File) ---
    unmatched_answers = []
    unmatched_answers_path = integrated_json_path.parent / "step5b_unmatched_answers.json"
    if unmatched_answers_path.exists():
        with open(unmatched_answers_path, 'r', encoding='utf-8') as f:
            # このファイルは単なる文字列のリストなので、そのまま読み込む
            # This file is a simple list of strings, so load it directly
            unmatched_answers = json.load(f)

    # --- サマリー作成 ---
    # --- Create Summary ---
    summary = {
        "problem_format_counts": dict(problem_format_counts),
        "total_questions": total_questions,
        "questions_with_images": questions_with_images,
        "total_images": total_images,
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