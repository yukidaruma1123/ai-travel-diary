"""
orchestrator.py
─────────────────────────────────────────────
プロジェクト #5: 架空の街・歴史 AI旅日記
Step 5: 全パイプライン一括実行スクリプト

使い方:
    python orchestrator.py               # 今日の日記を生成・投稿
    python orchestrator.py --dry-run     # 投稿せずに生成だけ確認
    python orchestrator.py --date 2025-05-01  # 指定日付で実行
    python orchestrator.py --skip-image  # 画像生成をスキップ
    python orchestrator.py --sns all     # 全SNSに投稿
"""

import os
import sys
import json
import argparse
import traceback
from pathlib import Path
from datetime import date, datetime

from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────────────────────
# ログ設定
# ──────────────────────────────────────────
LOG_DIR = Path("logs")

def log(msg: str, level: str = "INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] [{level}] {msg}"
    print(line)

    LOG_DIR.mkdir(exist_ok=True)
    log_file = LOG_DIR / f"{date.today().isoformat()}.log"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ──────────────────────────────────────────
# 各ステップの実行
# ──────────────────────────────────────────
def step_generate_diary(target_date: str, world_path: str) -> str:
    """Step2: 日記テキスト生成 → 日記JSONパスを返す"""
    from diary_engine import (
        load_world_bible, pick_todays_location, pick_todays_food,
        get_current_festival, build_diary_prompt,
        generate_diary, save_diary, print_summary
    )
    import anthropic
    from datetime import date as dt

    log("📖 日記テキスト生成開始")

    api_key = os.environ["ANTHROPIC_API_KEY"]
    client  = anthropic.Anthropic(api_key=api_key)

    d     = dt.fromisoformat(target_date)
    world = load_world_bible(world_path)

    location = pick_todays_location(world, d)
    food     = pick_todays_food(world, d)
    festival = get_current_festival(world, d)

    log(f"  訪問地: {location['name']} / 料理: {food['name']}")

    prompt     = build_diary_prompt(world, location, food, festival, d)
    diary_data = generate_diary(client, prompt)
    out_path   = save_diary(diary_data, d, location, food)

    log(f"  ✅ 日記生成完了: {out_path}")
    return str(out_path)


def step_generate_images(diary_path: str, engine: str = "dalle") -> bool:
    """Step3: 画像生成"""
    from image_engine import (
        load_diary, generate_realistic_prompt,
        generate_with_dalle, generate_with_stability,
        save_image, update_diary, OUTPUT_DIR
    )
    import anthropic
    from datetime import date as dt
    import time

    log("🖼️  画像生成開始")

    anthropic_key = os.environ["ANTHROPIC_API_KEY"]
    claude_client = anthropic.Anthropic(api_key=anthropic_key)

    if engine == "dalle":
        img_key     = os.environ["OPENAI_API_KEY"]
        generate_fn = lambda p, s: generate_with_dalle(p, s, img_key)
    else:
        img_key     = os.environ["STABILITY_API_KEY"]
        generate_fn = lambda p, s: generate_with_stability(p, s, img_key)

    diary       = load_diary(diary_path)
    diary_data  = diary.get("diary", {})
    target_date = diary.get("_meta", {}).get("target_date", dt.today().isoformat())
    prompts     = diary_data.get("image_prompts", [])

    out_dir     = OUTPUT_DIR / target_date
    saved_paths = []

    for i, prompt_data in enumerate(prompts):
        scene      = prompt_data.get("scene", f"scene_{i}")
        prompt_en  = prompt_data.get("prompt_en", "")
        visual_mood = prompt_data.get("visual_mood", "")

        realistic = generate_realistic_prompt(
            claude_client, scene, prompt_en, visual_mood
        )
        image_bytes = generate_fn(realistic, scene)

        if image_bytes:
            out_path = save_image(image_bytes, out_dir, i, scene)
            saved_paths.append(str(out_path))
            log(f"  ✅ 画像保存: {out_path}")
        else:
            saved_paths.append(None)
            log(f"  ⚠️  画像スキップ: {scene}", "WARN")

        if i < len(prompts) - 1:
            time.sleep(3)

    if any(saved_paths):
        update_diary(diary_path, saved_paths)

    return any(saved_paths)


def step_post_sns(diary_path: str, sns_target: str, dry_run: bool = False) -> dict:
    """Step4: SNS投稿"""
    from post_engine import (
        load_diary, get_image_paths,
        build_instagram_caption, build_x_caption,
        build_pinterest_description, save_post_results,
        InstagramPoster, XPoster, PinterestPoster
    )

    log(f"📤 SNS投稿開始 (target={sns_target}, dry_run={dry_run})")

    diary       = load_diary(diary_path)
    diary_data  = diary.get("diary", {})
    image_paths = get_image_paths(diary)

    if not image_paths:
        log("❌ 画像が見つかりません", "ERROR")
        return {}

    if dry_run:
        log("  🔍 DRY RUN: 投稿はスキップします")
        log(f"  キャプション確認: {build_instagram_caption(diary)[:80]}...")
        return {"dry_run": True}

    results     = {}
    sns_targets = (
        ["instagram", "x", "pinterest"] if sns_target == "all"
        else [sns_target]
    )

    if "instagram" in sns_targets:
        try:
            poster  = InstagramPoster()
            caption = build_instagram_caption(diary)
            post_id = (
                poster.post_carousel(image_paths, caption)
                if len(image_paths) >= 2
                else poster.post_single(image_paths[0], caption)
            )
            results["instagram"] = {"post_id": post_id, "status": "success"}
            log(f"  ✅ Instagram投稿完了: {post_id}")
        except Exception as e:
            results["instagram"] = {"status": "error", "message": str(e)}
            log(f"  ❌ Instagram失敗: {e}", "ERROR")

    if "x" in sns_targets:
        try:
            poster  = XPoster()
            text    = build_x_caption(diary)
            post_id = poster.post(text, image_paths[0] if image_paths else None)
            results["x"] = {"post_id": post_id, "status": "success"}
            log(f"  ✅ X投稿完了: {post_id}")
        except Exception as e:
            results["x"] = {"status": "error", "message": str(e)}
            log(f"  ❌ X失敗: {e}", "ERROR")

    if "pinterest" in sns_targets:
        try:
            poster      = PinterestPoster()
            title       = f"{diary_data.get('location_name', '')} — {diary_data.get('region_name', '')}"
            description = build_pinterest_description(diary)
            post_id     = poster.post(image_paths[0], title, description)
            results["pinterest"] = {"post_id": post_id, "status": "success"}
            log(f"  ✅ Pinterest投稿完了: {post_id}")
        except Exception as e:
            results["pinterest"] = {"status": "error", "message": str(e)}
            log(f"  ❌ Pinterest失敗: {e}", "ERROR")

    save_post_results(diary_path, results)
    return results


# ──────────────────────────────────────────
# 実行サマリーをJSONで保存
# ──────────────────────────────────────────
def save_run_summary(target_date: str, results: dict):
    LOG_DIR.mkdir(exist_ok=True)
    summary_path = LOG_DIR / f"{target_date}_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(
            {"date": target_date, "run_at": datetime.now().isoformat(), **results},
            f, ensure_ascii=False, indent=2
        )
    log(f"📋 実行サマリー保存: {summary_path}")


# ──────────────────────────────────────────
# メイン
# ──────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="AI旅日記 全パイプライン実行")
    parser.add_argument("--date",       default=None,        help="対象日付 YYYY-MM-DD")
    parser.add_argument("--world",      default="world_bible.yaml")
    parser.add_argument("--engine",     default="dalle",     choices=["dalle", "stability"])
    parser.add_argument("--sns",        default="instagram", choices=["instagram", "x", "pinterest", "all"])
    parser.add_argument("--dry-run",    action="store_true", help="投稿せず生成のみ")
    parser.add_argument("--skip-image", action="store_true", help="画像生成をスキップ")
    args = parser.parse_args()

    target_date = args.date or date.today().isoformat()

    log("=" * 55)
    log(f"🌍 AI旅日記パイプライン開始")
    log(f"   日付     : {target_date}")
    log(f"   エンジン : {args.engine}")
    log(f"   投稿先   : {args.sns}")
    log(f"   DRY RUN  : {args.dry_run}")
    log("=" * 55)

    run_results = {"target_date": target_date, "steps": {}}
    diary_path  = None

    try:
        # ── Step 2: 日記生成 ──
        diary_path = step_generate_diary(target_date, args.world)
        run_results["steps"]["diary"] = {"status": "success", "path": diary_path}

        # ── Step 3: 画像生成 ──
        if not args.skip_image:
            ok = step_generate_images(diary_path, args.engine)
            run_results["steps"]["image"] = {"status": "success" if ok else "partial"}
        else:
            log("⏭️  画像生成スキップ")
            run_results["steps"]["image"] = {"status": "skipped"}

        # ── Step 4: SNS投稿 ──
        post_results = step_post_sns(diary_path, args.sns, args.dry_run)
        run_results["steps"]["post"] = post_results

    except KeyboardInterrupt:
        log("⚠️  手動中断されました", "WARN")
        sys.exit(0)
    except Exception as e:
        log(f"❌ 予期しないエラー: {e}", "ERROR")
        log(traceback.format_exc(), "ERROR")
        run_results["steps"]["error"] = str(e)
        save_run_summary(target_date, run_results)
        sys.exit(1)

    save_run_summary(target_date, run_results)

    # 最終サマリー
    log("=" * 55)
    log("✅ 全パイプライン完了!")
    for step, result in run_results["steps"].items():
        status = result.get("status", "?")
        icon   = "✅" if status == "success" else ("⏭️" if status == "skipped" else "⚠️")
        log(f"   {icon} {step}: {status}")
    log("=" * 55)


if __name__ == "__main__":
    main()