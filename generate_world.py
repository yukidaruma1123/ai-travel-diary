"""
generate_world.py
─────────────────────────────────────────────
プロジェクト #5: 架空の街・歴史 AI旅日記
Step 1: World Bible (世界聖典) 自動生成スクリプト

使い方:
    pip install anthropic pyyaml
    export ANTHROPIC_API_KEY="sk-ant-..."
    python generate_world.py

    # 既存のYAMLを拡張する場合
    python generate_world.py --expand --input world_bible.yaml

出力:
    world_bible.yaml  ← 世界設定マスターデータ
"""

import argparse
import anthropic
import yaml
from pathlib import Path
from datetime import datetime
import os
import sys
import json
from dotenv import load_dotenv

load_dotenv()  # .envを自動読み込み

# ──────────────────────────────────────────
# 定数
# ──────────────────────────────────────────
OUTPUT_FILE = "world_bible.yaml"
MODEL       = "claude-opus-4-5"   # 世界観生成は高品質モデルを使用


# ──────────────────────────────────────────
# プロンプト定義
# ──────────────────────────────────────────
WORLD_GENERATION_PROMPT = """
あなたは架空世界の創造主です。
以下の条件で「旅日記SNS投稿」に最適な架空世界の設定を生成してください。

【条件】
- 毎日1〜2箇所の「場所」を訪れる旅日記に使えること
- 視覚的に映える風景・食事・建物・道具が描写できること
- 和製ファンタジー / スチームパンク / 異文化融合など、独自の世界観
- SNSで「続きが気になる」と思われる謎や伝承を含むこと
- 日本語話者が親しみやすい、しかし異世界感のある設定

以下のJSON形式で厳密に出力してください。
JSONのみを出力し、前後に説明文やマークダウンのコードブロック記号を一切含めないでください。

{
  "world": {
    "name": "世界名",
    "era": "時代背景の説明",
    "calendar": {
      "months": 数値,
      "month_names": ["月名1", "月名2", ...],
      "current_month": 数値,
      "season": "現在の季節"
    },
    "geography": {
      "overview": "世界全体の地理的説明",
      "regions": [
        {
          "id": "region_id",
          "name": "地域名",
          "climate": "気候",
          "architecture": "建築様式",
          "specialty": "名産品・特産物",
          "secret": "隠された謎や伝承",
          "locations": [
            {
              "id": "location_id",
              "name": "場所名",
              "type": "場所の種類 (市場/神殿/港/路地など)",
              "description": "2〜3文での場所の説明",
              "visual_mood": "光・色・雰囲気のキーワード (画像生成に使用)",
              "best_time": "訪れるのに最適な時間帯"
            }
          ]
        }
      ]
    },
    "culture": {
      "language_flavor": "言語の雰囲気・響き",
      "currency": "通貨名と説明",
      "greeting": "現地の挨拶",
      "taboos": ["禁忌1", "禁忌2"],
      "festivals": [
        {
          "name": "祭り名",
          "month": 数値,
          "description": "祭りの説明"
        }
      ],
      "food_culture": "食文化の特徴",
      "signature_foods": [
        {
          "name": "料理名",
          "description": "料理の説明",
          "visual_mood": "見た目のキーワード"
        }
      ]
    },
    "narrator": {
      "name": "ナレーターの名前",
      "background": "経歴・設定 (2〜3文)",
      "personality": "性格・文体の特徴",
      "goal": "旅の目的",
      "writing_style": "日記の文体指示 (例: 詩的・観察眼が鋭い・少し皮肉屋)",
      "catchphrase": "口癖や決め台詞"
    },
    "lore": {
      "creation_myth": "世界の創世神話 (2〜3文)",
      "ongoing_mystery": "現在進行中の謎や事件",
      "factions": [
        {
          "name": "勢力名",
          "description": "勢力の説明",
          "symbol": "象徴するもの"
        }
      ]
    }
  }
}
"""

EXPAND_PROMPT_TEMPLATE = """
以下は既存のWorld Bibleです:

{existing_yaml}

この世界設定を拡張してください。
- 新しい地域を1つ追加
- 既存地域に場所を2〜3個追加
- 新しい料理を2〜3個追加
- 新しい祭りを1つ追加

既存の世界観・文体と矛盾しないよう注意してください。
追加分のみをJSON形式で出力してください（世界全体ではなく、差分のみ）。

{
  "new_region": { ... },
  "additional_locations": { "region_id": [ ... ] },
  "additional_foods": [ ... ],
  "additional_festivals": [ ... ]
}
"""


# ──────────────────────────────────────────
# メイン処理
# ──────────────────────────────────────────
def generate_world(client: anthropic.Anthropic) -> dict:
    """新規の世界設定を生成する"""
    print("🌍 世界設定を生成中... (30〜60秒かかります)")

    message = client.messages.create(
        model=MODEL,
        max_tokens=8096,
        messages=[
            {"role": "user", "content": WORLD_GENERATION_PROMPT}
        ]
    )

    raw = message.content[0].text.strip()

    # JSON部分だけを抽出（念のため）
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"❌ JSON解析エラー: {e}")
        print("--- 受信したRAWデータ ---")
        print(raw[:500])
        sys.exit(1)

    return data


def expand_world(client: anthropic.Anthropic, existing_yaml_path: str) -> dict:
    """既存のWorld Bibleを拡張する"""
    print(f"📖 既存のWorld Bibleを読み込み中: {existing_yaml_path}")

    with open(existing_yaml_path, "r", encoding="utf-8") as f:
        existing_yaml = f.read()

    prompt = EXPAND_PROMPT_TEMPLATE.format(existing_yaml=existing_yaml)

    print("🔧 世界設定を拡張中...")
    message = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = message.content[0].text.strip()
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        additions = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"❌ JSON解析エラー: {e}")
        sys.exit(1)

    # 既存データを読み込んでマージ
    with open(existing_yaml_path, "r", encoding="utf-8") as f:
        world_data = yaml.safe_load(f)

    world = world_data["world"]

    # 新しい地域を追加
    if "new_region" in additions:
        world["geography"]["regions"].append(additions["new_region"])
        print(f"  ✅ 新地域追加: {additions['new_region'].get('name', '?')}")

    # 既存地域に場所を追加
    if "additional_locations" in additions:
        for region_id, locs in additions["additional_locations"].items():
            for region in world["geography"]["regions"]:
                if region.get("id") == region_id:
                    region["locations"].extend(locs)
                    print(f"  ✅ 場所追加: {region['name']} に {len(locs)} 箇所")

    # 料理を追加
    if "additional_foods" in additions:
        world["culture"]["signature_foods"].extend(additions["additional_foods"])
        print(f"  ✅ 料理追加: {len(additions['additional_foods'])} 品")

    # 祭りを追加
    if "additional_festivals" in additions:
        world["culture"]["festivals"].extend(additions["additional_festivals"])
        print(f"  ✅ 祭り追加: {len(additions['additional_festivals'])} 件")

    return world_data


def add_metadata(data: dict) -> dict:
    """メタデータをWorld Bibleに付加する"""
    data["_meta"] = {
        "generated_at": datetime.now().isoformat(),
        "version": "1.0",
        "project": "AI旅日記 Project #5",
        "total_locations": sum(
            len(r.get("locations", []))
            for r in data["world"]["geography"]["regions"]
        ),
        "total_foods": len(data["world"]["culture"]["signature_foods"]),
        "total_festivals": len(data["world"]["culture"]["festivals"]),
    }
    return data


def save_yaml(data: dict, path: str):
    """YAMLとして保存する"""
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(
            data,
            f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
            indent=2,
        )
    print(f"\n💾 保存完了: {path}")


def print_summary(data: dict):
    """生成結果のサマリーを表示する"""
    world = data["world"]
    meta  = data.get("_meta", {})
    narrator = world.get("narrator", {})

    print("\n" + "="*50)
    print("🗺️  World Bible 生成完了!")
    print("="*50)
    print(f"  世界名       : {world['name']}")
    print(f"  時代         : {world['era']}")
    print(f"  ナレーター   : {narrator.get('name', '?')} — {narrator.get('goal', '?')}")
    print(f"  地域数       : {len(world['geography']['regions'])}")
    print(f"  総訪問地数   : {meta.get('total_locations', '?')}")
    print(f"  料理数       : {meta.get('total_foods', '?')}")
    print(f"  祭り数       : {meta.get('total_festivals', '?')}")
    print("="*50)

    print("\n📍 登録された訪問地一覧:")
    for region in world["geography"]["regions"]:
        print(f"\n  【{region['name']}】 ({region.get('climate', '')})")
        for loc in region.get("locations", []):
            print(f"    - {loc['name']} ({loc.get('type', '')})")


# ──────────────────────────────────────────
# エントリーポイント
# ──────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="World Bible 生成スクリプト")
    parser.add_argument("--expand", action="store_true", help="既存YAMLを拡張モードで実行")
    parser.add_argument("--input",  default=OUTPUT_FILE,  help="拡張時の入力ファイルパス")
    parser.add_argument("--output", default=OUTPUT_FILE,  help="出力ファイルパス")
    args = parser.parse_args()

    # APIキー確認
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ 環境変数 ANTHROPIC_API_KEY が設定されていません")
        print("   export ANTHROPIC_API_KEY='sk-ant-...'")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    if args.expand:
        if not Path(args.input).exists():
            print(f"❌ 入力ファイルが見つかりません: {args.input}")
            sys.exit(1)
        data = expand_world(client, args.input)
    else:
        data = generate_world(client)
        data = add_metadata(data)

    save_yaml(data, args.output)
    print_summary(data)

    print(f"\n✅ 次のステップ: diary_engine.py を実行して日記を生成しましょう!")
    print(f"   python diary_engine.py --world {args.output}")


if __name__ == "__main__":
    main()