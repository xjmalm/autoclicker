"""生成 AutoClicker 的 Windows 图标。

输出：
- app.ico：多尺寸 Windows 图标
- app_preview.png：大尺寸预览图
"""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFilter


SIZE = 1024


def rounded_gradient_background() -> Image.Image:
    top = (59, 130, 246, 255)
    bottom = (124, 58, 237, 255)

    column = Image.new("RGB", (1, SIZE))
    column_pixels = column.load()
    for y in range(SIZE):
        ratio = y / (SIZE - 1)
        color = tuple(round(top[i] + (bottom[i] - top[i]) * ratio) for i in range(3))
        column_pixels[0, y] = color

    background = column.resize((SIZE, SIZE), Image.LANCZOS).convert("RGBA")

    mask = Image.new("L", (SIZE, SIZE), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle(
        (0, 0, SIZE - 1, SIZE - 1),
        radius=220,
        fill=255,
    )
    background.putalpha(mask)
    return background


def draw_click_ring(image: Image.Image) -> None:
    layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.ellipse(
        (235, 235, 789, 789),
        outline=(255, 255, 255, 36),
        width=22,
    )
    image.alpha_composite(layer)


def draw_cursor_arrow(image: Image.Image) -> None:
    normalized = [
        (0.0, 0.0),
        (0.0, 17.0),
        (12.5, 12.5),
        (17.5, 17.5),
        (12.5, 12.5),
        (17.0, 0.0),
    ]
    scale = 24.0
    offset_x = 270
    offset_y = 270

    points = [
        (round(offset_x + x * scale), round(offset_y + y * scale))
        for x, y in normalized
    ]

    shadow_layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow_layer)
    shadow_draw.polygon(
        [(x + 16, y + 20) for x, y in points],
        fill=(15, 23, 42, 95),
    )
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(14))
    image.alpha_composite(shadow_layer)

    arrow_layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    arrow_draw = ImageDraw.Draw(arrow_layer)
    arrow_draw.polygon(
        points,
        fill=(255, 255, 255, 255),
        outline=(15, 23, 42, 255),
        width=12,
    )
    image.alpha_composite(arrow_layer)


def add_highlight(image: Image.Image) -> None:
    layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.rounded_rectangle(
        (28, 28, SIZE - 29, SIZE - 29),
        radius=185,
        outline=(255, 255, 255, 46),
        width=8,
    )
    image.alpha_composite(layer)


def main() -> None:
    image = rounded_gradient_background()
    draw_click_ring(image)
    draw_cursor_arrow(image)
    add_highlight(image)

    image.save("app_preview.png", "PNG")

    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    image.save("app.ico", format="ICO", sizes=sizes)

    print("已生成 app_preview.png 和 app.ico")


if __name__ == "__main__":
    main()
