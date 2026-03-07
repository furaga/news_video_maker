"""Pillow テキストカード生成"""
import io
import logging
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

WIDTH, HEIGHT = 1080, 1920
FONT_SIZE = 72
SOURCE_FONT_SIZE = 32

# 優先順にフォントパスを試す
FONT_CANDIDATES = [
    "C:/Windows/Fonts/meiryo.ttc",
    "C:/Windows/Fonts/YuGothM.ttc",
    "C:/Windows/Fonts/msgothic.ttc",
]


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            pass
    logger.warning("日本語フォントが見つかりません。デフォルトフォントを使用します。")
    return ImageFont.load_default()


def _make_gradient_background() -> Image.Image:
    """グラデーション背景（紺色 → 深青）を生成"""
    img = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(img)
    for y in range(HEIGHT):
        ratio = y / HEIGHT
        r = int(10 + ratio * 5)
        g = int(20 + ratio * 30)
        b = int(60 + ratio * 80)
        draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))
    return img


def _download_and_crop_image(image_url: str) -> Image.Image | None:
    """記事画像をダウンロードして1080×1920にcoverクロップする"""
    try:
        r = httpx.get(
            image_url,
            headers={"User-Agent": "news-video-maker/0.1"},
            timeout=10,
            follow_redirects=True,
        )
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content)).convert("RGB")

        # Cover crop: 短辺を基準にリサイズしてから中央クロップ
        scale = max(WIDTH / img.width, HEIGHT / img.height)
        new_w = int(img.width * scale)
        new_h = int(img.height * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)

        left = (new_w - WIDTH) // 2
        top = (new_h - HEIGHT) // 2
        img = img.crop((left, top, left + WIDTH, top + HEIGHT))

        # 半透明の黒オーバーレイ（テキスト可読性確保）
        overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 140))
        img = img.convert("RGBA")
        img = Image.alpha_composite(img, overlay)
        return img.convert("RGB")

    except Exception as e:
        logger.warning("記事画像の取得に失敗しました: %s", e)
        return None


def generate_text_card(
    subtitle_text: str,
    source: str,
    output_path: Path,
    image_url: str | None = None,
) -> Path:
    """テキストカード画像を生成してPNGに保存する"""
    # 背景: 記事画像があれば使用、なければグラデーション
    img = None
    if image_url:
        img = _download_and_crop_image(image_url)
    if img is None:
        img = _make_gradient_background()

    draw = ImageDraw.Draw(img)

    # メインテキスト
    font = _load_font(FONT_SIZE)
    lines = _wrap_text(subtitle_text, font, draw, max_width=WIDTH - 80)
    line_height = FONT_SIZE + 16
    total_text_height = len(lines) * line_height

    y_start = (HEIGHT - total_text_height) // 2
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        x = (WIDTH - text_w) // 2
        y = y_start + i * line_height
        draw.text((x, y), line, fill=(255, 255, 255), font=font)

    # ソース表記（右下）
    source_font = _load_font(SOURCE_FONT_SIZE)
    source_text = f"Source: {source}"
    bbox = draw.textbbox((0, 0), source_text, font=source_font)
    source_w = bbox[2] - bbox[0]
    draw.text(
        (WIDTH - source_w - 20, HEIGHT - 60),
        source_text,
        fill=(180, 180, 180),
        font=source_font,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PNG")
    logger.info("画像生成完了: %s", output_path)
    return output_path


def _wrap_text(text: str, font, draw: ImageDraw.ImageDraw, max_width: int) -> list[str]:
    """テキストを指定幅で折り返す"""
    lines = []
    current = ""
    for char in text:
        test = current + char
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] > max_width and current:
            lines.append(current)
            current = char
        else:
            current = test
    if current:
        lines.append(current)
    return lines
