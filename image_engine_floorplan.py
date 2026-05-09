"""
image_engine_floorplan.py
─────────────────────────────────────────────
架空間取り図専用の画像生成エンジン
floorplan_prompt_engine.py が出力したJSONを読み込み
DALL-E 3で3枚の画像を生成する

使い方:
    python image_engine_floorplan.py
    python image_engine_floorplan.py --diary output/floorplan_diary/2026-05-07.json
"""

import os
import sys
import json
import time
import base64
import argparse
import requests
from pathlib import Path
from datetime import date

import anthropic
from dotenv import load_dotenv

load_dotenv()

OUTPUT_DIR = Path("output/floorplan_images")

# ══════════════════════════════════════════
# スタイル別のプロンプト強化
# ══════════════════════════════════════════

NO_TEXT = (
    "no text, no letters, no words, no labels, no writing, "
    "no annotations, no captions, no titles, no numbers, "
    "no signs, no inscriptions, no typography anywhere"
)

STYLE_ENHANCERS = {
    "architectural_blueprint": (
        "architectural floor plan drawing, white background, "
        "clean black ink lines, "
        "top-down orthographic view, precise technical drawing style, "
        "dotted walls, dimension lines, north arrow indicator, "
        "aged parchment paper texture, hand-drawn feel"
    ),
    "fantasy_illustration": (
        "fantasy map illustration style, top-down view, "
        "richly colored, ornate decorative border, "
        "painterly texture, magical atmosphere, "
        "detailed room contents visible, isometric-like depth, "
        "illuminated manuscript style, gold ink accents"
    ),
}

QUALITY_SUFFIX = (
    "highly detailed, beautiful composition, "
    "Instagram-worthy, striking visual, "
    "8K quality render"
)

NEGATIVE_BLUEPRINT = (
    "photo, realistic photo, 3D render, dark background, "
    "blurry, low quality, modern architecture, plain"
)

NEGATIVE_FANTASY = (
    "photo, realistic photo, blueprint only, "
    "white background, technical drawing only, "
    "blurry, low quality, ugly"
)


def load_diary(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_latest_diary() -> Path:
    diary_dir = Path("output/floorplan_diary")
    if not diary_dir.exists():
        print("❌ output/floorplan_diary/ が見つかりません")
        print("   先に floorplan_prompt_engine.py を実行してください")
        sys.exit(1)
    jsons = sorted(diary_dir.glob("*.json"), reverse=True)
    if not jsons:
        print("❌ 日記JSONが見つかりません")
        sys.exit(1)
    return jsons[0]


def enhance_prompt(prompt_data: dict, client: anthropic.Anthropic) -> str:
    """
    Claudeを使って架空間取り図用に
    プロンプトをさらにリアリティアップ
    """
    style      = prompt_data.get("style", "fantasy_illustration")
    base       = prompt_data.get("prompt_en", "")
    scene      = prompt_data.get("scene", "")
    style_enh  = STYLE_ENHANCERS.get(style, STYLE_ENHANCERS["fantasy_illustration"])

    full = f"{base}, {style_enh}, {QUALITY_SUFFIX}, {NO_TEXT}"
    return full[:1000]


def generate_image(prompt: str, negative: str, api_key: str) -> bytes:
    """DALL-E 3で画像生成"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type":  "application/json",
    }
    payload = {
        "model":           "dall-e-3",
        "prompt":          prompt,
        "n":               1,
        "size":            "1024x1024",
        "quality":         "hd",
        "style":           "vivid",   # 架空世界なのでvividで鮮やかに
        "response_format": "b64_json",
    }

    resp = requests.post(
        "https://api.openai.com/v1/images/generations",
        headers=headers,
        json=payload,
        timeout=120,
    )

    if resp.status_code != 200:
        print(f"    ❌ エラー: {resp.status_code} {resp.text[:200]}")
        return None

    revised = resp.json()["data"][0].get("revised_prompt", "")
    if revised:
        print(f"       📝 {revised[:70]}...")

    return base64.b64decode(resp.json()["data"][0]["b64_json"])


def save_image(image_bytes: bytes, out_dir: Path, index: int, scene: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    safe  = scene.replace("/", "_").replace(" ", "_").replace("（","_").replace("）","")
    path  = out_dir / f"{index:02d}_{safe}.png"
    with open(path, "wb") as f:
        f.write(image_bytes)
    return path


def update_diary(diary_path: str, image_paths: list):
    with open(diary_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    prompts = data.get("image_prompts", [])
    for i, img_path in enumerate(image_paths):
        if i < len(prompts) and img_path:
            prompts[i]["generated_image"] = str(img_path)
    with open(diary_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n  💾 日記JSONを更新: {diary_path}")


def main():
    parser = argparse.ArgumentParser(description="架空間取り図 画像生成")
    parser.add_argument("--diary", default=None)
    args = parser.parse_args()

    openai_key    = os.environ.get("OPENAI_API_KEY")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")

    if not openai_key:
        print("❌ OPENAI_API_KEY が設定されていません")
        sys.exit(1)
    if not anthropic_key:
        print("❌ ANTHROPIC_API_KEY が設定されていません")
        sys.exit(1)

    diary_path = args.diary or str(get_latest_diary())
    print(f"\n🎨 架空間取り図 画像生成エンジン")
    print(f"   日記JSON : {diary_path}\n")

    diary       = load_diary(diary_path)
    concept     = diary.get("concept", {})
    prompts     = diary.get("image_prompts", [])
    target_date = diary.get("_meta", {}).get("target_date", date.today().isoformat())

    print(f"  🌍 テーマ : {concept.get('theme','?')}")
    print(f"  🏠 形状   : {concept.get('shape','?')}")
    print(f"  🎨 生成枚数: {len(prompts)} 枚\n")

    client      = anthropic.Anthropic(api_key=anthropic_key)
    out_dir     = OUTPUT_DIR / target_date
    saved_paths = []

    for i, prompt_data in enumerate(prompts):
        scene = prompt_data.get("scene", f"scene_{i}")
        style = prompt_data.get("style", "fantasy_illustration")
        neg   = prompt_data.get("negative", NEGATIVE_FANTASY)

        print(f"  [{i+1}/{len(prompts)}] {scene} ({style})")

        full_prompt = enhance_prompt(prompt_data, client)
        print(f"       プロンプト: {full_prompt[:70]}...")

        image_bytes = generate_image(full_prompt, neg, openai_key)

        if image_bytes:
            out_path = save_image(image_bytes, out_dir, i, scene)
            saved_paths.append(str(out_path))
            print(f"       ✅ {out_path}")
        else:
            saved_paths.append(None)
            print(f"       ⚠️  失敗")

        if i < len(prompts) - 1:
            time.sleep(3)

    if any(saved_paths):
        update_diary(diary_path, saved_paths)

    print("\n" + "="*55)
    print("🎨 画像生成 完了!")
    print("="*55)
    for i, p in enumerate(saved_paths):
        scene  = prompts[i].get("scene", f"scene_{i}")
        status = f"✅ {p}" if p else "⚠️  失敗"
        print(f"  {scene}: {status}")
    print("="*55)
    print(f"\n✅ 次: python post_engine.py --diary {diary_path}")


if __name__ == "__main__":
    main()