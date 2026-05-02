"""
image_engine.py
─────────────────────────────────────────────
プロジェクト #5: 架空の街・歴史 AI旅日記
Step 3: 画像自動生成エンジン（超リアル写真風・v3）

変更点:
- 架空世界の設定を「現実の類似地域」に変換してから生成
- 食べ物は「素材・調理法・質感」で描写（料理名を使わない）
- Claude APIで「リアル変換プロンプト」を自動生成
- DALL-E 3パラメータ最適化
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

OUTPUT_DIR = Path("output/images")

# ──────────────────────────────────────────
# ネガティブ要素（プロンプトに混ぜる）
# ──────────────────────────────────────────
HARD_NEGATIVE = (
    "Do not include: illustration, painting, anime, manga, cartoon, "
    "CGI, 3D render, digital art, concept art, fantasy art, "
    "watercolor, sketch, comic, game art, stylized, unrealistic, "
    "plastic-looking food, artificial, mechanical texture"
)


# ──────────────────────────────────────────
# Claude APIで「リアル変換プロンプト」を生成
# ──────────────────────────────────────────
REALISM_CONVERSION_PROMPT = """
あなたはプロの写真家です。
架空世界の設定を「本物の旅行写真」として撮影するための
英語プロンプトに変換してください。

【ルール】
1. 架空の地名・世界名は絶対に使わない
2. 「fantasy」「magical」「fictional」は絶対に使わない
3. 現実の近い地域・文化に置き換える（例: 霧の石造り都市→Edinburgh, Prague）
4. 食べ物は料理名を使わず「素材・色・質感・調理法」で描写する
5. カメラ・レンズ・撮影条件を必ず含める
6. 一人称視点の旅行スナップとして描写する

【シーン情報】
シーン種類: {scene}
元の設定: {original_description}
場所の雰囲気: {visual_mood}

【出力形式】
JSONのみ出力。説明文・コードブロック不要。

{{
  "prompt": "英語プロンプト（100語以内）",
  "reasoning": "どの現実地域・素材に変換したか（日本語で一言）"
}}
"""


def generate_realistic_prompt(
    client: anthropic.Anthropic,
    scene: str,
    original_prompt: str,
    visual_mood: str,
) -> str:
    """Claude APIで架空設定→リアル写真プロンプトに変換"""

    prompt = REALISM_CONVERSION_PROMPT.format(
        scene=scene,
        original_description=original_prompt,
        visual_mood=visual_mood,
    )

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",  # 速度優先でHaikuを使用
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        data = json.loads(raw)
        reasoning = data.get("reasoning", "")
        prompt_en = data.get("prompt", original_prompt)
        print(f"       💡 変換: {reasoning}")
        return prompt_en
    except json.JSONDecodeError:
        return original_prompt


# ──────────────────────────────────────────
# 撮影スタイル（シーン別）
# ──────────────────────────────────────────
CAMERA_SETTINGS = {
    "メインの風景": (
        "shot on Sony A7R V with 24mm f/2.8 lens, "
        "golden hour, long exposure, tripod, "
        "RAW photo converted to JPEG, "
        "slight lens flare, atmospheric perspective, "
        "wet stone reflecting warm light"
    ),
    "料理・食事": (
        "shot on Canon EOS R5 with 100mm macro lens, "
        "f/2.8 aperture, soft natural side lighting from window, "
        "shallow depth of field, steam wisps visible, "
        "aged wooden surface, linen napkin, "
        "editorial food photography, no filters"
    ),
    "人物・生活感": (
        "shot on Leica M11 with 35mm Summilux lens, "
        "available light only, f/1.4, 1/500s, ISO 800, "
        "candid moment, subject unaware, "
        "documentary street photography, grain texture"
    ),
}

QUALITY_SUFFIX = (
    "photorealistic, hyperrealistic, "
    "8K resolution, ultra sharp, real texture, "
    "no post-processing artifacts, "
    "looks like a real photograph"
)


# ──────────────────────────────────────────
# 日記JSON読み込み
# ──────────────────────────────────────────
def load_diary(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_latest_diary() -> Path:
    diary_dir = Path("output/diary")
    if not diary_dir.exists():
        print("❌ output/diary/ が見つかりません")
        sys.exit(1)
    jsons = sorted(diary_dir.glob("*.json"), reverse=True)
    if not jsons:
        print("❌ 日記JSONが見つかりません")
        sys.exit(1)
    return jsons[0]


# ──────────────────────────────────────────
# DALL·E 3 生成
# ──────────────────────────────────────────
def generate_with_dalle(
    realistic_prompt: str,
    scene: str,
    api_key: str,
) -> bytes:

    camera = CAMERA_SETTINGS.get(scene, "")
    full_prompt = (
        f"{realistic_prompt}. "
        f"{camera}. "
        f"{QUALITY_SUFFIX}. "
        f"{HARD_NEGATIVE}."
    )
    full_prompt = full_prompt[:1000]

    print(f"    🎨 DALL-E 3 生成中: {scene}")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type":  "application/json",
    }
    payload = {
        "model":           "dall-e-3",
        "prompt":          full_prompt,
        "n":               1,
        "size":            "1792x1024",  # 横長で映える
        "quality":         "hd",
        "style":           "natural",
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
        print(f"       📝 revised: {revised[:80]}...")

    return base64.b64decode(resp.json()["data"][0]["b64_json"])


# ──────────────────────────────────────────
# Stability AI 生成
# ──────────────────────────────────────────
def generate_with_stability(
    realistic_prompt: str,
    scene: str,
    api_key: str,
) -> bytes:

    camera   = CAMERA_SETTINGS.get(scene, "")
    positive = f"{realistic_prompt}. {camera}. {QUALITY_SUFFIX}"

    print(f"    🎨 Stability AI 生成中: {scene}")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }
    payload = {
        "text_prompts": [
            {"text": positive[:800],    "weight": 1.0},
            {"text": HARD_NEGATIVE,     "weight": -1.0},
        ],
        "cfg_scale":    7,
        "height":       1024,
        "width":        1792,
        "samples":      1,
        "steps":        50,
        "style_preset": "photographic",
        "sampler":      "DPM_2_ANCESTRAL",
    }

    resp = requests.post(
        "https://api.stability.ai/v1/generation/"
        "stable-diffusion-xl-1024-v1-0/text-to-image",
        headers=headers,
        json=payload,
        timeout=120,
    )

    if resp.status_code != 200:
        print(f"    ❌ エラー: {resp.status_code} {resp.text[:200]}")
        return None

    return base64.b64decode(resp.json()["artifacts"][0]["base64"])


# ──────────────────────────────────────────
# 画像保存・JSON更新
# ──────────────────────────────────────────
def save_image(image_bytes: bytes, out_dir: Path,
               index: int, scene: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    safe = scene.replace("/", "_").replace(" ", "_")
    out_path = out_dir / f"scene_{index}_{safe}.png"
    with open(out_path, "wb") as f:
        f.write(image_bytes)
    return out_path


def update_diary(diary_path: str, image_paths: list):
    with open(diary_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    prompts = data.get("diary", {}).get("image_prompts", [])
    for i, img_path in enumerate(image_paths):
        if i < len(prompts) and img_path:
            prompts[i]["generated_image"] = str(img_path)
    with open(diary_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n  💾 日記JSONを更新しました: {diary_path}")


# ──────────────────────────────────────────
# メイン
# ──────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--diary",  default=None)
    parser.add_argument("--engine", default="dalle",
                        choices=["dalle", "stability"])
    args = parser.parse_args()

    # APIキー確認
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if not anthropic_key:
        print("❌ ANTHROPIC_API_KEY が設定されていません")
        sys.exit(1)

    if args.engine == "dalle":
        img_api_key = os.environ.get("OPENAI_API_KEY")
        if not img_api_key:
            print("❌ OPENAI_API_KEY が設定されていません")
            sys.exit(1)
        generate_fn = lambda p, s: generate_with_dalle(p, s, img_api_key)
    else:
        img_api_key = os.environ.get("STABILITY_API_KEY")
        if not img_api_key:
            print("❌ STABILITY_API_KEY が設定されていません")
            sys.exit(1)
        generate_fn = lambda p, s: generate_with_stability(p, s, img_api_key)

    diary_path = args.diary or str(get_latest_diary())
    print(f"\n🖼️  画像生成エンジン v3（超リアル写真風）")
    print(f"   エンジン : {args.engine.upper()}")
    print(f"   日記JSON : {diary_path}\n")

    diary       = load_diary(diary_path)
    diary_data  = diary.get("diary", {})
    target_date = diary.get("_meta", {}).get(
        "target_date", date.today().isoformat()
    )
    prompts     = diary_data.get("image_prompts", [])

    if not prompts:
        print("❌ image_prompts が見つかりません")
        sys.exit(1)

    print(f"  📍 訪問地  : {diary_data.get('location_name', '?')}")
    print(f"  🎨 生成枚数: {len(prompts)} 枚")
    print(f"  🔄 方式    : Claudeで架空→リアル変換 → DALL-E 3\n")

    claude_client = anthropic.Anthropic(api_key=anthropic_key)
    out_dir       = OUTPUT_DIR / target_date
    saved_paths   = []

    for i, prompt_data in enumerate(prompts):
        scene      = prompt_data.get("scene", f"scene_{i}")
        prompt_en  = prompt_data.get("prompt_en", "")
        visual_mood = prompt_data.get("visual_mood", "")

        print(f"\n  [{i+1}/{len(prompts)}] {scene}")

        # Step1: Claudeでリアル変換プロンプトを生成
        print(f"       🔄 架空→リアル変換中...")
        realistic_prompt = generate_realistic_prompt(
            claude_client, scene, prompt_en, visual_mood
        )

        # Step2: 画像生成
        image_bytes = generate_fn(realistic_prompt, scene)

        if image_bytes:
            out_path = save_image(image_bytes, out_dir, i, scene)
            saved_paths.append(str(out_path))
            print(f"       ✅ 保存: {out_path}")
        else:
            print(f"       ⚠️  スキップ")
            saved_paths.append(None)

        if i < len(prompts) - 1:
            time.sleep(3)

    if any(saved_paths):
        update_diary(diary_path, saved_paths)

    print("\n" + "=" * 55)
    print("🖼️  画像生成 完了!")
    print("=" * 55)
    for i, p in enumerate(saved_paths):
        scene  = prompts[i].get("scene", f"scene_{i}")
        status = f"✅ {p}" if p else "⚠️  失敗"
        print(f"  {scene}: {status}")
    print("=" * 55)
    print(f"\n✅ 次: python post_engine.py --diary {diary_path}")


if __name__ == "__main__":
    main()