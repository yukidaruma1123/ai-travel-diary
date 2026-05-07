"""
floorplan_prompt_engine.py
─────────────────────────────────────────────
架空世界の間取り図 + 外観・内観 画像プロンプト自動生成
Claude APIで毎日ランダムな架空住居の設定を生成し
DALL-E 3用プロンプトをJSONで出力する

使い方:
    python floorplan_prompt_engine.py
    python floorplan_prompt_engine.py --date 2026-05-07

出力:
    output/floorplan_diary/YYYY-MM-DD.json
"""

import os
import sys
import json
import random
import argparse
from pathlib import Path
from datetime import date, datetime

import anthropic
from dotenv import load_dotenv

load_dotenv()

OUTPUT_DIR = Path("output/floorplan_diary")
MODEL      = "claude-opus-4-5"

# ══════════════════════════════════════════
# 世界観・住居タイプのランダム素材
# ══════════════════════════════════════════

WORLD_THEMES = [
    # (テーマ名, 説明, 雰囲気キーワード)
    ("魔法文明",    "魔法と錬金術が発達した中世風世界",    "arcane, mystical, medieval, glowing runes"),
    ("深海都市",    "海底に築かれた都市文明",               "underwater, bioluminescent, pressure-sealed, coral"),
    ("空中浮遊",    "雲の上に浮かぶ島々に住む文明",         "floating island, clouds, airship, wind-worn stone"),
    ("地底文明",    "地下深くに広がる巨大な洞窟都市",       "cavern, stalagmites, underground, dim lantern light"),
    ("SF宇宙",      "宇宙植民地・軌道上居住施設",           "sci-fi, space station, zero gravity, metallic hull"),
    ("蒸気機関",    "蒸気と歯車が動力の異世界",             "steampunk, brass gears, steam pipes, Victorian"),
    ("自然融合",    "植物・木・水と一体化した有機的建築",    "organic, treehouse, living wood, moss-covered"),
    ("水晶文明",    "水晶と光を素材とした透明な建築",       "crystal, translucent, prismatic light, gem-like"),
    ("砂漠遺跡",    "古代遺跡に住み着いた砂漠の民",         "desert ruins, sandstone, carved cliff, ancient"),
    ("氷雪王国",    "永久凍土の中に掘られた氷の住居",       "ice palace, frozen, aurora, carved glacier"),
    ("ホラー屋敷",  "怨念や呪いが染み込んだ不気味な邸宅",  "haunted, gothic, dark, decayed, eerie shadows"),
    ("サイバーパンク","テクノロジーと貧困が混在する近未来",  "cyberpunk, neon, dystopian, cramped, holographic"),
    ("菌類世界",    "巨大な菌類・キノコが建材の世界",       "mushroom, fungal, spores, bioluminescent, organic"),
    ("溶岩火山",    "活火山の中に築かれた耐熱文明",         "volcanic, lava, obsidian, fire-resistant, dark rock"),
    ("時空歪み",    "物理法則が歪んだ不思議な空間",         "impossible geometry, M.C. Escher, non-Euclidean, surreal"),
]

FLOOR_SHAPES = [
    ("円形",        "perfectly circular floor plan, radial rooms like pie slices"),
    ("六角形",      "hexagonal floor plan, honeycomb-like room arrangement"),
    ("螺旋形",      "spiral floor plan, rooms arranged in a continuous spiral"),
    ("有機的変形",  "organic irregular shape, amoeba-like outline, no straight walls"),
    ("星形",        "star-shaped floor plan, pointed wing extensions"),
    ("多層塔型",    "multi-story tower cross-section, stacked circular floors"),
    ("L字変形",     "asymmetric L-shape with curved walls and irregular protrusions"),
    ("洞窟型",      "cave-carved irregular shape, natural rock walls with carved rooms"),
    ("木造樹上",    "built around and inside a massive tree, rooms in branches and trunk"),
    ("球体断面",    "cross-section of a sphere, dome-shaped rooms"),
    ("クモの巣",    "web-like radial pattern, thin corridors connecting circular nodes"),
    ("結晶型",      "crystalline geometric shape, sharp angles like a mineral formation"),
]

ROOM_TYPES_FANTASY = [
    "儀式の間", "魔法陣の部屋", "ポーション工房", "召喚の間",
    "霊廟", "夢見の間", "記憶の間", "時間の部屋",
    "無重力室", "水中居室", "炎の寝室", "風の塔",
    "腐食の実験室", "封印の間", "転移陣の間", "幻影の回廊",
    "骨の書斎", "生命樹の根元", "星観測室", "禁断の扉",
    "食事の広間", "来客の間", "主の寝室", "従者の部屋",
    "宝物庫", "武器庫", "図書室", "入口の間",
]

# ══════════════════════════════════════════
# Claude APIへのプロンプト
# ══════════════════════════════════════════

GENERATION_PROMPT = """
あなたは架空世界の建築家です。
以下の設定で「架空住居の間取り図」の画像生成プロンプトを作成してください。

【今回の設定】
世界観テーマ: {theme_name} — {theme_desc}
雰囲気キーワード: {theme_mood}
間取りの形状: {shape_name} — {shape_desc}
部屋リスト: {rooms}

【ルール】
1. DALL-E 3で生成するので英語プロンプトにすること
2. 「建築図面・間取り図・フロアプラン」スタイルで俯瞰図として描写
3. リアルな間取り図風（白背景・線画・ラベル入り）と
   ファンタジーイラスト風（色彩豊か・装飾あり）をランダムに使い分ける
4. 実在しない架空の場所であることを明確に
5. SNS映えする構図・配色を意識する

以下のJSON形式のみ出力。説明文・コードブロック不要。

{{
  "concept": {{
    "theme": "{theme_name}",
    "shape": "{shape_name}",
    "resident": "この家に住む架空のキャラクターの設定（日本語2文）",
    "story": "この間取りにまつわる短いストーリー（日本語3文）"
  }},
  "image_prompts": [
    {{
      "scene": "間取り図（俯瞰）",
      "style": "architectural_blueprint または fantasy_illustration のどちらか",
      "prompt_en": "DALL-E 3用英語プロンプト（120語以内）。建築図面または幻想的なイラストとして間取りを描写。部屋名を英語で記載。",
      "negative": "photo, realistic, 3D render, dark background"
    }},
    {{
      "scene": "外観",
      "style": "fantasy_illustration",
      "prompt_en": "DALL-E 3用英語プロンプト（100語以内）。建物の外観を描写。{theme_mood}の雰囲気を強調。",
      "negative": "floor plan, blueprint, top-down, interior"
    }},
    {{
      "scene": "メインルーム内観",
      "style": "fantasy_illustration",
      "prompt_en": "DALL-E 3用英語プロンプト（100語以内）。最も特徴的な部屋の内部を描写。住人のキャラクター性が感じられる空間。",
      "negative": "floor plan, blueprint, top-down, exterior"
    }}
  ],
  "captions": {{
    "instagram": "Instagram用日本語キャプション（200字以内・改行あり・ハッシュタグなし）",
    "x": "X用日本語キャプション（140字以内・ハッシュタグなし）"
  }},
  "hashtags": {{
    "jp": ["#架空間取り図", "#ファンタジー建築", "#異世界住宅"],
    "en": ["#FantasyFloorPlan", "#ImaginaryArchitecture", "#WorldBuilding"]
  }}
}}
"""

# ══════════════════════════════════════════
# メイン生成処理
# ══════════════════════════════════════════

def pick_daily_settings(target_date: date) -> dict:
    """日付シードでランダム設定を選択（同じ日は同じ設定）"""
    seed = int(target_date.strftime("%Y%m%d"))
    random.seed(seed)

    theme = random.choice(WORLD_THEMES)
    shape = random.choice(FLOOR_SHAPES)

    # 部屋数: 4〜8室
    n_rooms = random.randint(4, 8)
    rooms   = random.sample(ROOM_TYPES_FANTASY, n_rooms)

    return {
        "theme_name": theme[0],
        "theme_desc": theme[1],
        "theme_mood": theme[2],
        "shape_name": shape[0],
        "shape_desc": shape[1],
        "rooms":      "、".join(rooms),
    }


def generate_prompts(client: anthropic.Anthropic, settings: dict) -> dict:
    """Claude APIでプロンプトを生成"""
    print(f"  🌍 テーマ  : {settings['theme_name']} — {settings['theme_desc']}")
    print(f"  🏠 形状    : {settings['shape_name']}")
    print(f"  🚪 部屋数  : {settings['rooms']}")
    print(f"\n  ✍️  プロンプト生成中...")

    prompt = GENERATION_PROMPT.format(**settings)

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
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"❌ JSON解析エラー: {e}")
        print(raw[:300])
        sys.exit(1)


def save_output(data: dict, settings: dict, target_date: date) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output = {
        "_meta": {
            "generated_at": datetime.now().isoformat(),
            "target_date":  target_date.isoformat(),
            "settings":     settings,
        },
        **data
    }

    out_path = OUTPUT_DIR / f"{target_date.isoformat()}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    return out_path


def print_summary(data: dict, out_path: Path):
    concept = data.get("concept", {})
    prompts = data.get("image_prompts", [])

    print("\n" + "="*55)
    print("🏠 架空間取り図 生成完了!")
    print("="*55)
    print(f"  テーマ  : {concept.get('theme','?')}")
    print(f"  形状    : {concept.get('shape','?')}")
    print(f"  住人    : {concept.get('resident','?')}")
    print()
    print("【ストーリー】")
    story = concept.get("story", "")
    for i in range(0, len(story), 44):
        print(f"  {story[i:i+44]}")
    print()
    print("【間取り図プロンプト】")
    if prompts:
        p = prompts[0].get("prompt_en", "")
        print(f"  {p[:80]}...")
    print("="*55)
    print(f"\n💾 保存先: {out_path}")


# ══════════════════════════════════════════
# エントリーポイント
# ══════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="架空間取り図プロンプト生成")
    parser.add_argument("--date",  default=None, help="YYYY-MM-DD")
    parser.add_argument("--output", default=str(OUTPUT_DIR))
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY が設定されていません")
        sys.exit(1)

    target_date = date.fromisoformat(args.date) if args.date else date.today()

    print(f"\n🏠 架空間取り図 プロンプト生成エンジン")
    print(f"   対象日付: {target_date.isoformat()}\n")

    client   = anthropic.Anthropic(api_key=api_key)
    settings = pick_daily_settings(target_date)
    data     = generate_prompts(client, settings)
    out_path = save_output(data, settings, target_date)

    print_summary(data, out_path)

    print(f"\n✅ 次のステップ:")
    print(f"   python image_engine.py --diary {out_path} --mode floorplan")
    print(f"   python post_engine.py  --diary {out_path}")


if __name__ == "__main__":
    main()