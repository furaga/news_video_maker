"""Playwright + HTML/CSS によるアニメーションフレーム生成（字幕スタイル）"""
import asyncio
import base64
import html as html_module
import io
import logging
import re

import numpy as np
from PIL import Image
from moviepy import VideoClip

logger = logging.getLogger(__name__)

WIDTH, HEIGHT = 1080, 1920
FPS = 30
FADE_DURATION = 0.3   # セクション開始時のフェードイン時間

# ---- HTML テンプレート -------------------------------------------------------

_SUBTITLE_TEMPLATE = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    width: {width}px; height: {height}px;
    background: #0d1117;
    font-family: 'BIZ UDGothic', 'Noto Sans JP', 'Meiryo', 'Yu Gothic', sans-serif;
    overflow: hidden; position: relative;
  }}
  .bg {{
    position: absolute; inset: 0;
    background-image: url('{bg_data_url}');
    background-size: cover; background-position: center;
    transform: scale(1.06);
  }}
  .bg-overlay {{
    position: absolute; inset: 0;
    background: rgba(0, 0, 0, 0.25);
  }}
  /* タイトルバー（上部固定） */
  .title-bar {{
    position: absolute;
    top: 60px; left: 60px; right: 60px;
    z-index: 20;
  }}
  .title-bg {{
    display: inline-block;
    background: rgba(0, 0, 0, 0.65);
    border-radius: 16px;
    padding: 20px 32px;
    backdrop-filter: blur(8px);
    max-width: 100%;
  }}
  .title-text {{
    font-size: 44px; font-weight: 900;
    color: #ffffff;
    line-height: 1.4;
    text-shadow: 0 1px 4px rgba(0,0,0,0.6);
    word-break: break-all;
  }}
  /* ソースラベル */
  .source-label {{
    position: absolute;
    top: 230px; left: 60px;
    z-index: 20;
    display: inline-flex;
    align-items: center; gap: 10px;
  }}
  .source-dot {{
    width: 8px; height: 8px; border-radius: 50%;
    background: {source_color};
    flex-shrink: 0;
  }}
  .source-text {{
    font-size: 28px; font-weight: 700;
    color: rgba(255,255,255,0.7);
    text-shadow: 0 1px 3px rgba(0,0,0,0.8);
  }}
  /* 字幕ボックス（下部中央） */
  .subtitle-area {{
    position: absolute;
    bottom: 100px; left: 60px; right: 60px;
    z-index: 20;
    display: flex; justify-content: center;
  }}
  .subtitle-bg {{
    display: inline-block;
    background: rgba(0, 0, 0, 0.72);
    border-radius: 16px;
    padding: 24px 40px;
    backdrop-filter: blur(4px);
    max-width: 100%;
  }}
  .subtitle-text {{
    font-size: 56px; font-weight: 700;
    color: #ffffff;
    line-height: 1.5;
    text-align: center;
    text-shadow: 0 2px 6px rgba(0,0,0,0.8);
    word-break: break-all;
  }}
  #fade {{
    position: absolute; inset: 0; z-index: 100;
    background: #000; opacity: 1; pointer-events: none;
  }}
</style>
</head>
<body>
  <div class="bg" id="bg"></div>
  <div class="bg-overlay"></div>
  <div class="title-bar">
    <div class="title-bg">
      <div class="title-text">{title}</div>
    </div>
  </div>
  <div class="source-label">
    <div class="source-dot"></div>
    <span class="source-text">{source}</span>
  </div>
  <div class="subtitle-area">
    <div class="subtitle-bg">
      <div class="subtitle-text" id="subtitle">{subtitle}</div>
    </div>
  </div>
  <div id="fade"></div>
</body>
</html>
"""

_CTA_TEMPLATE = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    width: {width}px; height: {height}px;
    background: #0d1117;
    font-family: 'BIZ UDGothic', 'Noto Sans JP', 'Meiryo', 'Yu Gothic', sans-serif;
    overflow: hidden; position: relative;
  }}
  .bg {{
    position: absolute; inset: 0;
    background-image: url('{bg_data_url}');
    background-size: cover; background-position: center;
    transform: scale(1.06);
  }}
  .bg-overlay {{
    position: absolute; inset: 0;
    background: rgba(0, 0, 0, 0.5);
  }}
  .cta-center {{
    position: absolute; inset: 0;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    z-index: 20;
  }}
  .cta-bg {{
    display: inline-block;
    background: rgba(0, 0, 0, 0.78);
    border-radius: 28px;
    padding: 60px 80px;
    backdrop-filter: blur(8px);
    text-align: center;
  }}
  .cta-emoji {{
    font-size: 120px; line-height: 1; margin-bottom: 32px;
  }}
  .cta-text {{
    font-size: 68px; font-weight: 900;
    color: #ffffff;
    line-height: 1.6;
    text-shadow: 0 2px 8px rgba(0,0,0,0.8);
    white-space: pre-line;
  }}
  #fade {{
    position: absolute; inset: 0; z-index: 100;
    background: #000; opacity: 1; pointer-events: none;
  }}
</style>
</head>
<body>
  <div class="bg" id="bg"></div>
  <div class="bg-overlay"></div>
  <div class="cta-center">
    <div class="cta-bg">
      <div class="cta-emoji">👍</div>
      <div class="cta-text">{cta_text}</div>
    </div>
  </div>
  <div id="fade"></div>
</body>
</html>
"""

# ---- ヘルパー ----------------------------------------------------------------

# ソース別ブランドカラー
SOURCE_COLORS: dict[str, str] = {
    "techcrunch": "#1a7f37",
    "arstechnica": "#dd3333",
    "theverge": "#fa4718",
    "hackernews": "#ff6600",
}


def split_into_subtitle_chunks(text: str, max_chars: int = 22) -> list[str]:
    """narration_text を字幕チャンクのリストに分割する。

    句読点（。！？）で区切り、1チャンクが max_chars 文字を超える場合は
    読点（、）でさらに分割する。
    """
    # 句点・感嘆符・疑問符で分割（区切り文字を含む形で保持）
    raw = re.split(r'(?<=[。！？])', text.strip())
    raw = [s.strip() for s in raw if s.strip()]

    chunks = []
    for sentence in raw:
        if len(sentence) <= max_chars:
            chunks.append(sentence)
        else:
            # 読点で分割
            parts = re.split(r'(?<=、)', sentence)
            current = ""
            for part in parts:
                if len(current) + len(part) <= max_chars:
                    current += part
                else:
                    if current:
                        chunks.append(current)
                    # part 自体が長い場合はさらに強制分割
                    while len(part) > max_chars:
                        chunks.append(part[:max_chars])
                        part = part[max_chars:]
                    current = part
            if current:
                chunks.append(current)

    return chunks if chunks else [text]


def image_to_data_url(image_url: str) -> str | None:
    """記事画像をダウンロードして base64 data URL に変換する"""
    import httpx
    try:
        r = httpx.get(
            image_url,
            headers={"User-Agent": "news-video-maker/0.1"},
            timeout=10,
            follow_redirects=True,
        )
        r.raise_for_status()
        content_type = r.headers.get("content-type", "image/jpeg").split(";")[0].strip()
        b64 = base64.b64encode(r.content).decode()
        return f"data:{content_type};base64,{b64}"
    except Exception as e:
        logger.warning("記事画像の取得に失敗: %s", e)
        return None


_SCREENSHOT_VIEWPORT_W = 1080
_SCREENSHOT_VIEWPORT_H = 1920


async def _screenshot_article_url_async(url: str) -> str | None:
    """Playwright でページ全画面をキャプチャし 1080x1920 にリサイズして data URL を返す"""
    from news_video_maker.config import IMAGES_DIR

    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(
                viewport={"width": _SCREENSHOT_VIEWPORT_W, "height": _SCREENSHOT_VIEWPORT_H}
            )
            await page.goto(url, wait_until="load", timeout=30000)
            screenshot_bytes = await page.screenshot(type="png", full_page=False)
            await browser.close()

        # 元スクリーンショットを保存（デバッグ用）
        orig_path = IMAGES_DIR / "article_screenshot_orig.png"
        orig_path.write_bytes(screenshot_bytes)
        img = Image.open(io.BytesIO(screenshot_bytes))
        logger.info("スクリーンショット取得完了: %dx%d → %s", img.width, img.height, orig_path)

        # 1080x1920 にリサイズ
        img_resized = img.resize((WIDTH, HEIGHT), Image.LANCZOS)
        save_path = IMAGES_DIR / "article_screenshot_full.png"
        img_resized.save(save_path)
        logger.info("リサイズ済み画像保存: %s", save_path)

        buf = io.BytesIO()
        img_resized.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        return f"data:image/png;base64,{b64}"
    except Exception as e:
        logger.warning("記事ページのスクリーンショット取得に失敗: %s", e)
        return None


def screenshot_article_url(url: str) -> str | None:
    """記事ページのスクリーンショットを撮り base64 data URL を返す（同期ラッパー）"""
    return asyncio.run(_screenshot_article_url_async(url))


# ---- Playwright レンダリング -------------------------------------------------

async def _render_frames_async(
    html: str,
    subtitle_chunks: list[str],
    chunk_durations: list[float],
    section_start: float,
    total_duration: float,
    is_cta: bool = False,
) -> list[np.ndarray]:
    """Playwright でフレームをレンダリングする。

    各チャンクにつき chunk_duration 秒分のフレームを生成する。
    セクション冒頭はフェードインアニメーション付き。
    """
    from playwright.async_api import async_playwright

    frames: list[np.ndarray] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})
        await page.set_content(html, wait_until="networkidle")

        elapsed = 0.0
        for chunk_idx, (chunk, chunk_dur) in enumerate(zip(subtitle_chunks, chunk_durations)):
            # 字幕テキストを更新（CTAテンプレートは subtitle 要素なし）
            if not is_cta:
                escaped_chunk = chunk.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
                await page.evaluate(
                    f"document.getElementById('subtitle').textContent = '{escaped_chunk}';"
                )

            n_frames = max(1, round(chunk_dur * FPS))
            for frame_i in range(n_frames):
                t_in_chunk = frame_i / FPS
                global_t = section_start + elapsed + t_in_chunk

                await page.evaluate(
                    """([globalT, totalDuration, tInChunk, fadeDuration, isFirst]) => {
                        const bgEl = document.getElementById('bg');
                        if (bgEl) {
                            const bgScale = 1.06 + 0.08 * (globalT / totalDuration);
                            bgEl.style.transform = 'scale(' + bgScale + ')';
                        }
                        const fade = document.getElementById('fade');
                        if (fade) {
                            if (isFirst && tInChunk < fadeDuration) {
                                fade.style.opacity = 1 - tInChunk / fadeDuration;
                            } else {
                                fade.style.opacity = 0;
                            }
                        }
                    }""",
                    [global_t, total_duration, t_in_chunk, FADE_DURATION, chunk_idx == 0],
                )

                screenshot = await page.screenshot(type="png")
                img = Image.open(io.BytesIO(screenshot)).convert("RGB")
                frames.append(np.array(img))

            elapsed += chunk_dur

        await browser.close()

    return frames


def _render_frames(
    html: str,
    subtitle_chunks: list[str],
    chunk_durations: list[float],
    section_start: float = 0.0,
    total_duration: float = 60.0,
    is_cta: bool = False,
) -> list[np.ndarray]:
    """同期ラッパー"""
    return asyncio.run(_render_frames_async(
        html, subtitle_chunks, chunk_durations, section_start, total_duration, is_cta
    ))


# ---- 公開 API ---------------------------------------------------------------

def generate_subtitle_clip(
    title: str,
    subtitle_chunks: list[str],
    chunk_durations: list[float],
    bg_data_url: str,
    source: str,
    source_url: str,
    duration: float,
    section_start: float = 0.0,
    total_duration: float = 60.0,
) -> VideoClip:
    """字幕スタイルの VideoClip を返す。

    subtitle_chunks: 表示する字幕テキストのリスト（narration_text を分割したもの）
    chunk_durations: 各チャンクの表示時間（秒）
    """
    source_color = SOURCE_COLORS.get(source, "#00dcc2")

    html = _SUBTITLE_TEMPLATE.format(
        width=WIDTH,
        height=HEIGHT,
        bg_data_url=bg_data_url or "",
        title=html_module.escape(title),
        source=html_module.escape(source),
        source_color=source_color,
        subtitle=html_module.escape(subtitle_chunks[0] if subtitle_chunks else ""),
    )

    logger.info("字幕クリップレンダリング開始: %d チャンク, %.1fs", len(subtitle_chunks), duration)
    rendered = _render_frames(html, subtitle_chunks, chunk_durations, section_start, total_duration)

    def make_frame(t: float) -> np.ndarray:
        idx = min(int(t * FPS), len(rendered) - 1)
        return rendered[idx]

    logger.info("字幕クリップ準備完了: duration=%.1fs, frames=%d", duration, len(rendered))
    return VideoClip(make_frame, duration=duration)


def generate_cta_clip(
    bg_data_url: str,
    duration: float,
    section_start: float = 0.0,
    total_duration: float = 60.0,
) -> VideoClip:
    """CTAセクション用 VideoClip を返す"""
    cta_text = "高評価とチャンネル登録\\nよろしくお願いします！"

    html = _CTA_TEMPLATE.format(
        width=WIDTH,
        height=HEIGHT,
        bg_data_url=bg_data_url or "",
        cta_text=html_module.escape("高評価とチャンネル登録\nよろしくお願いします！"),
    )

    chunks = ["高評価とチャンネル登録\nよろしくお願いします！"]
    durations = [duration]

    logger.info("CTAクリップレンダリング開始: %.1fs", duration)
    rendered = _render_frames(html, chunks, durations, section_start, total_duration, is_cta=True)

    def make_frame(t: float) -> np.ndarray:
        idx = min(int(t * FPS), len(rendered) - 1)
        return rendered[idx]

    logger.info("CTAクリップ準備完了: duration=%.1fs, frames=%d", duration, len(rendered))
    return VideoClip(make_frame, duration=duration)
