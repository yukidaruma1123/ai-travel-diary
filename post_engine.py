"""
post_engine.py
─────────────────────────────────────────────
プロジェクト #5: 架空の街・歴史 AI旅日記
Step 4: SNS自動投稿エンジン

対応SNS:
    Instagram  (Meta Graph API)
    X/Twitter  (Twitter API v2)
    Pinterest  (Pinterest API v5)

使い方:
    python post_engine.py
    python post_engine.py --diary output/diary/2025-04-30.json
    python post_engine.py --diary output/diary/2025-04-30.json --sns instagram
    python post_engine.py --diary output/diary/2025-04-30.json --sns all

出力:
    投稿済みの投稿IDを日記JSONに書き戻す
"""

import os
import sys
import json
import time
import argparse
import mimetypes
import requests
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()


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


def get_image_paths(diary: dict) -> list[str]:
    """日記JSONから生成済み画像パスを取得"""
    prompts = diary.get("diary", {}).get("image_prompts", [])
    paths = []
    for p in prompts:
        img = p.get("generated_image")
        if img and Path(img).exists():
            paths.append(img)
    return paths


# ──────────────────────────────────────────
# キャプション・ハッシュタグ組み立て
# ──────────────────────────────────────────
def build_instagram_caption(diary: dict) -> str:
    d = diary.get("diary", {})
    caption   = d.get("caption_instagram", d.get("caption_x", ""))
    tags_jp   = d.get("hashtags_jp", [])
    tags_en   = d.get("hashtags_en", [])
    hashtags  = " ".join(tags_jp + tags_en)
    return f"{caption}\n\n{hashtags}"


def build_x_caption(diary: dict) -> str:
    d = diary.get("diary", {})
    caption  = d.get("caption_x", "")
    tags_jp  = d.get("hashtags_jp", [])
    tags_en  = d.get("hashtags_en", [])
    hashtags = " ".join(tags_jp[:3] + tags_en[:2])  # X は文字数制限あり
    text     = f"{caption}\n\n{hashtags}"
    return text[:280]  # X の上限


def build_pinterest_description(diary: dict) -> str:
    d = diary.get("diary", {})
    text     = d.get("text_jp", "")[:400]
    tags_jp  = d.get("hashtags_jp", [])
    tags_en  = d.get("hashtags_en", [])
    hashtags = " ".join(tags_jp + tags_en)
    return f"{text}\n\n{hashtags}"


# ──────────────────────────────────────────
# Instagram 投稿
# ──────────────────────────────────────────
class InstagramPoster:
    """
    Meta Graph API を使ったInstagram投稿
    必要な環境変数:
        META_ACCESS_TOKEN         — ユーザーアクセストークン
        META_INSTAGRAM_ACCOUNT_ID — InstagramビジネスアカウントID
    """

    def __init__(self):
        self.access_token  = os.environ.get("META_ACCESS_TOKEN")
        self.account_id    = os.environ.get("META_INSTAGRAM_ACCOUNT_ID")
        self.base_url      = "https://graph.facebook.com/v19.0"

        if not self.access_token or not self.account_id:
            raise EnvironmentError(
                "META_ACCESS_TOKEN と META_INSTAGRAM_ACCOUNT_ID を .env に設定してください\n"
                "取得手順: https://developers.facebook.com/docs/instagram-api/getting-started"
            )

    def _upload_image_to_imgbb(self, image_path: str) -> str:
        """
        Instagram Graph APIは公開URLの画像しか受け付けないため
        imgbb (無料) に一時アップロードして公開URLを取得する
        環境変数: IMGBB_API_KEY
        """
        imgbb_key = os.environ.get("IMGBB_API_KEY")
        if not imgbb_key:
            raise EnvironmentError(
                "IMGBB_API_KEY が設定されていません\n"
                "取得先 (無料): https://api.imgbb.com/"
            )

        with open(image_path, "rb") as f:
            import base64
            b64 = base64.b64encode(f.read()).decode()

        resp = requests.post(
            "https://api.imgbb.com/1/upload",
            data={"key": imgbb_key, "image": b64},
            timeout=60,
        )
        resp.raise_for_status()
        url = resp.json()["data"]["url"]
        print(f"      📤 画像アップロード完了: {url[:60]}...")
        return url

    def post_single(self, image_path: str, caption: str) -> str:
        """1枚の画像を投稿 → 投稿IDを返す"""
        print("  📸 Instagram: 画像をアップロード中...")
        image_url = self._upload_image_to_imgbb(image_path)

        # Step1: メディアオブジェクト作成
        print("  📸 Instagram: メディアオブジェクト作成中...")
        resp = requests.post(
            f"{self.base_url}/{self.account_id}/media",
            params={
                "image_url":    image_url,
                "caption":      caption,
                "access_token": self.access_token,
            },
            timeout=60,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"メディア作成失敗: {resp.text[:200]}")

        creation_id = resp.json()["id"]

        # Step2: 公開
        print("  📸 Instagram: 投稿を公開中...")
        time.sleep(3)  # 処理待ち
        resp = requests.post(
            f"{self.base_url}/{self.account_id}/media_publish",
            params={
                "creation_id":  creation_id,
                "access_token": self.access_token,
            },
            timeout=60,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"公開失敗: {resp.text[:200]}")

        post_id = resp.json()["id"]
        print(f"  ✅ Instagram 投稿完了! ID: {post_id}")
        return post_id

    def post_carousel(self, image_paths: list[str], caption: str) -> str:
        """複数画像をカルーセル投稿 → 投稿IDを返す"""
        print(f"  📸 Instagram: カルーセル投稿 ({len(image_paths)}枚)")

        # 各画像のメディアIDを取得
        children_ids = []
        for i, path in enumerate(image_paths[:10]):  # Instagram上限10枚
            print(f"      画像 {i+1}/{len(image_paths)} をアップロード中...")
            image_url = self._upload_image_to_imgbb(path)

            resp = requests.post(
                f"{self.base_url}/{self.account_id}/media",
                params={
                    "image_url":    image_url,
                    "is_carousel_item": "true",
                    "access_token": self.access_token,
                },
                timeout=60,
            )
            if resp.status_code != 200:
                print(f"      ⚠️  画像{i+1}スキップ: {resp.text[:100]}")
                continue
            children_ids.append(resp.json()["id"])
            time.sleep(2)

        if not children_ids:
            raise RuntimeError("有効な画像がありませんでした")

        # カルーセルコンテナ作成
        resp = requests.post(
            f"{self.base_url}/{self.account_id}/media",
            params={
                "media_type":   "CAROUSEL",
                "children":     ",".join(children_ids),
                "caption":      caption,
                "access_token": self.access_token,
            },
            timeout=60,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"カルーセル作成失敗: {resp.text[:200]}")

        container_id = resp.json()["id"]

        # 公開
        time.sleep(3)
        resp = requests.post(
            f"{self.base_url}/{self.account_id}/media_publish",
            params={
                "creation_id":  container_id,
                "access_token": self.access_token,
            },
            timeout=60,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"公開失敗: {resp.text[:200]}")

        post_id = resp.json()["id"]
        print(f"  ✅ Instagram カルーセル投稿完了! ID: {post_id}")
        return post_id


# ──────────────────────────────────────────
# X (Twitter) 投稿
# ──────────────────────────────────────────
class XPoster:
    """
    Twitter API v2 を使った X 投稿
    必要な環境変数:
        X_API_KEY
        X_API_SECRET
        X_ACCESS_TOKEN
        X_ACCESS_TOKEN_SECRET
    """

    def __init__(self):
        try:
            import tweepy
        except ImportError:
            raise ImportError("pip install tweepy を実行してください")

        api_key    = os.environ.get("X_API_KEY")
        api_secret = os.environ.get("X_API_SECRET")
        token      = os.environ.get("X_ACCESS_TOKEN")
        token_sec  = os.environ.get("X_ACCESS_TOKEN_SECRET")

        if not all([api_key, api_secret, token, token_sec]):
            raise EnvironmentError(
                "X_API_KEY / X_API_SECRET / X_ACCESS_TOKEN / X_ACCESS_TOKEN_SECRET\n"
                "を .env に設定してください\n"
                "取得先: https://developer.twitter.com/en/portal/dashboard"
            )

        self.client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=token,
            access_token_secret=token_sec,
        )
        # v1.1 (画像アップロード用)
        auth = tweepy.OAuth1UserHandler(api_key, api_secret, token, token_sec)
        self.api_v1 = tweepy.API(auth)

    def post(self, text: str, image_path: str = None) -> str:
        print("  🐦 X: 投稿中...")
        media_ids = []

        if image_path and Path(image_path).exists():
            print("  🐦 X: 画像をアップロード中...")
            media = self.api_v1.media_upload(filename=image_path)
            media_ids.append(media.media_id)

        resp = self.client.create_tweet(
            text=text,
            media_ids=media_ids if media_ids else None,
        )
        post_id = str(resp.data["id"])
        print(f"  ✅ X 投稿完了! ID: {post_id}")
        return post_id


# ──────────────────────────────────────────
# Pinterest 投稿
# ──────────────────────────────────────────
class PinterestPoster:
    """
    Pinterest API v5 を使ったピン作成
    必要な環境変数:
        PINTEREST_ACCESS_TOKEN
        PINTEREST_BOARD_ID
    """

    def __init__(self):
        self.access_token = os.environ.get("PINTEREST_ACCESS_TOKEN")
        self.board_id     = os.environ.get("PINTEREST_BOARD_ID")

        if not self.access_token or not self.board_id:
            raise EnvironmentError(
                "PINTEREST_ACCESS_TOKEN と PINTEREST_BOARD_ID を .env に設定してください\n"
                "取得先: https://developers.pinterest.com/docs/getting-started/authentication/"
            )

    def post(self, image_path: str, title: str, description: str,
             link: str = None) -> str:
        print("  📌 Pinterest: ピンを作成中...")

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type":  "application/json",
        }

        # 画像をbase64でアップロード
        with open(image_path, "rb") as f:
            import base64
            b64 = base64.b64encode(f.read()).decode()

        payload = {
            "board_id":   self.board_id,
            "title":      title[:100],
            "description": description[:500],
            "media_source": {
                "source_type": "image_base64",
                "content_type": "image/png",
                "data": b64,
            },
        }
        if link:
            payload["link"] = link

        resp = requests.post(
            "https://api.pinterest.com/v5/pins",
            headers=headers,
            json=payload,
            timeout=60,
        )

        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Pinterest投稿失敗: {resp.status_code} {resp.text[:200]}")

        post_id = resp.json()["id"]
        print(f"  ✅ Pinterest 投稿完了! ID: {post_id}")
        return post_id


# ──────────────────────────────────────────
# 投稿結果を日記JSONに書き戻す
# ──────────────────────────────────────────
def save_post_results(diary_path: str, results: dict):
    with open(diary_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "_post_results" not in data:
        data["_post_results"] = {}

    data["_post_results"].update({
        **results,
        "posted_at": datetime.now().isoformat(),
    })

    with open(diary_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n  💾 投稿結果を日記JSONに保存しました")


# ──────────────────────────────────────────
# メイン処理
# ──────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="SNS自動投稿エンジン")
    parser.add_argument("--diary", default=None)
    parser.add_argument(
        "--sns",
        default="instagram",
        choices=["instagram", "x", "pinterest", "all"],
        help="投稿先SNS (instagram / x / pinterest / all)",
    )
    args = parser.parse_args()

    diary_path = args.diary or str(get_latest_diary())
    print(f"\n📤 SNS自動投稿エンジン起動")
    print(f"   日記JSON : {diary_path}")
    print(f"   投稿先   : {args.sns}\n")

    diary       = load_diary(diary_path)
    diary_data  = diary.get("diary", {})
    image_paths = get_image_paths(diary)

    if not image_paths:
        print("❌ 生成済み画像が見つかりません")
        print("   先に image_engine.py を実行してください")
        sys.exit(1)

    print(f"  🖼️  使用画像: {len(image_paths)} 枚")
    for p in image_paths:
        print(f"      {p}")
    print()

    results     = {}
    sns_targets = (
        ["instagram", "x", "pinterest"] if args.sns == "all"
        else [args.sns]
    )

    # ── Instagram ──
    if "instagram" in sns_targets:
        try:
            poster  = InstagramPoster()
            caption = build_instagram_caption(diary)

            if len(image_paths) >= 2:
                post_id = poster.post_carousel(image_paths, caption)
            else:
                post_id = poster.post_single(image_paths[0], caption)

            results["instagram"] = {"post_id": post_id, "status": "success"}
        except Exception as e:
            print(f"  ❌ Instagram エラー: {e}")
            results["instagram"] = {"status": "error", "message": str(e)}

    # ── X ──
    if "x" in sns_targets:
        try:
            poster  = XPoster()
            text    = build_x_caption(diary)
            post_id = poster.post(text, image_paths[0] if image_paths else None)
            results["x"] = {"post_id": post_id, "status": "success"}
        except Exception as e:
            print(f"  ❌ X エラー: {e}")
            results["x"] = {"status": "error", "message": str(e)}

    # ── Pinterest ──
    if "pinterest" in sns_targets:
        try:
            poster      = PinterestPoster()
            title       = f"{diary_data.get('location_name', '架空の旅')} — {diary_data.get('region_name', '')}"
            description = build_pinterest_description(diary)
            post_id     = poster.post(image_paths[0], title, description)
            results["pinterest"] = {"post_id": post_id, "status": "success"}
        except Exception as e:
            print(f"  ❌ Pinterest エラー: {e}")
            results["pinterest"] = {"status": "error", "message": str(e)}

    # 結果保存
    save_post_results(diary_path, results)

    # サマリー
    print("\n" + "="*55)
    print("📤 SNS投稿 完了!")
    print("="*55)
    for sns, result in results.items():
        status = "✅ 成功" if result["status"] == "success" else "❌ 失敗"
        detail = result.get("post_id", result.get("message", ""))
        print(f"  {sns:12}: {status}  {detail}")
    print("="*55)
    print(f"\n✅ 次のステップ: GitHub Actionsで完全自動化しましょう!")
    print(f"   python orchestrator.py でパイプライン全体を一括実行できます")


if __name__ == "__main__":
    main()