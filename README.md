# **medexam-parser: 医師国家試験PDFデータ化プロジェクト**

## **はじめに**

このプロジェクトは、厚生労働省が公開している医師国家試験の問題PDFを解析し、機械可読性の高いJSON形式のデータセットと、問題に付随する画像を抽出することを目的としています。生成されたデータは、学習アプリ、統計分析、研究など、様々な用途での活用が期待されます。

## **ライセンス**

このリポジトリに含まれるソースコードは [GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0.html) のもとで公開されています。

【重要】ライセンスの適用範囲について  
本ライセンスは、このリポジトリに含まれるソースコードおよび関連するドキュメントのみに適用されます。  
利用者がinput/ディレクトリに配置する元のPDFファイル、および本ツールによって生成される**JSONデータや画像ファイル（output/ディレクトリ内の成果物）**は、GPL v3.0の適用範囲外です。これらの著作権は元の権利者に帰属します。成果物の利用にあたっては、元のPDFの利用規約や著作権法を遵守してください。

## **想定される技術スタック**

* **プログラミング言語:** Python 3.9+  
* **実行環境:** Docker, Docker Compose  
* **主要ライブラリ:**  
  * PyMuPDF (fitz): PDFからのテキスト、画像、座標情報の抽出  
  * Pillow: 画像処理、WebP形式への変換  
  * python-dotenv: 環境変数の管理  
  * LLM API Client (e.g., google-generativeai): LLMとの連携  
* **データフォーマット:** JSON, WebP

## **概要**

medexam-parserは、指定された年度の医師国家試験問題PDF（問題冊子、別冊、正答値表）をインプットとして受け取ります。PythonスクリプトがこれらのPDFを解析し、問題文、選択肢、画像、正解といった情報を構造化されたデータに変換します。

**主な特徴:**

* **Dockerによる環境構築:** 実行環境の違いによる問題をなくし、誰でも簡単に実行できます。
* **構造化データ出力:** 全ての問題は、後続処理で扱いやすい統一されたJSON形式で出力されます。
* **画像抽出と最適化:** 問題に関連する画像は自動で抽出され、Webで扱いやすいWebP形式に変換・保存されます。
* **ルールベースとLLMの併用:** 画像と問題の紐付けはルールベースで高速・高精度に処理し、複雑なレイアウトの解釈や構造化にはLLM（大規模言語モデル）を利用します。
* **ステップごとの中間ファイル:** 開発やデバッグを容易にするため、処理の各段階で中間ファイルを出力します。

## **プロジェクトファイル構成**

```
.
├── docker-compose.yml     # Dockerコンテナの起動設定  
├── Dockerfile             # Dockerコンテナの設計図  
├── requirements.txt       # Pythonの依存ライブラリ  
├── .env.example           # 環境変数設定のテンプレート  
├── src/  
│   └── main.py            # メインの処理スクリプト  
│   └── steps/             # 各処理ステップのスクリプト
│
├── input/                 # ここに処理対象のPDFを配置する  
│   ├── tp240424-01a_01.pdf
│   └── ...  
│  
├── output/                # 処理結果がここに生成される  
│   ├── json/  
│   │   └── tp240424-01.json  
│   └── images/
│       ├── tp240424-01-A-15-A.webp
│       └── ...  
│  
└── intermediate/          # 各処理ステップの中間ファイルがここに保存される  
    └── tp240424-01a_01/
        ├── step1_raw_extraction.json  
        └── ...
```

## **処理フロー**

データ生成は以下のフローで行われます。Step 4c（画像マッピング）はルールベースで実行され、問題の分割（Step 3）、構造化（Step 4）、正答値表の解析（Step 5a）はLLMを活用します。

```mermaid
graph TD
    A["1. PDF配置"] --> B("2. ファイル名解析");
    B --> C{"Step 1: 生データ抽出"};
    C --> D{"Step 2: テキスト順序再構成"};
    D --> E{"Step 3: 問題チャンク分割 (LLM)"};
    E --> F{"Step 4: 構造化 (LLM)"};
    
    subgraph "画像PDF処理"
        direction LR
        C_IMG["Step 1: 生データ抽出 (画像PDF)"]
    end

    subgraph "正答値表PDF処理"
        direction LR
        C_ANS["Step 1: 生データ抽出 (正答値表PDF)"]
    end

    C --> C_IMG;
    C --> C_ANS;

    C_IMG --> G{"Step 4c: 画像マッピング (ルールベース)"};
    C_ANS --> J_A("Step 5a: 正答値表解析 (LLM)");

    F --> J_B("Step 5b: 正解・画像情報統合");
    G --> J_B;
    J_A --> J_B;
    
    J_B --> K{"Step 5.5: 集計情報出力"};
    K --> L{"Step 6: 最終生成"};
    L --> M["JSONファイル出力"];
    L --> N["画像ファイル出力"];

    M --> O{ "Step 7: LLMによる問題解答 (任意)" };
    N --> O;
    O --> P[ "解答結果JSONL出力" ];

```

## **実装ステップと現状**

* [x] **Step 1: Raw Extraction (生データ抽出)**: PDFからテキスト、画像、およびそれらの座標情報を抽出し、中間ファイルとして保存する。画像はWebP形式でロスレス圧縮して保存される。**画像ブロックには、ページ内で最も近いテキストブロックの内容 (`associated_text`) を関連付けて保存する。**
* [x] **Step 2: Text Reordering (テキスト順序再構成)**: 2段組レイアウトを解析し、テキストを正しい順序に並べ替える。
* [x] **Step 3: Problem Chunking (問題チャンク分割)**: LLMを利用して、テキストを問題ごとに分割する。
* [x] **Step 4: Structure Parsing (構造化)**: LLMを利用し、各問題チャンクを問題文、選択肢などを持つ構造化JSONに変換する。
* [x] **Step 4c: Image Mapping (画像マッピング)**: 別冊画像PDFから抽出された`associated_text`を利用し、**ルールベースで**問題（`join_key`）と画像ファイル名の対応関係をマッピングする。
* [x] **Step 5a: Answer Key Parsing (正答値表解析)**: LLMを利用し、正答値表PDFから問題番号と正解のペアを抽出する。
* [x] **Step 5b: Integration (正解・画像情報統合)**: Step 4, 4c, 5a の結果を統合し、問題に正解と画像情報（画像IDとパス）を付与する。
* [x] **Step 5.5: Summary Output (集計情報出力)**: 各PDFファイルごとの問題数、総画像数、問題タイプの内訳などの統計情報を中間ファイルとして出力する。
* [x] **Step 6: Finalization (最終生成)**: 全てのデータを統合し、最終的なJSONと画像ファイルを出力する。JSON内の画像パスを更新し、中間ディレクトリの画像を最終出力ディレクトリに整理・リネームする。
* [x] **Step 7: Problem Solving (LLMによる問題解答)**: (任意実行) Step 6で生成されたJSONと画像をLLMに提示し、問題を解かせる。解答、根拠、自信度、関連領域をJSONL形式で出力する。

## **実行手順**

#### **1. リポジトリのクローン**

```bash
git clone https://github.com/your-username/medexam-parser.git
cd medexam-parser
```

#### **2. 環境変数の設定**

LLMを利用するステップ（3, 4, 5a）のためにAPIキーを設定します。`.env.example`をコピーして`.env`ファイルを作成してください。

```bash
cp .env.example .env
```

その後、`.env`ファイルを開き、お使いのLLMのAPIキーを記述します。

```env
# 例: Google Gemini API Key
GOOGLE_API_KEY="your_api_key_here"
```

#### **3. 入力PDFの配置**

処理したい年度の医師国家試験PDF一式を`input/`ディレクトリに配置します。

*   **命名規則の重要性:** スクリプトはファイル名に基づいて処理内容を自動で判断します。
    *   **問題文PDF:** `..._01.pdf` で終わるファイル (例: `tp240424-01a_01.pdf`)
    *   **画像PDF:** `..._02.pdf` で終わるファイル (例: `tp240424-01a_02.pdf`)
    *   **正答値表PDF:** `...seitou.pdf` を含むファイル (例: `tp240424-01seitou.pdf`)

#### **4. Dockerコンテナのビルドと起動**

`docker-compose.yml`に記載されている`version`属性は古い形式のため、警告が表示される場合は削除してください。

```bash
# Dockerイメージをビルド
docker-compose build

# 解析処理の実行（コンテナ起動）
docker-compose run --rm parser python src/main.py [引数...]
```

#### **5. 解析の実行**

`docker-compose run --rm parser python src/main.py` コマンドで解析処理を実行します。

**主要なコマンドライン引数:**

| 引数 | 説明 | デフォルト値 |
| :--- | :--- | :--- |
| `--steps [数値...]` | 実行するステップ番号をスペース区切りで指定します。`5a`, `5b`, `5.5` のように指定可能です。 | 全ステップ（Step 7除く） |
| `--files [ファイル名...]` | 処理対象のPDFファイルをスペース区切りで指定します。 | `input`内の全PDF |
| `--model-name [モデル名]` | Step 3, 4, 5a, 7で使用するLLMモデル名を指定します。 | `gemini-1.5-flash` |
| `--rate-limit-wait [秒数]`| LLM API呼び出し間の待機時間（秒）を指定します。 | `10.0` |
| `--batch-size [数値]` | Step 4で一度に処理する問題数を指定します。 | `5` |
| `--max-batches [数値]` | Step 4で処理する最大バッチ数を指定します（デバッグ用）。`0`の場合は全バッチを処理します。 | `0` |
| `--retry-step3 [回数]` | Step 3 のLLM API呼び出しリトライ回数。 | `3` |
| `--retry-step4 [回数]` | Step 4 のLLM API呼び出しリトライ回数。 | `3` |
| `--retry-step5a [回数]`| Step 5a のLLM API呼び出しリトライ回数。 | `3` |
| `--retry-step7 [回数]`| Step 7 のLLM API呼び出しリトライ回数。 | `3` |
| `--num-runs [回数]`| Step 7で同じ問題を解く回数を指定します。再現性確認用。 | `1` |
| `--debug` | デバッグモードを有効にし、処理の詳細ログを出力します。 | `False` |

**基本的な実行コマンド:**

```bash
# input内の全PDFを対象に、データ化の全ステップ（1～6）を実行する（推奨）
docker-compose run --rm parser python src/main.py
```

**特定のファイルやステップを指定する実行例:**

```bash
# 特定のファイル群に対して、全ステップを実行する
docker-compose run --rm parser python src/main.py \
    --files tp240424-01a_01.pdf tp240424-01a_02.pdf tp240424-01seitou.pdf

# Step1, 4c, 5b のみ実行し、画像マッピングと統合の動作を確認する
docker-compose run --rm parser python src/main.py \
    --steps 1 4c 5b \
    --files tp240424-01a_01.pdf tp240424-01a_02.pdf tp240424-01seitou.pdf

# Step 7 のみ実行し、生成済みのJSONを使ってLLMに問題を解かせる
docker-compose run --rm parser python src/main.py --steps 7

```

処理が完了すると、`intermediate/` ディレクトリに各ステップの中間成果物が、`output/` ディリクトリに最終成果物が生成されます。Step 7を実行した場合は、`output/step7_solved/`に解答結果が出力されます。

## **生成される産物の例**

#### **JSONデータ (`output/json/{exam_id}.json`)**

```

**画像を含む選択式問題の例:**

```json
{
  "id": "tp240424-01a_01-15",
  "join_key": "A-15",
  "question_type": "multiple_choice",
  "text": "（問題文）",
  "images": [
    {
      "id": "A",
      "path": "tp240424-01-A-15-A.webp"
    }
  ],
  "choices": [
    { "id": "a", "text": "選択肢1" },
    { "id": "b", "text": "選択肢2" }
  ],
  "answer": {
    "choices": ["a"]
  }
}
```

#### **画像データ (`output/images/`)**

* `tp240424-01-A-15-A.webp` (試験ID `tp240424-01`, `join_key` `A-15` の画像 `A`)

#### **Step7 解答結果データ (`output/step7_solved/{exam_id}.jsonl`)**

Step 7を実行した場合、各問題に対するLLMの解答がJSONL形式で出力されます。

```json
{
  "exam_id": "tp240424-01",
  "question_id": "tp240424-01a_01-15",
  "run_index": 1,
  "timestamp": "2023-10-27T10:00:00.123456",
  "llm_response": {
    "answer": "a",
    "reason": "根拠となる医学的知識や、問題文からの解釈など。",
    "image_findings": "胸部X線写真では、右肺上葉に空洞を伴う腫瘤影を認める。",
    "confidence": "95%~",
    "domains": ["心臟・脈管疾患", "診察"]
  }
}
```

## **今後の課題・展望**

* **対応年度の拡大:** 過去の年度の試験問題PDFにも対応できるよう、パーサーの堅牢性を向上させる。
* **Web UIの開発:** PDFをアップロードし、ブラウザ上で結果を確認・編集できるインターフェースを構築する。
* **精度評価:** LLMによる解析結果の精度を定量的に評価する仕組みを導入する。
* **パフォーマンス最適化:** 大量のPDFを高速に処理するための並列処理やキャッシュ機構を検討する。

## **貢献の方法 (Contributing)**

バグ報告、機能追加の提案、プルリクエストはGitHubのIssuesからお願いします。

```