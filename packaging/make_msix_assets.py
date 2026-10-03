"""生成 MSIX 包所需的图标资源（packaging\\assets）。

MSIX 要求包内提供 StoreLogo、Square44x44Logo、Square150x150Logo 等图片，
并且推荐同时提供 100/125/150/200/400 各缩放比例的版本，否则在高 DPI
屏幕上会被拉伸模糊。

素材来源是仓库根目录的 app_preview.png（由 make_icon.py 生成，透明背景），
本脚本把图形等比居中放到暖色底板上，输出到 packaging\\assets。

用法：
    python packaging\\make_msix_assets.py
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    raise SystemExit(
        "缺少 Pillow，无法生成图标资源。请执行：python -m pip install pillow"
    )


BASE_DIR = Path(__file__).resolve().parent
REPO_DIR = BASE_DIR.parent
SOURCE_IMAGE = REPO_DIR / "app_preview.png"
OUTPUT_DIR = BASE_DIR / "assets"

# 与 AppxManifest.xml 中 VisualElements 的 BackgroundColor 保持一致。
BACKGROUND = (253, 243, 236, 255)
SCALES = (100, 125, 150, 200, 400)

# (资源名, 宽, 高, 图形占短边比例)
TILES = (
    ("StoreLogo", 50, 50, 0.78),
    ("Square44x44Logo", 44, 44, 0.72),
    ("Square150x150Logo", 150, 150, 0.62),
    ("Wide310x150Logo", 310, 150, 0.62),
)


def load_glyph() -> Image.Image:
    """载入素材并裁掉透明外边距，保证各尺寸留白比例一致。"""
    if not SOURCE_IMAGE.exists():
        raise SystemExit(f"缺少素材：{SOURCE_IMAGE}（可先运行 make_icon.py 生成）")
    image = Image.open(SOURCE_IMAGE).convert("RGBA")
    box = image.getbbox()
    if box:
        image = image.crop(box)
    return image


def render(glyph: Image.Image, width: int, height: int, ratio: float) -> Image.Image:
    """把图形等比居中绘制到指定尺寸的底板上。"""
    canvas = Image.new("RGBA", (width, height), BACKGROUND)
    target = max(1, round(min(width, height) * ratio))
    scale = target / max(glyph.width, glyph.height)
    size = (max(1, round(glyph.width * scale)), max(1, round(glyph.height * scale)))
    scaled = glyph.resize(size, Image.Resampling.LANCZOS)
    canvas.alpha_composite(scaled, ((width - size[0]) // 2, (height - size[1]) // 2))
    return canvas


def main() -> int:
    glyph = load_glyph()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    written = 0
    for name, width, height, ratio in TILES:
        for percent in SCALES:
            size = (
                max(1, round(width * percent / 100)),
                max(1, round(height * percent / 100)),
            )
            suffix = "" if percent == 100 else f".scale-{percent}"
            path = OUTPUT_DIR / f"{name}{suffix}.png"
            render(glyph, size[0], size[1], ratio).save(path, "PNG")
            written += 1
            print(f"  {path.relative_to(REPO_DIR)}  {size[0]}x{size[1]}")

    print(f"已生成 {written} 个图标资源：{OUTPUT_DIR.relative_to(REPO_DIR)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
