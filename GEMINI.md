# GEMINI.md - 開発と思考の記録

このファイルは、Geminiとの対話を通じてこのプロジェクトがどのように開発されたかを記録するものです。

## 2025-08-03

### 初期セットアップとステップ実行の柔軟性確保

1.  **プロジェクトの開始**: `README.md`を読み込み、プロジェクトの全体像を把握した。
2.  **モジュール化の提案**: 当初、`main.py`に全ての処理を記述する案を提示したが、ユーザーからのフィードバックを受け、各処理ステップを個別のPythonファイル (`src/steps/step*.py`) に分割する方針に変更した。これにより、コードの可読性とメンテナンス性が向上した。
3.  **Step 1: 生データ抽出**: `src/steps/step1_extract.py` を作成。`PyMuPDF`ライブラリを使用し、PDFからテキストと画像の座標情報を抽出する機能を実装した。
    *   **遭遇した問題**: `TypeError: Object of type bytes is not JSON serializable`
    *   **原因**: `PyMuPDF`が抽出したデータに画像のバイナリデータが含まれており、それがJSON化できなかった。
    *   **解決策**: Step1の責務はあくまで「構造情報の抽出」であると再定義し、JSONに保存する前に画像のバイナリデータを意図的に削除する処理を追加して解決した。
4.  **Step 2: テキスト順序再構成**: `src/steps/step2_reorder.py` を作成。Step1で抽出したテキストブロックの座標情報を基に、2段組レイアウトなどを自然な読順に並べ替える機能を実装した。
5.  **独立したステップ実行機能の実装**:
    *   **課題**: 当初は`docker-compose up`で全工程を実行する想定だったが、開発やデバッグのためには各ステップを個別に実行したいという要望があった。
    *   **解決策**: `main.py`にPythonの`argparse`ライブラリを導入。`--steps`や`--files`といったコマンドライン引数を追加し、実行するステップや対象ファイルを柔軟に指定できるようにした。
    *   **実行コマンドの変更**: `docker-compose up`ではなく、引数を渡しやすく、かつ実行後にコンテナが自動削除される `docker-compose run --rm` を使用する方式に変更した。これにより、試行錯誤が容易になった。

### 現在の実行コマンド

*   **Dockerイメージのビルド:**
    ```bash
    docker-compose build
    ```
*   **特定のステップの実行 (例: Step 1):**
    ```bash
    docker-compose run --rm parser python src/main.py --steps 1
    ```
*   **特定のファイルに対して複数ステップを実行 (例: Step 1, 2):**
    ```bash
    docker-compose run --rm parser python src/main.py --steps 1 2 --files tp240424-01a_01.pdf
    ```
