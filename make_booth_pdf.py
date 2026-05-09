"""
make_booth_pdf.py - Booth販売用 架空間取り図集PDF生成
"""

import json
import argparse
from pathlib import Path
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white, black
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image as RLImage,
    PageBreak, Table, TableStyle
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image as PILImage
import platform

# ── フォント ──────────────────────────────
def setup_font():
    candidates = {
        "Windows": [r"C:\Windows\Fonts\YuGothM.ttc",
                    r"C:\Windows\Fonts\meiryo.ttc",
                    r"C:\Windows\Fonts\msgothic.ttc"],
        "Darwin":  ["/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc"],
        "Linux":   ["/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"],
    }.get(platform.system(), [])
    for path in candidates:
        if Path(path).exists():
            try:
                pdfmetrics.registerFont(TTFont("JP", path))
                return "JP"
            except Exception:
                continue
    return "Helvetica"

FONT = setup_font()

# ── カラー ────────────────────────────────
C_BG     = HexColor("#FAFAF8")
C_DARK   = HexColor("#1A1A18")
C_ACCENT = HexColor("#1558A0")
C_ACCENT2= HexColor("#534AB7")
C_LIGHT  = HexColor("#E6F1FB")
C_MUTED  = HexColor("#888888")
C_BORDER = HexColor("#E4E0DA")

W, H = A4  # 595 x 842 pt

# ── 使用可能な描画幅・高さ（マージン考慮）─
MARGIN_L = 15*mm
MARGIN_R = 15*mm
MARGIN_T = 18*mm
MARGIN_B = 18*mm
USABLE_W = W - MARGIN_L - MARGIN_R   # 約165mm
USABLE_H = H - MARGIN_T - MARGIN_B   # 約257mm


# ── 画像サイズ計算（はみ出さないように）──
def fit_image(img_path, max_w_pt, max_h_pt):
    """アスペクト比を保ってmax内に収めたpt単位サイズを返す"""
    try:
        with PILImage.open(img_path) as img:
            iw, ih = img.size
    except Exception:
        return max_w_pt * 0.8, max_h_pt * 0.8
    ratio = min(max_w_pt / iw, max_h_pt / ih)
    return iw * ratio, ih * ratio


# ══════════════════════════════════════════
# ページ装飾
# ══════════════════════════════════════════
class PageDecorator:
    def __init__(self, title, total_pages):
        self.title       = title
        self.total_pages = total_pages
        self._page       = 0

    def __call__(self, c, doc):
        self._page += 1
        c.saveState()
        if self._page > 2:  # 表紙・目次はヘッダーなし
            c.setStrokeColor(C_ACCENT)
            c.setLineWidth(1.5)
            c.line(MARGIN_L, H - 12*mm, W - MARGIN_R, H - 12*mm)
            c.setFont(FONT, 8)
            c.setFillColor(C_MUTED)
            c.drawString(MARGIN_L, H - 9*mm, self.title)

        c.setStrokeColor(C_BORDER)
        c.setLineWidth(0.5)
        c.line(MARGIN_L, 14*mm, W - MARGIN_R, 14*mm)
        c.setFont(FONT, 8)
        c.setFillColor(C_MUTED)
        c.drawRightString(W - MARGIN_R, 9*mm,
                          f"{self._page} / {self.total_pages}")
        c.drawString(MARGIN_L, 9*mm,
                     "© AI架空建築研究所  複製・再配布禁止")
        c.restoreState()


# ══════════════════════════════════════════
# データ収集
# ══════════════════════════════════════════
def collect_entries(image_dir: Path, diary_dir: Path) -> list:
    entries = []
    for date_dir in sorted(image_dir.iterdir()):
        if not date_dir.is_dir():
            continue
        imgs = sorted(date_dir.glob("*.png"))
        if not imgs:
            continue
        json_path = diary_dir / f"{date_dir.name}.json"
        meta = {}
        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            concept = data.get("concept", {})
            meta = {
                "theme":    concept.get("theme",    "架空の世界"),
                "shape":    concept.get("shape",    ""),
                "resident": concept.get("resident", ""),
                "story":    concept.get("story",    ""),
                "caption":  data.get("captions", {}).get("instagram", ""),
            }
        entries.append({
            "date":   date_dir.name,
            "images": [str(p) for p in imgs],
            "meta":   meta,
        })
    return entries


# ══════════════════════════════════════════
# 表紙（全面画像）
# ══════════════════════════════════════════
def draw_cover_page(c, book_title, subtitle, entry_count, cover_img_path):
    """全面画像の表紙を直接描画"""
    c.saveState()

    if cover_img_path and Path(cover_img_path).exists():
        # 画像をページ全体に引き伸ばす（クロップ）
        try:
            with PILImage.open(cover_img_path) as img:
                iw, ih = img.size
            # ページ全体を覆うスケール
            scale = max(W / iw, H / ih)
            draw_w = iw * scale
            draw_h = ih * scale
            x_off  = (W - draw_w) / 2
            y_off  = (H - draw_h) / 2
            c.drawImage(cover_img_path, x_off, y_off,
                        width=draw_w, height=draw_h,
                        preserveAspectRatio=False)
        except Exception:
            # 画像読み込み失敗時はグラデーション背景
            c.setFillColor(C_ACCENT)
            c.rect(0, 0, W, H, fill=1, stroke=0)
    else:
        c.setFillColor(C_ACCENT)
        c.rect(0, 0, W, H, fill=1, stroke=0)

    # 半透明オーバーレイ（下部グラデーション風）
    c.setFillColor(HexColor("#000000"))
    c.setFillAlpha(0.55)
    c.rect(0, 0, W, H * 0.45, fill=1, stroke=0)
    c.setFillAlpha(0.25)
    c.rect(0, H * 0.45, W, H * 0.55, fill=1, stroke=0)

    # タイトル（下部）
    c.setFillAlpha(1.0)
    c.setFillColor(white)
    c.setFont(FONT, 30)
    c.drawCentredString(W/2, 85*mm, book_title)

    c.setFont(FONT, 12)
    c.setFillColor(HexColor("#B5D4F4"))
    c.drawCentredString(W/2, 73*mm, subtitle)

    # 細い区切り線
    c.setStrokeColor(white)
    c.setStrokeAlpha(0.5)
    c.setLineWidth(0.5)
    c.line(W/2 - 35*mm, 68*mm, W/2 + 35*mm, 68*mm)
    c.setStrokeAlpha(1.0)

    c.setFont(FONT, 9)
    c.setFillColor(HexColor("#CCCCCC"))
    c.drawCentredString(W/2, 60*mm, f"{entry_count} 邸の架空住居を収録")

    # 発行情報
    now = datetime.now().strftime("%Y年%m月")
    c.setFont(FONT, 7)
    c.setFillColor(HexColor("#AAAAAA"))
    c.drawCentredString(W/2, 22*mm, f"AI架空建築研究所  {now}発行")
    c.drawCentredString(W/2, 17*mm, "本書の無断複製・転載を禁じます")

    c.restoreState()


# ══════════════════════════════════════════
# 目次
# ══════════════════════════════════════════
def build_toc(story, entries):
    s_h = ParagraphStyle("toc_h", fontName=FONT, fontSize=18,
                          textColor=C_DARK, spaceAfter=6*mm, alignment=TA_CENTER)
    s_i = ParagraphStyle("toc_i", fontName=FONT, fontSize=10,
                          textColor=C_DARK, spaceBefore=2*mm, leftIndent=5*mm)
    s_s = ParagraphStyle("toc_s", fontName=FONT, fontSize=8,
                          textColor=C_MUTED, leftIndent=12*mm)

    story.append(Spacer(1, 10*mm))
    story.append(Paragraph("目  次", s_h))
    story.append(Spacer(1, 4*mm))
    for i, e in enumerate(entries, 1):
        theme = e["meta"].get("theme","架空の世界")
        shape = e["meta"].get("shape","")
        story.append(Paragraph(f"第{i}邸　{theme}　— {shape}", s_i))
        res = e["meta"].get("resident","")
        if res:
            story.append(Paragraph(
                (res[:45]+"...") if len(res)>45 else res, s_s))
    story.append(PageBreak())


# ══════════════════════════════════════════
# 各邸
# ══════════════════════════════════════════
def build_entry(story, entry, index):
    meta    = entry["meta"]
    images  = entry["images"]
    theme   = meta.get("theme","架空の世界")
    shape   = meta.get("shape","")
    resident= meta.get("resident","")
    story_t = meta.get("story","")
    caption = meta.get("caption","")

    s_num  = ParagraphStyle("num",  fontName=FONT, fontSize=9,
                             textColor=C_ACCENT, spaceAfter=1*mm)
    s_th   = ParagraphStyle("th",   fontName=FONT, fontSize=18,
                             textColor=C_DARK,   spaceAfter=2*mm, leading=24)
    s_sh   = ParagraphStyle("sh",   fontName=FONT, fontSize=10,
                             textColor=C_ACCENT2,spaceAfter=3*mm)
    s_lbl  = ParagraphStyle("lbl",  fontName=FONT, fontSize=8,
                             textColor=C_MUTED,  spaceBefore=2*mm, spaceAfter=1*mm)
    s_body = ParagraphStyle("body", fontName=FONT, fontSize=9,
                             textColor=C_DARK,   leading=14, spaceAfter=2*mm)

    # ── ページ1: 間取り図 ──
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph(f"第 {index} 邸", s_num))
    story.append(Paragraph(theme, s_th))
    story.append(Paragraph(f"建築様式: {shape}", s_sh))

    fp_imgs = [p for p in images if Path(p).name.startswith("00_")]
    if fp_imgs:
        iw, ih = fit_image(fp_imgs[0], USABLE_W, 110*mm)
        story.append(RLImage(fp_imgs[0], width=iw, height=ih, hAlign="CENTER"))
        story.append(Paragraph("▲ 間取り図（俯瞰）", s_lbl))

    if resident:
        story.append(Spacer(1, 2*mm))
        story.append(Paragraph("【住人設定】", s_lbl))
        story.append(Paragraph(resident, s_body))
    if story_t:
        story.append(Paragraph("【この家の物語】", s_lbl))
        story.append(Paragraph(story_t, s_body))

    story.append(PageBreak())

    # ── ページ2: 外観・内観 ──
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph(f"第 {index} 邸　— 外観・内観", s_num))
    story.append(Paragraph(theme, s_th))

    ext_imgs = [p for p in images if Path(p).name.startswith("01_")]
    int_imgs = [p for p in images if Path(p).name.startswith("02_")]

    img_max_h = 95*mm

    if ext_imgs:
        iw, ih = fit_image(ext_imgs[0], USABLE_W, img_max_h)
        story.append(RLImage(ext_imgs[0], width=iw, height=ih, hAlign="CENTER"))
        story.append(Paragraph("▲ 外観", s_lbl))
        story.append(Spacer(1, 3*mm))

    if int_imgs:
        iw, ih = fit_image(int_imgs[0], USABLE_W, img_max_h)
        story.append(RLImage(int_imgs[0], width=iw, height=ih, hAlign="CENTER"))
        story.append(Paragraph("▲ メインルーム内観", s_lbl))

    if caption:
        short = (caption[:120]+"...") if len(caption)>120 else caption
        story.append(Spacer(1, 2*mm))
        story.append(Paragraph(short, s_body))

    story.append(PageBreak())


# ══════════════════════════════════════════
# 奥付
# ══════════════════════════════════════════
def build_afterword(story, entry_count, book_title):
    s_h = ParagraphStyle("aw_h", fontName=FONT, fontSize=16,
                          textColor=C_DARK, spaceAfter=6*mm, alignment=TA_CENTER)
    s_b = ParagraphStyle("aw_b", fontName=FONT, fontSize=9,
                          textColor=C_DARK, leading=16, spaceAfter=4*mm)

    story.append(Spacer(1, 15*mm))
    story.append(Paragraph("あとがき", s_h))
    story.append(Paragraph(
        f"本書には、AIが生成した {entry_count} 邸の架空住居の間取り図・外観・内観を収録しています。"
        "これらはすべて実在しない世界の、実在しない家です。"
        "それぞれに住人がいて、物語があります。", s_b))
    story.append(Paragraph(
        "TRPG・小説・漫画・ゲームの世界観制作や、"
        "「ありえたかもしれない家」を眺めるための資料として、"
        "ご活用いただければ幸いです。", s_b))

    story.append(Spacer(1, 20*mm))
    now = datetime.now().strftime("%Y年%m月")
    data = [
        ["書名",     book_title],
        ["発行",     now],
        ["制作",     "AI架空建築研究所"],
        ["生成AI",   "Claude (Anthropic) / DALL-E 3 (OpenAI)"],
        ["収録数",   f"{entry_count} 邸"],
        ["注意事項", "本書の画像・テキストの無断転載・商用利用を禁じます"],
    ]
    t = Table(data, colWidths=[35*mm, 120*mm])
    t.setStyle(TableStyle([
        ("FONTNAME",     (0,0),(-1,-1), FONT),
        ("FONTSIZE",     (0,0),(-1,-1), 8),
        ("TEXTCOLOR",    (0,0),(0,-1),  C_MUTED),
        ("TEXTCOLOR",    (1,0),(1,-1),  C_DARK),
        ("LINEBELOW",    (0,0),(-1,-2), 0.3, C_BORDER),
        ("TOPPADDING",   (0,0),(-1,-1), 4),
        ("BOTTOMPADDING",(0,0),(-1,-1), 4),
    ]))
    story.append(t)


# ══════════════════════════════════════════
# メイン
# ══════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--title",    default="架空世界の間取り図集 Vol.1")
    parser.add_argument("--subtitle", default="実在しない世界の、実在しない家。")
    parser.add_argument("--output",   default=None)
    parser.add_argument("--image-dir",default="output/floorplan_images")
    parser.add_argument("--diary-dir",default="output/floorplan_diary")
    args = parser.parse_args()

    image_dir = Path(args.image_dir)
    diary_dir = Path(args.diary_dir)

    print(f"\n📚 Booth販売用PDF生成")
    print(f"   タイトル: {args.title}")

    entries = collect_entries(image_dir, diary_dir)
    print(f"   収録邸数: {len(entries)} 邸")
    if not entries:
        print("❌ 画像が見つかりません"); return

    out_dir  = Path("output/booth")
    out_dir.mkdir(parents=True, exist_ok=True)
    safe     = args.title.replace(" ","_").replace("/","_")
    out_path = Path(args.output) if args.output else out_dir / f"{safe}.pdf"

    # 表紙用画像: 最初の邸の外観(01_)を使用
    cover_img = None
    for e in entries:
        ext = [p for p in e["images"] if Path(p).name.startswith("01_")]
        if ext:
            cover_img = ext[0]
            break

    # ページ数概算: 表紙1 + 目次1 + 邸×2 + 奥付1
    total_pages = 2 + len(entries) * 2 + 1
    decorator   = PageDecorator(args.title, total_pages)

    doc = SimpleDocTemplate(
        str(out_path), pagesize=A4,
        leftMargin=MARGIN_L, rightMargin=MARGIN_R,
        topMargin=MARGIN_T,  bottomMargin=MARGIN_B,
        title=args.title, author="AI架空建築研究所",
    )

    # ── 表紙は onFirstPage で直接描画 ──
    def first_page(c, doc):
        draw_cover_page(c, args.title, args.subtitle,
                        len(entries), cover_img)
        # ページ番号だけ付与
        decorator._page += 1

    story = []
    story.append(PageBreak())   # 表紙の後に改ページ

    # 目次
    build_toc(story, entries)

    # 各邸
    for i, entry in enumerate(entries, 1):
        print(f"   [{i}/{len(entries)}] {entry['meta'].get('theme','?')}")
        build_entry(story, entry, i)

    # 奥付
    build_afterword(story, len(entries), args.title)

    print(f"\n   📄 PDF生成中...")
    doc.build(story, onFirstPage=first_page, onLaterPages=decorator)

    size_mb = out_path.stat().st_size / 1024 / 1024
    print(f"\n✅ PDF生成完了!")
    print(f"   保存先: {out_path}")
    print(f"   サイズ: {size_mb:.1f} MB  /  収録: {len(entries)} 邸")
    print(f"\n📦 Boothへの出品:")
    print(f"   1. https://booth.pm → 「商品を追加」→ デジタルコンテンツ")
    print(f"   2. 価格: ¥500〜¥800 推奨")
    print(f"   3. タグ: 架空建築, 間取り図, ファンタジー, TRPG素材")

if __name__ == "__main__":
    main()