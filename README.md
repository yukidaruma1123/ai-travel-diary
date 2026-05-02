# 🌍 AI旅日記 Project #5 — VSCode セットアップガイド

## フォルダ構成

```
project5/
├── .vscode/
│   ├── settings.json     ← Python環境・フォーマッター設定
│   ├── extensions.json   ← 推奨拡張機能
│   └── launch.json       ← F5実行の設定
├── .env.example          ← APIキーのテンプレート
├── .env                  ← ★自分で作成（Gitにコミットしない）
├── .gitignore
├── requirements.txt
├── generate_world.py     ← Step 1
├── diary_engine.py       ← Step 2（次回作成）
├── image_engine.py       ← Step 3（次回作成）
├── post_engine.py        ← Step 4（次回作成）
├── orchestrator.py       ← Step 5（次回作成）
├── world_bible.yaml      ← 生成された世界設定
└── output/
    ├── diary/            ← 生成された日記JSON
    └── images/           ← 生成された画像
```

---

## ✅ セットアップ手順（初回のみ）

### 1. フォルダをVSCodeで開く

```bash
code project5/
```

### 2. 推奨拡張機能をインストール

VSCodeが右下に「推奨拡張機能をインストールしますか？」と表示するので **「インストール」** をクリック。

表示されない場合:
- `Ctrl+Shift+P` → `Extensions: Show Recommended Extensions`

### 3. Python仮想環境を作る

VSCode内のターミナル（`Ctrl+@`）で:

```bash
# 仮想環境を作成
python -m venv .venv

# 有効化（Mac/Linux）
source .venv/bin/activate

# 有効化（Windows）
.venv\Scripts\activate

# パッケージをインストール
pip install -r requirements.txt
```

### 4. Pythonインタープリターを選択

- `Ctrl+Shift+P` → `Python: Select Interpreter`
- `.venv` と書かれた選択肢を選ぶ

### 5. .envファイルを作成

```bash
# テンプレートをコピー
cp .env.example .env
```

`.env` をVSCodeで開いて、`ANTHROPIC_API_KEY` にAPIキーを貼り付け。

---

## 🚀 実行方法

### 方法A: F5キー（推奨）

1. 左サイドバーの「実行とデバッグ」アイコンをクリック（または `Ctrl+Shift+D`）
2. 上部のドロップダウンから実行したいスクリプトを選択
3. `F5` を押す

### 方法B: ターミナル

```bash
# 仮想環境が有効な状態で
python generate_world.py
```

---

## 🔑 APIキーの取得

| キー | 取得先 | 必須タイミング |
|------|--------|---------------|
| `ANTHROPIC_API_KEY` | https://console.anthropic.com | **Step 1から必須** |
| `STABILITY_API_KEY` | https://platform.stability.ai | Step 3 |
| `OPENAI_API_KEY` | https://platform.openai.com | Step 3 |
| `X_API_KEY` など | https://developer.twitter.com | Step 4 |

---

## ❓ よくあるトラブル

**`ModuleNotFoundError: No module named 'anthropic'`**
→ 仮想環境が有効になっていない。ターミナルの先頭に `(.venv)` があるか確認。

**`ANTHROPIC_API_KEY が設定されていません`**
→ `.env` ファイルが存在するか、キーが正しく貼り付けられているか確認。

**F5を押しても動かない**
→ `Ctrl+Shift+P` → `Python: Select Interpreter` で `.venv` を選び直す。