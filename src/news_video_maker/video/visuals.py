"""Playwright + HTML/CSS によるアニメーションフレーム生成"""
import asyncio
import base64
import io
import logging
from pathlib import Path

import httpx
import numpy as np
from PIL import Image
from moviepy import VideoClip

logger = logging.getLogger(__name__)

WIDTH, HEIGHT = 1080, 1920
FPS = 30
INTRO_DURATION = 0.6   # カード + テキストのスライドイン時間
OUTRO_DURATION = 0.4   # フェードアウト時間

# ---- HTML テンプレート -------------------------------------------------------
# {bg_data_url}: base64 data URL or empty string
# {source}:      ソース名 (e.g. "techcrunch.com")
# {source_url}:  元記事 URL
# {subtitle}:    字幕テキスト

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}

  body {{
    width: {width}px;
    height: {height}px;
    background: #0d1117;
    font-family: 'BIZ UDGothic', 'Noto Sans JP', 'Meiryo', 'Yu Gothic', sans-serif;
    overflow: hidden;
    position: relative;
  }}

  /* 背景画像 (blurred + darkened) */
  .bg {{
    position: absolute;
    inset: 0;
    background-image: url('{bg_data_url}');
    background-size: cover;
    background-position: center;
    filter: blur(12px) brightness(0.22) saturate(0.8);
    transform: scale(1.06);
  }}

  /* 背景グラデーションオーバーレイ */
  .bg-overlay {{
    position: absolute;
    inset: 0;
    background: linear-gradient(
      180deg,
      rgba(5, 10, 30, 0.6) 0%,
      transparent 40%,
      transparent 60%,
      rgba(5, 10, 30, 0.8) 100%
    );
  }}

  /* メインコンテンツ */
  .content {{
    position: relative;
    z-index: 1;
    height: 100%;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    padding: 80px 70px;
  }}

  /* メインカード */
  .card {{
    width: 100%;
    background: rgba(12, 22, 45, 0.82);
    border: 1px solid rgba(0, 220, 190, 0.18);
    border-radius: 36px;
    padding: 56px 60px 64px;
    backdrop-filter: blur(24px);
    -webkit-backdrop-filter: blur(24px);
    box-shadow:
      0 0 0 1px rgba(0, 220, 190, 0.08),
      0 24px 80px rgba(0, 0, 0, 0.6),
      inset 0 1px 0 rgba(255, 255, 255, 0.06);
    animation: card-enter {intro_ms}ms cubic-bezier(0.16, 1, 0.3, 1) both;
  }}

  @keyframes card-enter {{
    from {{ opacity: 0; transform: translateY(64px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
  }}

  /* ソースラベル */
  .source-label {{
    font-size: 30px;
    font-weight: 700;
    color: #00dcc2;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-bottom: 22px;
    opacity: 0;
    animation: fade-in {intro_ms}ms 150ms ease-out forwards;
  }}

  /* 区切り線 */
  .divider {{
    height: 1px;
    background: linear-gradient(90deg,
      transparent 0%,
      rgba(0, 220, 190, 0.35) 30%,
      rgba(0, 220, 190, 0.35) 70%,
      transparent 100%
    );
    margin-bottom: 40px;
    opacity: 0;
    animation: fade-in {intro_ms}ms 200ms ease-out forwards;
  }}

  /* メインテキスト */
  .main-text {{
    font-size: 72px;
    font-weight: 700;
    color: #f0f4ff;
    line-height: 1.4;
    letter-spacing: 0.01em;
    opacity: 0;
    animation: text-enter {intro_ms}ms 120ms cubic-bezier(0.16, 1, 0.3, 1) forwards;
  }}

  @keyframes text-enter {{
    from {{ opacity: 0; transform: translateY(24px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
  }}

  @keyframes fade-in {{
    from {{ opacity: 0; }}
    to   {{ opacity: 1; }}
  }}

  /* ボトムバー（記事情報） */
  .bottom-bar {{
    position: absolute;
    bottom: 56px;
    left: 60px;
    right: 60px;
    background: rgba(10, 18, 38, 0.75);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 20px;
    padding: 22px 32px;
    display: flex;
    align-items: center;
    gap: 18px;
    backdrop-filter: blur(16px);
    opacity: 0;
    animation: fade-in {intro_ms}ms 350ms ease-out forwards;
  }}

  .bottom-dot {{
    width: 7px;
    height: 7px;
    min-width: 7px;
    border-radius: 50%;
    background: #00dcc2;
  }}

  .bottom-source {{
    font-size: 26px;
    font-weight: 700;
    color: #a0b8d8;
    white-space: nowrap;
  }}

  .bottom-url {{
    font-size: 22px;
    color: #4a6888;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }}

  /* フェードオーバーレイ (JS で opacity を制御) */
  #fade {{
    position: absolute;
    inset: 0;
    z-index: 100;
    background: #000;
    opacity: 1;
    pointer-events: none;
    transition: none;
  }}
</style>
</head>
<body>
  <div class="bg"></div>
  <div class="bg-overlay"></div>

  <div class="content">
    <div class="card">
      <div class="source-label">{source}</div>
      <div class="divider"></div>
      <div class="main-text">{subtitle}</div>
    </div>
  </div>

  <div class="bottom-bar">
    <div class="bottom-dot"></div>
    <span class="bottom-source">{source}</span>
    <span class="bottom-url">{source_url}</span>
  </div>

  <div id="fade"></div>
</body>
</html>
"""

# ---- ヘルパー ----------------------------------------------------------------

def _image_to_data_url(image_url: str) -> str | None:
    """記事画像をダウンロードして base64 data URL に変換する"""
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


def _build_html(subtitle_text: str, source: str, source_url: str, bg_data_url: str) -> str:
    """HTML文字列を組み立てる"""
    return _HTML_TEMPLATE.format(
        width=WIDTH,
        height=HEIGHT,
        intro_ms=int(INTRO_DURATION * 1000),
        bg_data_url=bg_data_url or "",
        source=source,
        source_url=source_url,
        subtitle=subtitle_text,
    )


async def _render_frames_async(html: str, times: list[float]) -> list[np.ndarray]:
    """Playwright で指定時刻リストのフレームをレンダリングする"""
    from playwright.async_api import async_playwright

    frames: list[np.ndarray] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})
        await page.set_content(html, wait_until="networkidle")

        for t in times:
            # CSS/JS アニメーションを指定時刻にシークして停止
            await page.evaluate(
                """(t) => {
                    document.getAnimations({ subtree: true }).forEach(a => {
                        a.currentTime = t * 1000;
                        a.pause();
                    });
                    // フェードオーバーレイ制御
                    const fade = document.getElementById('fade');
                    const fadeIn  = Math.max(0, 1 - t / 0.25);
                    fade.style.opacity = fadeIn;
                }""",
                t,
            )
            screenshot = await page.screenshot(type="png")
            img = Image.open(io.BytesIO(screenshot)).convert("RGB")
            frames.append(np.array(img))

        await browser.close()

    return frames


def _render_frames(html: str, times: list[float]) -> list[np.ndarray]:
    """同期ラッパー"""
    return asyncio.run(_render_frames_async(html, times))


# ---- 公開 API ---------------------------------------------------------------

def generate_animated_clip(
    subtitle_text: str,
    source: str,
    source_url: str,
    duration: float,
    image_url: str | None = None,
) -> VideoClip:
    """HTML/CSS アニメーション付き moviepy VideoClip を返す

    intro/hold/outro の 3 ゾーンでフレームを最小限だけレンダリングし、
    hold フレームは複製することでパフォーマンスを確保する。
    """
    outro_start = max(INTRO_DURATION + 0.5, duration - OUTRO_DURATION)

    # 背景画像の準備
    bg_data_url = _image_to_data_url(image_url) if image_url else None
    html = _build_html(subtitle_text, source, source_url, bg_data_url or "")

    # レンダリングが必要な時刻リスト
    intro_times = [i / FPS for i in range(int(INTRO_DURATION * FPS) + 1)]
    hold_times  = [INTRO_DURATION + 0.01]   # 1枚だけ
    outro_times = [
        outro_start + i / FPS
        for i in range(int(OUTRO_DURATION * FPS) + 1)
    ]
    all_times = intro_times + hold_times + outro_times

    logger.info("フレームレンダリング開始: %d 枚", len(all_times))
    rendered = _render_frames(html, all_times)

    # インデックス分割
    n_intro = len(intro_times)
    intro_frames = rendered[:n_intro]
    hold_frame   = rendered[n_intro]
    outro_frames = rendered[n_intro + 1:]

    # hold フレームの枚数
    n_hold = max(1, round((outro_start - INTRO_DURATION) * FPS))
    all_frames = intro_frames + [hold_frame] * n_hold + outro_frames

    # フェードアウト中は黒オーバーレイを合成
    def _apply_fade_out(frame: np.ndarray, t: float) -> np.ndarray:
        if t <= outro_start:
            return frame
        ratio = min(1.0, (t - outro_start) / OUTRO_DURATION)
        black = np.zeros_like(frame)
        return (frame * (1 - ratio) + black * ratio).astype(np.uint8)

    def make_frame(t: float) -> np.ndarray:
        idx = min(int(t * FPS), len(all_frames) - 1)
        return _apply_fade_out(all_frames[idx], t)

    logger.info("アニメーションクリップ準備完了: duration=%.1fs, frames=%d", duration, len(all_frames))
    return VideoClip(make_frame, duration=duration)
