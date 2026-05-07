"""
orchestrator_floorplan.py - 架空間取り図システム 全パイプライン実行
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

LOG_DIR = Path("logs")

def log(msg, level="INFO"):
    ts   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    print(line)
    LOG_DIR.mkdir(exist_ok=True)
    with open(LOG_DIR / f"{date.today().isoformat()}.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def get_image_paths_floorplan(diary: dict) -> list:
    """floorplan_diary用の画像パス取得（post_engineのものとは別実装）"""
    prompts = diary.get("image_prompts", [])
    paths = []
    for p in prompts:
        img = p.get("generated_image")
        if img and Path(img).exists():
            paths.append(img)
    return paths


def step1_generate_prompts(target_date: str) -> str:
    from floorplan_prompt_engine import (
        pick_daily_settings, generate_prompts, save_output
    )
    import anthropic
    from datetime import date as dt

    log("📐 プロンプト生成開始")
    client   = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    d        = dt.fromisoformat(target_date)
    settings = pick_daily_settings(d)
    data     = generate_prompts(client, settings)
    out_path = save_output(data, settings, d)
    log(f"  ✅ 完了: {out_path}")
    return str(out_path)


def step2_generate_images(diary_path: str) -> bool:
    from image_engine_floorplan import (
        load_diary, enhance_prompt, generate_image,
        save_image, update_diary, OUTPUT_DIR
    )
    import anthropic
    import time
    from datetime import date as dt

    log("🎨 画像生成開始")
    client  = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    diary   = load_diary(diary_path)
    prompts = diary.get("image_prompts", [])
    td      = diary.get("_meta", {}).get("target_date", dt.today().isoformat())
    out_dir = OUTPUT_DIR / td
    saved   = []

    for i, pd in enumerate(prompts):
        scene  = pd.get("scene", f"scene_{i}")
        neg    = pd.get("negative", "photo, realistic, low quality")
        full   = enhance_prompt(pd, client)
        bytes_ = generate_image(full, neg, os.environ["OPENAI_API_KEY"])
        if bytes_:
            p = save_image(bytes_, out_dir, i, scene)
            saved.append(str(p))
            log(f"  ✅ {scene}: {p}")
        else:
            saved.append(None)
            log(f"  ⚠️  {scene}: 失敗", "WARN")
        if i < len(prompts)-1: time.sleep(3)

    if any(saved):
        update_diary(diary_path, saved)
    return any(saved)


def step3_post_sns(diary_path: str, sns: str, dry_run: bool) -> dict:
    from post_engine import (
        InstagramPoster, save_post_results
    )

    log(f"📤 SNS投稿開始 (target={sns}, dry_run={dry_run})")

    # floorplan_diary用の画像パス取得
    with open(diary_path, "r", encoding="utf-8") as f:
        diary = json.load(f)

    image_paths = get_image_paths_floorplan(diary)

    if not image_paths:
        log("❌ 画像が見つかりません", "ERROR")
        log(f"   diary_path={diary_path}", "ERROR")
        # 生成済み画像のパスを直接探す
        td      = diary.get("_meta", {}).get("target_date", "")
        img_dir = Path("output/floorplan_images") / td
        if img_dir.exists():
            image_paths = [str(p) for p in sorted(img_dir.glob("*.png"))]
            log(f"   フォルダから {len(image_paths)} 枚見つかりました")
        if not image_paths:
            return {}

    if dry_run:
        log(f"  🔍 DRY RUN: 投稿スキップ ({len(image_paths)}枚確認)")
        for p in image_paths:
            log(f"      {p}")
        return {"dry_run": True, "image_count": len(image_paths)}

    results = {}
    caps    = diary.get("captions", {})
    tags_jp = diary.get("hashtags", {}).get("jp", [])
    tags_en = diary.get("hashtags", {}).get("en", [])
    caption = caps.get("instagram", "") + "\n\n" + " ".join(tags_jp + tags_en)

    if "instagram" in sns or sns == "all":
        try:
            poster  = InstagramPoster()
            post_id = (poster.post_carousel(image_paths, caption)
                       if len(image_paths) >= 2
                       else poster.post_single(image_paths[0], caption))
            results["instagram"] = {"post_id": post_id, "status": "success"}
            log(f"  ✅ Instagram: {post_id}")
        except Exception as e:
            results["instagram"] = {"status": "error", "message": str(e)}
            log(f"  ❌ Instagram: {e}", "ERROR")

    save_post_results(diary_path, results)
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date",    default=None)
    parser.add_argument("--sns",     default="instagram",
                        choices=["instagram","x","pinterest","all"])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    target_date = args.date or date.today().isoformat()

    log("="*55)
    log(f"🏠 架空間取り図パイプライン開始")
    log(f"   日付: {target_date}  DRY: {args.dry_run}")
    log("="*55)

    results = {}
    try:
        diary_path         = step1_generate_prompts(target_date)
        results["prompts"] = {"status": "success", "path": diary_path}

        ok                 = step2_generate_images(diary_path)
        results["images"]  = {"status": "success" if ok else "partial"}

        post_res           = step3_post_sns(diary_path, args.sns, args.dry_run)
        results["post"]    = post_res

    except Exception as e:
        log(f"❌ エラー: {e}", "ERROR")
        log(traceback.format_exc(), "ERROR")
        sys.exit(1)

    log("="*55)
    log("✅ 全パイプライン完了!")
    for step, r in results.items():
        st   = r.get("status", "?")
        icon = "✅" if st in ("success","True") else ("⏭️" if "dry" in str(r) else "⚠️")
        log(f"   {icon} {step}: {st}")
    log("="*55)


if __name__ == "__main__":
    main()