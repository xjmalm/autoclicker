"""把无花果原图处理成 Windows 多尺寸图标。

处理流程：
1. 去掉原图右下角水印。
2. 按果实主体计算边界，做等比例方形裁剪。
3. 去掉白色背景，保留透明 alpha。
4. 输出 app_preview.png 和 app.ico。
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps


BASE_DIR = Path(__file__).resolve().parent
SOURCE_IMAGE = BASE_DIR / "assets" / "fig_source.jpg"

OUTPUT_SIZE = 1024
ICON_SIZES = [
    (16, 16),
    (24, 24),
    (32, 32),
    (48, 48),
    (64, 64),
    (128, 128),
    (256, 256),
]


def load_source() -> Image.Image:
    if not SOURCE_IMAGE.exists():
        raise FileNotFoundError(f"缺少原图：{SOURCE_IMAGE}")
    return Image.open(SOURCE_IMAGE).convert("RGB")


def remove_watermark(image: Image.Image) -> Image.Image:
    """覆盖右下角水印。水印下方是纯白背景，不会遮住果实。"""
    width, height = image.size
    draw = ImageDraw.Draw(image)
    draw.rectangle(
        (
            int(width * 0.78),
            int(height * 0.93),
            width,
            height,
        ),
        fill=(255, 255, 255),
    )
    return image


def content_box(image: Image.Image) -> tuple[int, int, int, int]:
    pixels = np.asarray(image).astype(np.int16)
    non_white = (
        (pixels[:, :, 0] < 245)
        | (pixels[:, :, 1] < 245)
        | (pixels[:, :, 2] < 245)
    )
    ys, xs = np.where(non_white)
    if len(xs) == 0:
        return 0, 0, image.width, image.height
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def crop_to_subject(image: Image.Image) -> Image.Image:
    left, top, right, bottom = content_box(image)
    width = right - left
    height = bottom - top
    side = max(width, height)

    margin = int(side * 0.05)
    side = min(min(image.size), side + margin * 2)

    center_x = (left + right) // 2
    center_y = (top + bottom) // 2
    crop_left = max(0, min(image.width - side, center_x - side // 2))
    crop_top = max(0, min(image.height - side, center_y - side // 2))

    return image.crop((crop_left, crop_top, crop_left + side, crop_top + side))


def remove_white_background(image: Image.Image) -> Image.Image:
    """从四边泛洪白底，保留果实内部的高光。"""
    pixels = np.asarray(image).astype(np.int16)
    near_white = (
        (pixels[:, :, 0] > 245)
        & (pixels[:, :, 1] > 245)
        & (pixels[:, :, 2] > 245)
    )
    background = Image.fromarray(
        np.where(near_white, 255, 0).astype(np.uint8),
        mode="L",
    ).copy()

    # 从四个角开始填充，只移除与边框相连的白色区域。
    for point in (
        (0, 0),
        (background.width - 1, 0),
        (0, background.height - 1),
        (background.width - 1, background.height - 1),
    ):
        ImageDraw.floodfill(background, point, 128, thresh=0)

    background = background.point(lambda value: 255 if value == 128 else 0)
    background = background.filter(ImageFilter.GaussianBlur(1.2))
    alpha = ImageOps.invert(background)

    result = image.convert("RGBA")
    result.putalpha(alpha)
    return result


def main() -> None:
    image = load_source()
    image = remove_watermark(image)
    image = crop_to_subject(image)
    image = image.resize((OUTPUT_SIZE, OUTPUT_SIZE), Image.LANCZOS)
    image = remove_white_background(image)

    image.save("app_preview.png", "PNG")
    image.save("app.ico", format="ICO", sizes=ICON_SIZES)

    print("已生成透明背景的无花果图标：app_preview.png 和 app.ico")


if __name__ == "__main__":
    main()
