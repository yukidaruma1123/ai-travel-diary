"""
floorplan_engine.py - 間取り図自動生成エンジン
スマホ最適化版 (1080x1080px Instagram正方形)
"""
import random
from dataclasses import dataclass, field
from pathlib import Path
from datetime import date
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib import font_manager as _fm

# ── 日本語フォント自動検出 ────────────────
def _setup_japanese_font():
    import platform
    os_name = platform.system()
    candidates = []
    if os_name == "Windows":
        candidates = [
            r"C:\Windows\Fonts\YuGothM.ttc",
            r"C:\Windows\Fonts\meiryo.ttc",
            r"C:\Windows\Fonts\msgothic.ttc",
        ]
    elif os_name == "Darwin":
        candidates = [
            "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
        ]
    else:
        candidates = [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        ]
    for path in candidates:
        if Path(path).exists():
            _fm.fontManager.addfont(path)
            prop = _fm.FontProperties(fname=path)
            matplotlib.rcParams["font.family"] = prop.get_name()
            matplotlib.rcParams["axes.unicode_minus"] = False
            return prop.get_name()
    for f in _fm.fontManager.ttflist:
        if any(k in f.name for k in ["Gothic","Meiryo","Yu ","Noto","Hiragino","IPAex"]):
            matplotlib.rcParams["font.family"] = f.name
            matplotlib.rcParams["axes.unicode_minus"] = False
            return f.name
    return None

_JP_FONT = _setup_japanese_font()

# ── データ定義 ────────────────────────────
@dataclass
class Room:
    name: str
    x: float; y: float; w: float; h: float

@dataclass
class FloorPlan:
    title: str
    rooms: list
    total_area: float
    style: str
    mode: str
    notes: list = field(default_factory=list)

# ── カラーパレット ────────────────────────
PALETTES = {
    "modern":   {"bg":"#F8F8F6","wall":"#1E1E1C","accent":"#1A5FA8",
                 "sub":"#555555","grid":"#E0DDD8","door":"#999999"},
    "nordic":   {"bg":"#F5F7F4","wall":"#2A2E28","accent":"#0D6650",
                 "sub":"#4A5248","grid":"#DEE2DC","door":"#8A9088"},
    "japanese": {"bg":"#F7F4EF","wall":"#3A2A1E","accent":"#8B3012",
                 "sub":"#5A4A3A","grid":"#EAE4DA","door":"#A09080"},
    "fantasy":  {"bg":"#F2F0FA","wall":"#2E2880","accent":"#4A42B0",
                 "sub":"#3A3478","grid":"#D8D4F0","door":"#7870CC"},
    "scifi":    {"bg":"#EEF4FA","wall":"#02254A","accent":"#1258A0",
                 "sub":"#2A4A70","grid":"#C8DCF0","door":"#3878CC"},
}

ROOM_COLORS = {
    "modern": {
        "LDK":"#E8EEF5","寝室":"#F2EDE8","洗面":"#E5F0F3","浴室":"#DDE8F0",
        "トイレ":"#EDE9E4","玄関":"#E4E0DB","バルコニー":"#E4EDE0",
        "収納":"#EAE7E2","書斎":"#E8ECF0","子供部屋":"#F0E8EE",
        "子供部屋A":"#F0E8EE","子供部屋B":"#E8EEF0","廊下":"#ECEAE6",
    },
    "nordic": {
        "LDK":"#E8F0E8","寝室":"#EDE8E2","洗面":"#E2EDE8","浴室":"#DDE8EC",
        "トイレ":"#E8E5E0","玄関":"#E3E0DA","バルコニー":"#E0EAD8",
        "収納":"#E8E5E0","書斎":"#E5EAE8","子供部屋":"#EDE8E2",
        "子供部屋A":"#EDE8E2","子供部屋B":"#E5E8ED","廊下":"#E8E6E2",
    },
    "japanese": {
        "LDK":"#F0E8D8","寝室":"#EDE4D4","洗面":"#E2EDE6","浴室":"#DAE6EE",
        "トイレ":"#EAE2D6","玄関":"#E6DDD0","バルコニー":"#E4EAD8",
        "収納":"#E6DDD0","書斎":"#EEE8D8","子供部屋":"#EEE0D8",
        "子供部屋A":"#EEE0D8","子供部屋B":"#E8EED8","廊下":"#EAE2D4",
    },
    "fantasy": {
        "LDK":"#DDD8F5","寝室":"#E5D8F5","洗面":"#D8E5F5","浴室":"#D2DFF0",
        "トイレ":"#DDD8F0","玄関":"#D8D4EC","バルコニー":"#D4ECE4",
        "収納":"#DDD8EC","書斎":"#D8DCF5","子供部屋":"#EDD8F5",
        "子供部屋A":"#EDD8F5","子供部屋B":"#D8EDF5","廊下":"#DAD8EE",
        "大広間":"#D4D0F2","門の間":"#DAD6EE","賢者の書斎":"#D0DDF5",
        "錬金術室":"#DDD0EC","秘密の間":"#EED0EE","水晶の間":"#D0EEF5",
        "隠し通路":"#D8D8EC","観測台":"#D0EEDC",
        "エアロック":"#D0DDF0","コモンエリア":"#D4DDF5",
        "個室A":"#DDD0F5","個室B":"#D0EEF5",
        "水再生室":"#D0EEF2","医療ポッド":"#DEECD0",
        "動力炉室":"#EEDDD0","観測デッキ":"#D0EEE8",
    },
    "scifi": {
        "LDK":"#D4E8F5","寝室":"#D8EEF5","洗面":"#CDF0F5","浴室":"#C8EEF5",
        "トイレ":"#D4E4F2","玄関":"#CDE0EE","バルコニー":"#C8EEE0",
        "収納":"#CDE0EE","書斎":"#D4E8F5","子供部屋":"#DDDDF5",
        "子供部屋A":"#DDDDF5","子供部屋B":"#D8EEF5","廊下":"#CDE0F2",
        "エアロック":"#C8E2EE","コモンエリア":"#CEE0F5",
        "個室A":"#D4D0F5","個室B":"#CEEEF5",
        "水再生室":"#C8EEF2","医療ポッド":"#D4EED0",
        "動力炉室":"#EED8D0","観測デッキ":"#C8EEE4",
    },
}

# ── 間取りパターン ────────────────────────
def make_1ldk(style, mode):
    rooms = [
        Room("玄関",      0.0, 0.0, 2.0, 1.5),
        Room("LDK",       0.0, 1.5, 5.5, 3.5),
        Room("寝室",      5.5, 0.0, 3.0, 3.5),
        Room("洗面",      0.0, 5.0, 2.5, 1.5),
        Room("浴室",      2.5, 5.0, 2.0, 1.5),
        Room("トイレ",    4.5, 5.0, 1.5, 1.5),
        Room("収納",      6.0, 3.5, 2.5, 1.5),
        Room("バルコニー", 0.0, -1.5, 5.5, 1.5),
    ]
    return FloorPlan("1LDK" if mode=="real" else "居室+広間", rooms,
                     45.0, style, mode,
                     ["洋室 1", "LDK 18.5帖", "南向きバルコニー"])

def make_2ldk(style, mode):
    rooms = [
        Room("玄関",      0.0, 0.0, 2.0, 1.5),
        Room("廊下",      2.0, 0.0, 1.5, 4.0),
        Room("LDK",       0.0, 1.5, 5.5, 4.0),
        Room("寝室",      5.5, 0.0, 3.0, 3.0),
        Room("子供部屋",  5.5, 3.0, 3.0, 2.5),
        Room("洗面",      3.5, 4.5, 2.0, 2.0),
        Room("浴室",      3.5, 6.5, 2.0, 1.5),
        Room("トイレ",    5.5, 5.5, 1.5, 1.5),
        Room("収納",      7.0, 5.5, 1.5, 2.5),
        Room("バルコニー", 0.0, -1.5, 5.5, 1.5),
    ]
    return FloorPlan("2LDK" if mode=="real" else "二間続き", rooms,
                     62.0, style, mode,
                     ["洋室x2", "LDK 20帖", "全居室収納付き"])

def make_3ldk(style, mode):
    rooms = [
        Room("玄関",      0.0, 0.0, 2.5, 1.8),
        Room("廊下",      2.5, 0.0, 1.5, 5.5),
        Room("LDK",       0.0, 1.8, 5.5, 4.0),
        Room("書斎",      0.0, 5.8, 2.5, 2.5),
        Room("寝室",      4.0, 5.8, 4.0, 2.5),
        Room("子供部屋A", 5.5, 0.0, 2.5, 2.8),
        Room("子供部屋B", 5.5, 2.8, 2.5, 2.7),
        Room("洗面",      4.0, 4.0, 2.0, 1.8),
        Room("浴室",      6.0, 4.0, 2.0, 1.8),
        Room("トイレ",    2.5, 5.5, 1.5, 1.5),
        Room("収納",      0.0, 8.3, 8.0, 1.2),
        Room("バルコニー", 0.0, -1.5, 6.5, 1.5),
    ]
    return FloorPlan("3LDK" if mode=="real" else "三間の家", rooms,
                     82.0, style, mode,
                     ["洋室x3", "LDK 22帖", "書斎付き"])

def make_fantasy_tower(style):
    rooms = [
        Room("門の間",    1.0, 0.0, 4.0, 2.0),
        Room("大広間",    0.0, 2.0, 6.0, 4.5),
        Room("賢者の書斎", 6.0, 0.0, 3.0, 3.5),
        Room("錬金術室",  6.0, 3.5, 3.0, 3.0),
        Room("秘密の間",  0.0, 6.5, 2.5, 2.0),
        Room("水晶の間",  2.5, 6.5, 3.5, 2.0),
        Room("隠し通路",  0.0, 8.5, 9.0, 1.0),
        Room("観測台",    3.0, -2.0, 3.0, 2.0),
    ]
    return FloorPlan("魔導師の塔", rooms, 95.0, style, "fantasy",
                     ["地下室への隠し扉あり", "北向き観測台", "魔法陣埋め込み床"])

def make_scifi_habitat(style):
    rooms = [
        Room("エアロック",  0.0, 2.0, 2.0, 2.5),
        Room("コモンエリア", 2.0, 0.5, 5.0, 4.0),
        Room("個室A",       7.0, 0.0, 2.5, 2.5),
        Room("個室B",       7.0, 2.5, 2.5, 2.5),
        Room("水再生室",    2.0, 4.5, 2.0, 2.0),
        Room("医療ポッド",  4.0, 4.5, 2.0, 2.0),
        Room("動力炉室",    6.0, 4.5, 3.5, 2.0),
        Room("観測デッキ",  2.0, -2.0, 5.5, 2.0),
    ]
    return FloorPlan("軌道上居住モジュール", rooms, 78.0, style, "fantasy",
                     ["耐圧構造", "酸素循環システム内蔵", "非常脱出ポッド接続"])

PLAN_GENERATORS = {
    "real":    [make_1ldk, make_2ldk, make_3ldk],
    "fantasy": [make_fantasy_tower, make_scifi_habitat],
}

# ── 描画エンジン（スマホ最適化）────────────
def draw_floorplan(plan: FloorPlan, output_path: Path) -> Path:
    pal = PALETTES.get(plan.style, PALETTES["modern"])
    rc  = ROOM_COLORS.get(plan.style, ROOM_COLORS["modern"])

    all_x = [r.x for r in plan.rooms] + [r.x+r.w for r in plan.rooms]
    all_y = [r.y for r in plan.rooms] + [r.y+r.h for r in plan.rooms]
    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)
    pw = max_x - min_x
    ph = max_y - min_y

    # ── Instagram正方形 1080x1080 想定 ──
    # figsize=(12,12) @ dpi=90 → 1080x1080px
    FIG  = 12.0
    DPI  = 90
    # 間取り描画領域: 図の中央80%に収める
    PAD_TOP    = 1.6   # タイトル用
    PAD_BOTTOM = 1.0   # ノート用
    PAD_LR     = 0.8

    draw_w = FIG - PAD_LR * 2
    draw_h = FIG - PAD_TOP - PAD_BOTTOM
    scale  = min(draw_w / pw, draw_h / ph) * 0.88

    fig, ax = plt.subplots(figsize=(FIG, FIG), dpi=DPI)
    fig.patch.set_facecolor(pal["bg"])
    ax.set_facecolor(pal["bg"])

    # 座標変換: 間取りを中央に配置
    cx = (min_x + max_x) / 2
    cy = (min_y + max_y) / 2

    def tx(x): return (x - cx) * scale
    def ty(y): return (y - cy) * scale

    # ── グリッド ──
    for gx in np.arange(min_x, max_x + 1, 1.0):
        ax.axvline(tx(gx), color=pal["grid"], linewidth=0.4, zorder=0, alpha=0.7)
    for gy in np.arange(min_y, max_y + 1, 1.0):
        ax.axhline(ty(gy), color=pal["grid"], linewidth=0.4, zorder=0, alpha=0.7)

    WALL      = 0.04 * scale
    skip_door = {"バルコニー","廊下","収納","観測デッキ","隠し通路"}
    open_rooms = {"バルコニー","観測デッキ"}

    for room in plan.rooms:
        room_col = rc.get(room.name, pal.get("room","#F0EDE8"))
        rx = tx(room.x);  ry = ty(room.y)
        rw = room.w * scale; rh = room.h * scale

        is_open = room.name in open_rooms

        if is_open:
            rect = patches.Rectangle(
                (rx, ry), rw, rh,
                linewidth=1.5, edgecolor=pal["wall"],
                facecolor=room_col, linestyle="--", zorder=1)
            ax.add_patch(rect)
        else:
            fill = patches.Rectangle(
                (rx+WALL, ry+WALL), rw-WALL*2, rh-WALL*2,
                linewidth=0, facecolor=room_col, zorder=1)
            wall = patches.Rectangle(
                (rx, ry), rw, rh,
                linewidth=2.5, edgecolor=pal["wall"],
                facecolor="none", zorder=3)
            ax.add_patch(fill)
            ax.add_patch(wall)

        # ドア記号
        if room.name not in skip_door:
            dr  = min(rw, rh) * 0.22
            dax = rx + rw * 0.15
            day = ry
            arc = patches.Arc(
                (dax, day), dr*2, dr*2,
                angle=0, theta1=0, theta2=90,
                color=pal["door"], linewidth=1.2, zorder=4)
            ax.add_patch(arc)
            ax.plot([dax, dax],      [day, day+dr], color=pal["door"], linewidth=1.2, zorder=4)
            ax.plot([dax, dax+dr],   [day, day],    color=pal["door"], linewidth=1.2, zorder=4)

        # ── ラベル（大きめ・2行）──
        lcx = rx + rw/2
        lcy = ry + rh/2

        # 部屋名: 面積に応じてフォントサイズを決定（最小11pt）
        area_units = rw * rh / (scale**2)
        fs_name = max(11, min(16, area_units * 5.5))
        fs_area = max(9,  min(13, area_units * 4.0))

        ax.text(lcx, lcy + rh*0.08, room.name,
                ha="center", va="center",
                fontsize=fs_name, fontweight="bold",
                color=pal["wall"], zorder=5)

        no_area = {"バルコニー","廊下","玄関","収納","隠し通路","観測デッキ"}
        if room.name not in no_area:
            area_m2 = room.w * room.h * 2.0
            ax.text(lcx, lcy - rh*0.18, f"{area_m2:.1f}m2",
                    ha="center", va="center",
                    fontsize=fs_area, color=pal["accent"], zorder=5)

    # ── 寸法線 ──
    ap = dict(arrowstyle="<->", color=pal["accent"], linewidth=1.0, mutation_scale=10)
    dim_y = ty(min_y) - 0.7
    ax.annotate("", xy=(tx(max_x), dim_y), xytext=(tx(min_x), dim_y), arrowprops=ap, zorder=6)
    ax.text((tx(min_x)+tx(max_x))/2, dim_y-0.3, f"{pw:.1f}m",
            ha="center", va="top", fontsize=11, color=pal["accent"])

    dim_x = tx(max_x) + 0.7
    ax.annotate("", xy=(dim_x, ty(max_y)), xytext=(dim_x, ty(min_y)), arrowprops=ap, zorder=6)
    ax.text(dim_x+0.3, (ty(min_y)+ty(max_y))/2, f"{ph:.1f}m",
            ha="left", va="center", fontsize=11, color=pal["accent"], rotation=90)

    # ── 方位記号 ──
    nx = tx(max_x) + 0.3
    ny = ty(max_y) + 0.2
    ax.annotate("", xy=(nx, ny+0.8), xytext=(nx, ny),
                arrowprops=dict(arrowstyle="->", color=pal["accent"],
                                linewidth=2.0, mutation_scale=12))
    ax.text(nx, ny+1.0, "N", ha="center", va="bottom",
            fontsize=13, color=pal["accent"], fontweight="bold")

    # ── タイトルエリア（上部・大きく）──
    title_y = ty(max_y) + 1.5
    ax.text(tx(min_x), title_y, plan.title,
            ha="left", va="bottom",
            fontsize=22, fontweight="bold", color=pal["wall"])

    mode_str  = "リアル風" if plan.mode=="real" else "架空世界"
    style_map = {"modern":"MODERN","nordic":"NORDIC","japanese":"JAPANESE",
                 "fantasy":"FANTASY","scifi":"SCI-FI"}
    ax.text(tx(min_x), title_y + 1.05,
            f"{plan.total_area:.0f}m2  ·  {mode_str}  ·  {style_map.get(plan.style,'')}",
            ha="left", va="bottom",
            fontsize=13, color=pal["accent"])

    # ── ノート（下部）──
    note_y = ty(min_y) - 1.3
    ax.text(tx(min_x), note_y, "  /  ".join(plan.notes),
            ha="left", va="top",
            fontsize=11, color=pal["sub"], style="italic")

    # ── 枠線（全体）──
    lim = 6.2
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_aspect("equal")
    ax.axis("off")

    plt.tight_layout(pad=0.2)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=DPI, bbox_inches="tight",
                facecolor=pal["bg"])
    plt.close(fig)
    return output_path


# ── 日次生成 ─────────────────────────────
def generate_daily_floorplan(
    target_date: date = None,
    output_dir: Path = Path("output/floorplans"),
    fantasy_ratio: float = 0.3,
) -> dict:
    if target_date is None:
        target_date = date.today()
    seed = int(target_date.strftime("%Y%m%d"))
    random.seed(seed)
    mode = "fantasy" if random.random() < fantasy_ratio else "real"
    if mode == "real":
        style = random.choice(["modern","nordic","japanese"])
        plan  = random.choice(PLAN_GENERATORS["real"])(style, mode)
    else:
        style = random.choice(["fantasy","scifi"])
        plan  = random.choice(PLAN_GENERATORS["fantasy"])(style)
    out_path = output_dir / f"{target_date.isoformat()}_floorplan.png"
    draw_floorplan(plan, out_path)
    return {"date": target_date.isoformat(), "mode": mode, "style": style,
            "title": plan.title, "total_area": plan.total_area,
            "notes": plan.notes, "image_path": str(out_path)}


# ── CLI ───────────────────────────────────
if __name__ == "__main__":
    import argparse, json
    from dotenv import load_dotenv
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("--date",  default=None)
    parser.add_argument("--mode",  default=None, choices=["real","fantasy"])
    parser.add_argument("--style", default=None,
                        choices=["modern","nordic","japanese","fantasy","scifi"])
    parser.add_argument("--output", default="output/floorplans")
    parser.add_argument("--fantasy-ratio", type=float, default=0.3)
    args = parser.parse_args()

    target_date = date.fromisoformat(args.date) if args.date else date.today()
    print(f"\n🏠 間取り図生成エンジン起動 (スマホ最適化版)")
    print(f"   フォント: {_JP_FONT or 'デフォルト'}")
    print(f"   日付: {target_date.isoformat()}")

    if args.mode or args.style:
        seed  = int(target_date.strftime("%Y%m%d"))
        random.seed(seed)
        mode  = args.mode or ("real" if random.random() > 0.3 else "fantasy")
        style = args.style or (
            random.choice(["modern","nordic","japanese"]) if mode=="real"
            else random.choice(["fantasy","scifi"]))
        plan = (random.choice(PLAN_GENERATORS["real"])(style, mode)
                if mode=="real"
                else random.choice(PLAN_GENERATORS["fantasy"])(style))
        out_path = Path(args.output) / f"{target_date.isoformat()}_floorplan.png"
        draw_floorplan(plan, out_path)
        result = {"date": target_date.isoformat(), "mode": mode, "style": style,
                  "title": plan.title, "total_area": plan.total_area,
                  "notes": plan.notes, "image_path": str(out_path)}
    else:
        result = generate_daily_floorplan(
            target_date=target_date,
            output_dir=Path(args.output),
            fantasy_ratio=args.fantasy_ratio)

    print(f"\n   モード  : {result['mode']}")
    print(f"   スタイル: {result['style']}")
    print(f"   間取り  : {result['title']}  ({result['total_area']}m2)")
    print(f"   保存先  : {result['image_path']}")
    print(f"\n✅ 完了!")