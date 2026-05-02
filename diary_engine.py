"""
diary_engine.py
─────────────────────────────────────────────
プロジェクト #5: 架空の街・歴史 AI旅日記
Step 2: 旅日記テキスト + 画像プロンプト 自動生成エンジン

使い方:
    python diary_engine.py
    python diary_engine.py --world world_bible.yaml
    python diary_engine.py --world world_bible.yaml --date 2024-03-15

出力:
    output/diary/YYYY-MM-DD.json
"""

import os
import sys
import json
import random
import argparse
from pathlib import Path
from datetime import datetime, date

import anthropic
import yaml
from dotenv import load_dotenv

load_dotenv()

MODEL      = "claude-opus-4-5"
OUTPUT_DIR = Path("output/diary")


def load_world_bible(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def pick_todays_location(world: dict, target_date: date) -> dict:
    regions = world["world"]["geography"]["regions"]
    all_locations = []
    for region in regions:
        for loc in region.get("locations", []):
            all_locations.append({
                **loc,
                "region_name": region["name"],
                "region_climate": region["climate"],
                "region_specialty": region["specialty"],
            })
    seed = int(target_date.strftime("%Y%m%d"))
    random.seed(seed)
    return random.choice(all_locations)


def pick_todays_food(world: dict, target_date: date) -> dict:
    foods = world["world"]["culture"]["signature_foods"]
    seed = int(target_date.strftime("%Y%m%d")) + 1
    random.seed(seed)
    return random.choice(foods)


def get_current_festival(world: dict, target_date: date):
    festivals = world["world"]["culture"]["festivals"]
    total_months = world["world"]["calendar"]["months"]
    normalized_month = ((target_date.month - 1) % total_months) + 1
    for festival in festivals:
        if festival.get("month") == normalized_month:
            return festival
    return None


def build_diary_prompt(world: dict, location: dict, food: dict,
                        festival, target_date: date) -> str:
    w        = world["world"]
    narrator = w["narrator"]
    culture  = w["culture"]
    calendar = w["calendar"]

    month_idx      = (target_date.month - 1) % calendar["months"]
    fictional_date = (
        f"{calendar['month_names'][month_idx]} {target_date.day}日"
        f"・{w['era']}"
    )

    festival_info = ""
    if festival:
        festival_info = f"""
【今月の祭り】
祭り名: {festival['name']}
説明: {festival['description']}
→ 祭りの雰囲気や準備の様子を日記に自然に織り込んでください。
"""

    loc_name    = location['name']
    region_name = location['region_name']

    prompt = f"""
あなたは架空世界「{w['name']}」を旅するナレーター「{narrator['name']}」です。

【ナレーター設定】
経歴: {narrator['background']}
性格: {narrator['personality']}
旅の目的: {narrator['goal']}
文体指示: {narrator['writing_style']}
口癖: {narrator['catchphrase']}

【世界設定】
時代: {w['era']}
通貨: {culture['currency']}
挨拶: {culture['greeting']}
食文化: {culture['food_culture']}

【今日の架空日付】
{fictional_date}

【今日訪れた場所】
場所名: {loc_name}
種類: {location['type']}
地域: {region_name}（{location['region_climate']}）
説明: {location['description']}
雰囲気: {location['visual_mood']}
訪問時間帯: {location['best_time']}

【今日食べたもの】
料理名: {food['name']}
説明: {food['description']}
見た目: {food['visual_mood']}

{festival_info}

以下のJSON形式で厳密に出力してください。
JSONのみを出力し、前後に説明文やコードブロック記号を含めないこと。

{{
  "diary": {{
    "date_fictional": "{fictional_date}",
    "location_name": "{loc_name}",
    "region_name": "{region_name}",
    "text_jp": "日本語の旅日記本文（300〜400字）。場所の匂い・音・手触りを描写。地元の人との会話を1つ入れる。最後に一文、今日の問いを入れる。",
    "text_en": "English version of the diary (150-200 words). Same content, natural translation. End with a question.",
    "caption_x": "X用キャプション。日本語140字以内。ハッシュタグなし。旅情感のある一文で終わる。",
    "caption_instagram": "Instagram用キャプション。日本語200字以内。改行を使って読みやすく。絵文字は使わない。",
    "image_prompts": [
      {{
        "scene": "メインの風景",
        "prompt_en": "landscape scene of {loc_name} in {region_name}, {location['visual_mood']}, fantasy world, detailed illustration, cinematic lighting, concept art style, highly detailed",
        "negative_prompt": "low quality, blurry, modern, realistic photo, text, watermark"
      }},
      {{
        "scene": "料理・食事",
        "prompt_en": "fantasy food illustration of {food['name']}, {food['visual_mood']}, detailed, warm lighting, top-down view, artbook style",
        "negative_prompt": "low quality, blurry, modern, text, watermark"
      }},
      {{
        "scene": "人物・生活感",
        "prompt_en": "fantasy traveler in {loc_name}, locals going about daily life, {location['visual_mood']}, detailed illustration, storybook style",
        "negative_prompt": "low quality, blurry, modern, text, watermark, nsfw"
      }}
    ],
    "hashtags_jp": ["#架空旅日記", "#ファンタジー旅行", "#世界観"],
    "hashtags_en": ["#FantasyTravel", "#WorldBuilding", "#ImaginaryWorld", "#FictionalDiary"]
  }}
}}
"""
    return prompt


def generate_diary(client: anthropic.Anthropic, prompt: str) -> dict:
    print("  ✍️  日記テキストを生成中...")
    message = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = message.content[0].text.strip()
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"❌ JSON解析エラー: {e}")
        print("--- RAW出力 (先頭500字) ---")
        print(raw[:500])
        sys.exit(1)


def save_diary(data: dict, target_date: date, location: dict, food: dict) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output = {
        "_meta": {
            "generated_at": datetime.now().isoformat(),
            "target_date": target_date.isoformat(),
            "location_id": location.get("id"),
            "food_name": food["name"],
        },
        **data
    }
    out_path = OUTPUT_DIR / f"{target_date.isoformat()}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    return out_path


def print_summary(data: dict, out_path: Path):
    diary = data.get("diary", {})
    print("\n" + "="*55)
    print("📖 旅日記 生成完了!")
    print("="*55)
    print(f"  日付   : {diary.get('date_fictional', '?')}")
    print(f"  訪問地 : {diary.get('location_name', '?')}")
    print(f"  地域   : {diary.get('region_name', '?')}")
    print()
    print("【日記本文（日本語）】")
    text = diary.get("text_jp", "")
    for i in range(0, len(text), 44):
        print(f"  {text[i:i+44]}")
    print()
    print("【X用キャプション】")
    print(f"  {diary.get('caption_x', '')}")
    print()
    print("【画像プロンプト 1枚目】")
    prompts = diary.get("image_prompts", [])
    if prompts:
        print(f"  {prompts[0].get('prompt_en', '')}")
    print("="*55)
    print(f"\n💾 保存先: {out_path}")


def main():
    parser = argparse.ArgumentParser(description="旅日記生成エンジン")
    parser.add_argument("--world", default="world_bible.yaml")
    parser.add_argument("--date",  default=None, help="YYYY-MM-DD形式（省略時は今日）")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ 環境変数 ANTHROPIC_API_KEY が設定されていません")
        sys.exit(1)

    target_date = date.fromisoformat(args.date) if args.date else date.today()

    print(f"\n🗺️  AI旅日記エンジン起動")
    print(f"   対象日付: {target_date.isoformat()}")
    print(f"   World Bible: {args.world}\n")

    if not Path(args.world).exists():
        print(f"❌ World Bibleが見つかりません: {args.world}")
        print("   先に generate_world.py を実行してください")
        sys.exit(1)

    world = load_world_bible(args.world)
    print(f"  ✅ 世界「{world['world']['name']}」を読み込みました")

    location = pick_todays_location(world, target_date)
    food     = pick_todays_food(world, target_date)
    festival = get_current_festival(world, target_date)

    print(f"  📍 今日の訪問地: {location['name']} ({location['region_name']})")
    print(f"  🍽️  今日の料理 : {food['name']}")
    if festival:
        print(f"  🎉 今月の祭り : {festival['name']}")

    prompt     = build_diary_prompt(world, location, food, festival, target_date)
    client     = anthropic.Anthropic(api_key=api_key)
    diary_data = generate_diary(client, prompt)
    out_path   = save_diary(diary_data, target_date, location, food)

    print_summary(diary_data, out_path)
    print(f"\n✅ 次のステップ: image_engine.py で画像を生成しましょう!")
    print(f"   python image_engine.py --diary {out_path}")


if __name__ == "__main__":
    main()