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
    # ── 自然・環境系 ──
    ("魔法文明",      "魔法と錬金術が発達した中世風世界",        "arcane, mystical, medieval, glowing runes"),
    ("深海都市",      "海底に築かれた都市文明",                   "underwater, bioluminescent, pressure-sealed, coral"),
    ("空中浮遊",      "雲の上に浮かぶ島々に住む文明",             "floating island, clouds, airship, wind-worn stone"),
    ("地底文明",      "地下深くに広がる巨大な洞窟都市",           "cavern, stalagmites, underground, dim lantern light"),
    ("自然融合",      "植物・木・水と一体化した有機的建築",        "organic, treehouse, living wood, moss-covered"),
    ("砂漠遺跡",      "古代遺跡に住み着いた砂漠の民",             "desert ruins, sandstone, carved cliff, ancient"),
    ("氷雪王国",      "永久凍土の中に掘られた氷の住居",           "ice palace, frozen, aurora, carved glacier"),
    ("溶岩火山",      "活火山の中に築かれた耐熱文明",             "volcanic, lava, obsidian, fire-resistant, dark rock"),
    ("菌類世界",      "巨大な菌類・キノコが建材の世界",           "mushroom, fungal, spores, bioluminescent, organic"),
    ("珊瑚礁宮殿",    "珊瑚と貝殻で作られた海中の宮殿",          "coral palace, seashell, ocean floor, pearl, kelp forest"),
    ("雲海神殿",      "霧と雲の中に浮かぶ古代神殿",              "misty temple, cloud sea, ancient pillars, divine light"),
    ("巨木都市",      "樹齢数万年の巨木の内部に作られた都市",     "giant tree interior, wooden chambers, root corridors, amber light"),
    ("砂中遺跡",      "砂に埋もれた古代文明の地下空間",           "buried ruins, sandstone, ancient carvings, torchlight"),
    ("氷河洞窟",      "氷河の内部に自然形成された居住空間",       "ice cave, glacier blue, frozen waterfall, crystal clear"),
    ("火山島",        "活火山の火口付近に築かれた居住地",         "volcanic island, obsidian walls, lava glow, ash sky"),
    ("浮遊岩",        "重力に逆らって浮かぶ岩塊の上の住居",       "floating rock, anti-gravity, waterfalls upward, sky island"),
    ("深森神域",      "原生林の奥深くに封印された神の住居",       "ancient forest, sacred grove, bioluminescent plants, twilight"),
    # ── テクノロジー系 ──
    ("SF宇宙",        "宇宙植民地・軌道上居住施設",               "sci-fi, space station, zero gravity, metallic hull"),
    ("蒸気機関",      "蒸気と歯車が動力の異世界",                 "steampunk, brass gears, steam pipes, Victorian"),
    ("サイバーパンク", "テクノロジーと貧困が混在する近未来",       "cyberpunk, neon, dystopian, cramped, holographic"),
    ("バイオパンク",   "生体技術で建築された有機的な近未来都市",   "biopunk, organic machinery, flesh walls, bio-luminescent tubes"),
    ("ディーゼルパンク","ディーゼルエンジンと工業美の異世界",      "dieselpunk, industrial, oil pipes, factory aesthetic, gritty"),
    ("アトムパンク",   "1950年代SF風の核エネルギー文明",           "atompunk, retro-futuristic, atomic age, chrome, googie architecture"),
    ("ソーラーパンク", "太陽エネルギーと植物が共存するユートピア", "solarpunk, solar panels, green rooftop, sustainable, bright utopia"),
    ("量子空間",      "量子力学的に存在が不確定な住居",           "quantum realm, probability clouds, superposition, glitch reality"),
    ("ナノテク",      "ナノマシンで自在に変形する住居",           "nanotechnology, self-assembling, microscale, silver fluid"),
    ("廃墟サイバー",  "廃墟化したサイバー都市の再利用住居",        "ruins cyberpunk, overgrown circuits, rusted neon, decay tech"),
    # ── 神秘・ホラー系 ──
    ("水晶文明",      "水晶と光を素材とした透明な建築",           "crystal, translucent, prismatic light, gem-like"),
    ("ホラー屋敷",    "怨念や呪いが染み込んだ不気味な邸宅",       "haunted, gothic, dark, decayed, eerie shadows"),
    ("時空歪み",      "物理法則が歪んだ不思議な空間",             "impossible geometry, M.C. Escher, non-Euclidean, surreal"),
    ("夢幻境",        "夢と現実の境界が溶けた幻想空間",           "dreamscape, surreal, melting architecture, pastel nightmare"),
    ("死者の宮殿",    "冥界に存在する死者のための住居",           "underworld, skeletal architecture, pale moonlight, spirit realm"),
    ("悪夢城",        "恐怖を具現化した生きている城",             "living castle, breathing walls, nightmare, grotesque, dark fantasy"),
    ("霧の神殿",      "濃霧の中に現れては消える幻の神殿",         "fog temple, ethereal, disappearing, mist, ghostly architecture"),
    ("呪術師の塔",    "呪術と禁忌の儀式が行われる黒い塔",         "cursed tower, ritual circles, black stone, forbidden magic"),
    ("鏡の迷宮",      "無限に続く鏡の回廊からなる住居",           "mirror maze, infinite reflection, glass corridors, disorienting"),
    ("時計仕掛け",    "時間を操る装置が組み込まれた住居",         "clockwork, time manipulation, gears everywhere, temporal anomaly"),
    # ── 文化・歴史系 ──
    ("東洋仙境",      "仙人が住む東洋的な幻想世界",               "Chinese immortal realm, jade, bamboo, mountain mist, feng shui"),
    ("砂漠カリフ",    "アラビアンナイト風の豪奢な宮殿",           "Arabian nights, mosaic tiles, arched corridors, desert palace"),
    ("北欧神話",      "ヴァイキングと神々が共存する世界",         "Norse mythology, longhouse, runes, Yggdrasil, frost and fire"),
    ("古代ローマ",    "魔法が加わった古代ローマ風建築",           "Roman fantasy, marble columns, aqueducts, mosaic floor, toga"),
    ("マヤ神殿",      "生きた神が降臨するマヤ文明の神殿",         "Mayan temple, jungle overgrown, stone carvings, sacred geometry"),
    ("江戸異界",      "妖怪と人間が共存する江戸時代の長屋",       "Edo Japan, yokai, paper screens, engawa, lantern light"),
    ("ケルト魔境",    "ケルト神話の妖精が住む森の住居",           "Celtic fairy mound, ancient oak, stone circle, emerald light"),
    ("インカ天空",    "マチュピチュを超える天空の都市遺跡",        "Incan ruins, mountain top, stone terraces, condor, altitude"),
    # ── 特殊・ユニーク系 ──
    ("本の世界",      "巨大な本の内側に作られた住居",             "inside a book, paper architecture, ink rivers, library world"),
    ("音楽空間",      "音楽と振動で構成された音の住居",           "sound architecture, musical notes, vibrating strings, resonance"),
    ("色彩文明",      "色と光のみで構成された住居",               "color world, prismatic, pure light, chromatic architecture"),
    ("砂糖菓子",      "お菓子と砂糖で作られたメルヘン住居",       "candy architecture, sugar walls, chocolate floors, gingerbread"),
    ("骨格文明",      "巨大生物の骨格を利用した住居",             "bone architecture, giant skeleton, fossil walls, organic decay"),
    ("雲の綿",        "雲の素材でできたふわふわの住居",           "cloud material, soft architecture, cotton candy sky, weightless"),
    ("砂の城",        "砂で精巧に作られ崩れない不思議な城",       "sand castle, intricate, desert magic, golden, elaborate"),
    ("記憶の館",      "訪れた人の記憶が壁に刻まれる住居",         "memory palace, faded photographs, nostalgic, layered time"),
]

FLOOR_SHAPES = [
    # ── 幾何学形状 ──
    ("円形",          "perfectly circular floor plan, radial rooms like pie slices"),
    ("六角形",        "hexagonal floor plan, honeycomb-like room arrangement"),
    ("螺旋形",        "spiral floor plan, rooms arranged in a continuous spiral"),
    ("星形",          "star-shaped floor plan, pointed wing extensions"),
    ("球体断面",      "cross-section of a sphere, dome-shaped rooms"),
    ("結晶型",        "crystalline geometric shape, sharp angles like a mineral formation"),
    ("八角形",        "octagonal floor plan, eight equal sides with central hub"),
    ("三角形",        "triangular floor plan, three wings meeting at a central point"),
    ("十字形",        "cross-shaped floor plan, four equal arms extending outward"),
    ("菱形",          "diamond-shaped floor plan, diagonal orientation"),
    ("同心円",        "concentric circles floor plan, nested ring-shaped corridors"),
    ("花弁形",        "flower petal shaped, rooms radiating like petals from center"),
    ("雪の結晶",      "snowflake pattern floor plan, six-fold symmetry with branching rooms"),
    ("無限大",        "figure-eight or infinity symbol shaped floor plan"),
    ("迷路格子",      "grid maze floor plan, regular intersections with many dead ends"),
    # ── 有機的形状 ──
    ("有機的変形",    "organic irregular shape, amoeba-like outline, no straight walls"),
    ("洞窟型",        "cave-carved irregular shape, natural rock walls with carved rooms"),
    ("木造樹上",      "built around and inside a massive tree, rooms in branches and trunk"),
    ("クモの巣",      "web-like radial pattern, thin corridors connecting circular nodes"),
    ("根茎型",        "root system shaped floor plan, branching irregular corridors"),
    ("波紋型",        "ripple pattern, concentric irregular waves"),
    ("流水型",        "river-like flowing shape, meandering corridors"),
    ("珊瑚型",        "coral-like branching structure, organic protrusions"),
    ("雲形",          "cloud-shaped outline, soft irregular bumps"),
    ("溶岩流",        "lava flow shaped, one large mass with irregular flowing extensions"),
    # ── 複合・特殊形状 ──
    ("多層塔型",      "multi-story tower cross-section, stacked circular floors"),
    ("L字変形",       "asymmetric L-shape with curved walls and irregular protrusions"),
    ("断崖彫刻",      "carved into a cliff face, horizontal layered rooms"),
    ("入れ子構造",    "rooms within rooms, nested boxes of decreasing size"),
    ("鏡像対称",      "perfectly mirrored left-right symmetry, bilateral layout"),
    ("回転非対称",    "rotationally asymmetric, twisted irregular layout"),
    ("モジュール型",  "modular hexagonal or square pods connected by tunnels"),
    ("フラクタル",    "fractal self-similar pattern, rooms contain smaller rooms"),
    ("橋渡し",        "multiple separate structures connected by bridges and walkways"),
    ("地下迷宮",      "underground labyrinth, multiple levels connected by staircases"),
    ("環状列石",      "rooms arranged in a circle like Stonehenge"),
    ("船型",          "ship hull cross-section, long narrow hull with decks"),
    ("砦型",          "fortress floor plan, thick outer walls with inner keep"),
    ("蜂の巣",        "honeycomb tessellation, tightly packed hexagonal cells"),
    ("DNA螺旋",       "double helix cross-section, two intertwining spiral paths"),
]

ROOM_TYPES_FANTASY = [
    # ── 魔法・儀式系 ──
    "儀式の間", "魔法陣の部屋", "ポーション工房", "召喚の間",
    "封印の間", "転移陣の間", "禁断の扉", "魔導炉",
    "占星術の塔", "幻視の浴室", "時間停止の間", "呪文工房",
    "魔力充填室", "異界の窓", "霊力溜め", "契約の間",
    "魔法陣図書館", "錬金釜の間", "幽閉の塔", "魔女の台所",
    # ── 自然・元素系 ──
    "炎の寝室", "風の塔", "水中居室", "無重力室",
    "生命樹の根元", "氷の結晶室", "雷蓄積槽", "土の瞑想室",
    "霧の回廊", "光の祭壇", "闇の瞑想室", "嵐の観測台",
    "溶岩浴場", "砂の流動室", "植物の寝室", "星の庭",
    "月光の間", "太陽の礼拝堂", "虹の架け橋", "雨の読書室",
    # ── 知識・研究系 ──
    "図書室", "骨の書斎", "星観測室", "腐食の実験室",
    "標本室", "地図の間", "暗号解読室", "禁書庫",
    "解剖実験室", "時計工房", "発明工房", "化石研究室",
    "幻獣図鑑の間", "古文書保管室", "鉱物収集室", "魔道具工房",
    "天体観測ドーム", "夢の記録室", "記憶格納庫", "知識の泉",
    # ── 居住・生活系 ──
    "夢見の間", "記憶の間", "霊廟", "時間の部屋",
    "食事の広間", "来客の間", "主の寝室", "従者の部屋",
    "宝物庫", "武器庫", "入口の間", "幻影の回廊",
    "瞑想の間", "浮遊する寝台の部屋", "透明な浴室", "音楽の間",
    "香りの庭", "色彩の遊戯室", "影の書斎", "静寂の間",
    # ── 特殊・ユニーク系 ──
    "逆さまの部屋", "縮小の間", "鏡の回廊", "時間巻き戻し室",
    "夢と現実の境界", "次元の裂け目", "記憶消去室", "感情蒸留室",
    "恐怖の具現化室", "欲望の間", "秘密の二重扉", "幽霊の寝室",
    "不死の研究室", "変身の間", "予言の水鏡", "神託の間",
    "冥界への入口", "魂の天秤室", "時間結晶展示室", "無の間",
    # ── 機能・実用系 ──
    "蒸気動力室", "エネルギー炉心", "通信の間", "転送ポッド格納庫",
    "冷凍保管室", "毒の調合室", "罠工房", "諜報の間",
    "賭博の広間", "拷問の間", "脱出用秘密通路", "偽の宝物庫",
    "侵入者感知室", "聖域", "禊の泉", "参拝の間",
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
    "instagram": "Instagram用日本語キャプション（200字以内・改行あり・ハッシュタグなし）。最後の1行に「図集はプロフリンクのBoothで販売中」という趣旨の一文を自然に入れる。",
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