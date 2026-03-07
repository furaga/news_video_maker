"""Playwright + HTML/CSS によるアニメーションフレーム生成"""
import asyncio
import base64
import html as html_module
import io
import logging

import httpx
import numpy as np
from PIL import Image
from moviepy import VideoClip

logger = logging.getLogger(__name__)

WIDTH, HEIGHT = 1080, 1920
FPS = 30
INTRO_DURATION = 0.6   # カード + テキストのスライドイン時間
OUTRO_DURATION = 0.4   # スクロールアップ時間

# セクションタイプごとの視覚スタイル定義
_SECTION_STYLES: dict[str, dict] = {
    "hook":   {"accent": "#00dcc2", "is_title": True},
    "main_1": {"accent": "#00dcc2"},
    "main_2": {"accent": "#4a8fff"},
    "main_3": {"accent": "#a855f7"},
    "main_4": {"accent": "#f59e0b"},
    "main":   {"accent": "#00dcc2"},
    "outro":  {"accent": "#22c55e"},
}

# ---- HTML テンプレート -------------------------------------------------------

# タイトルカード（hook セクション用）
_TITLE_CARD_TEMPLATE = """\
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
    filter: blur(12px) brightness(0.18) saturate(0.7);
    transform: scale(1.06);
  }}
  .bg-overlay {{
    position: absolute; inset: 0;
    background: linear-gradient(180deg,
      rgba(5, 10, 30, 0.7) 0%, rgba(5, 10, 30, 0.3) 50%,
      rgba(5, 10, 30, 0.8) 100%
    );
  }}
  .content {{
    position: relative; z-index: 1; height: 100%;
    display: flex; flex-direction: column;
    justify-content: center; align-items: center;
    padding: 80px 70px;
  }}
  .card {{
    width: 100%;
    background: rgba(8, 16, 38, 0.88);
    border: 1px solid {accent_18};
    border-top: 4px solid {accent};
    border-radius: 36px;
    padding: 56px 60px 64px;
    backdrop-filter: blur(24px);
    -webkit-backdrop-filter: blur(24px);
    box-shadow:
      0 0 0 1px {accent_08},
      0 0 50px {accent_12},
      0 24px 80px rgba(0, 0, 0, 0.65),
      inset 0 1px 0 rgba(255, 255, 255, 0.06);
    animation: card-enter {intro_ms}ms cubic-bezier(0.16, 1, 0.3, 1) both;
  }}
  @keyframes card-enter {{
    from {{ opacity: 0; transform: translateY(64px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
  }}
  .news-badge {{
    display: inline-flex; align-items: center; gap: 12px;
    font-size: 30px; font-weight: 700;
    color: {accent};
    letter-spacing: 0.18em; text-transform: uppercase;
    margin-bottom: 36px;
    opacity: 0; animation: fade-in {intro_ms}ms 150ms ease-out forwards;
  }}
  .badge-dot {{
    width: 12px; height: 12px; border-radius: 50%;
    background: {accent}; box-shadow: 0 0 10px {accent};
  }}
  .title-text {{
    font-size: 66px; font-weight: 700;
    color: #ffffff;
    line-height: 1.35; letter-spacing: 0.01em;
    margin-bottom: 36px;
    opacity: 0;
    animation: text-enter {intro_ms}ms 120ms cubic-bezier(0.16, 1, 0.3, 1) forwards;
  }}
  .divider {{
    height: 1px;
    background: linear-gradient(90deg,
      transparent 0%, {accent_35} 30%, {accent_35} 70%, transparent 100%
    );
    margin-bottom: 32px;
    opacity: 0; animation: fade-in {intro_ms}ms 200ms ease-out forwards;
  }}
  .sub-text {{
    font-size: 46px; font-weight: 500;
    color: #a0c0e0; line-height: 1.4;
    opacity: 0; animation: fade-in {intro_ms}ms 300ms ease-out forwards;
  }}
  @keyframes text-enter {{
    from {{ opacity: 0; transform: translateY(24px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
  }}
  @keyframes fade-in {{
    from {{ opacity: 0; }} to {{ opacity: 1; }}
  }}
  .bottom-bar {{
    position: absolute; bottom: 56px; left: 60px; right: 60px;
    background: rgba(10, 18, 38, 0.75);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 20px; padding: 22px 32px;
    display: flex; align-items: center; gap: 18px;
    backdrop-filter: blur(16px);
    opacity: 0; animation: fade-in {intro_ms}ms 350ms ease-out forwards;
  }}
  .bottom-dot {{ width: 7px; height: 7px; min-width: 7px; border-radius: 50%; background: {accent}; }}
  .bottom-source {{ font-size: 26px; font-weight: 700; color: #a0b8d8; white-space: nowrap; }}
  .bottom-url {{ font-size: 22px; color: #4a6888; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  #fade {{
    position: absolute; inset: 0; z-index: 100;
    background: #000; opacity: 1; pointer-events: none; transition: none;
  }}
</style>
</head>
<body>
  <div class="bg"></div>
  <div class="bg-overlay"></div>
  <div class="content">
    <div class="card">
      <div class="news-badge"><span class="badge-dot"></span>TODAY'S TECH</div>
      <div class="title-text">{display_title}</div>
      <div class="divider"></div>
      <div class="sub-text">{subtitle}</div>
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

# 標準カード（main_* / outro セクション用）
_STANDARD_CARD_TEMPLATE = """\
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
    filter: blur(12px) brightness(0.22) saturate(0.8);
    transform: scale(1.06);
  }}
  .bg-overlay {{
    position: absolute; inset: 0;
    background: linear-gradient(180deg,
      rgba(5, 10, 30, 0.6) 0%, transparent 40%,
      transparent 60%, rgba(5, 10, 30, 0.8) 100%
    );
  }}
  .content {{
    position: relative; z-index: 1; height: 100%;
    display: flex; flex-direction: column;
    justify-content: center; align-items: center;
    padding: 80px 70px;
  }}
  .card {{
    width: 100%;
    background: rgba(12, 22, 45, 0.82);
    border: 1px solid {accent_18};
    border-left: 4px solid {accent};
    border-radius: 36px;
    padding: 56px 60px 64px;
    backdrop-filter: blur(24px);
    -webkit-backdrop-filter: blur(24px);
    box-shadow:
      0 0 0 1px {accent_08},
      0 24px 80px rgba(0, 0, 0, 0.6),
      inset 0 1px 0 rgba(255, 255, 255, 0.06);
    animation: card-enter {intro_ms}ms cubic-bezier(0.16, 1, 0.3, 1) both;
  }}
  @keyframes card-enter {{
    from {{ opacity: 0; transform: translateY(64px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
  }}
  .divider {{
    height: 1px;
    background: linear-gradient(90deg,
      transparent 0%, {accent_35} 30%, {accent_35} 70%, transparent 100%
    );
    margin-bottom: 40px;
    opacity: 0; animation: fade-in {intro_ms}ms 200ms ease-out forwards;
  }}
  .main-text {{
    font-size: 72px; font-weight: 700;
    color: #f0f4ff;
    line-height: 1.4; letter-spacing: 0.01em;
    opacity: 0;
    animation: text-enter {intro_ms}ms 120ms cubic-bezier(0.16, 1, 0.3, 1) forwards;
  }}
  @keyframes text-enter {{
    from {{ opacity: 0; transform: translateY(24px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
  }}
  @keyframes fade-in {{
    from {{ opacity: 0; }} to {{ opacity: 1; }}
  }}
  .bottom-bar {{
    position: absolute; bottom: 56px; left: 60px; right: 60px;
    background: rgba(10, 18, 38, 0.75);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 20px; padding: 22px 32px;
    display: flex; align-items: center; gap: 18px;
    backdrop-filter: blur(16px);
    opacity: 0; animation: fade-in {intro_ms}ms 350ms ease-out forwards;
  }}
  .bottom-dot {{ width: 7px; height: 7px; min-width: 7px; border-radius: 50%; background: {accent}; }}
  .bottom-source {{ font-size: 26px; font-weight: 700; color: #a0b8d8; white-space: nowrap; }}
  .bottom-url {{ font-size: 22px; color: #4a6888; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  #fade {{
    position: absolute; inset: 0; z-index: 100;
    background: #000; opacity: 1; pointer-events: none; transition: none;
  }}
</style>
</head>
<body>
  <div class="bg"></div>
  <div class="bg-overlay"></div>
  <div class="content">
    <div class="card">
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

def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    """#RRGGBB → rgba(r, g, b, alpha)"""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"


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


def _build_html(
    subtitle_text: str,
    source: str,
    source_url: str,
    bg_data_url: str,
    section_type: str = "main",
    display_title: str = "",
) -> str:
    """HTML文字列を組み立てる"""
    style = _SECTION_STYLES.get(section_type, _SECTION_STYLES["main"])
    accent = style["accent"]
    is_title = style.get("is_title", False)

    common = dict(
        width=WIDTH,
        height=HEIGHT,
        intro_ms=int(INTRO_DURATION * 1000),
        bg_data_url=bg_data_url or "",
        source=source,
        source_url=source_url,
        subtitle=html_module.escape(subtitle_text),
        accent=accent,
        accent_08=_hex_to_rgba(accent, 0.08),
        accent_12=_hex_to_rgba(accent, 0.12),
        accent_18=_hex_to_rgba(accent, 0.18),
        accent_20=_hex_to_rgba(accent, 0.20),
        accent_35=_hex_to_rgba(accent, 0.35),
        accent_40=_hex_to_rgba(accent, 0.40),
    )

    if is_title:
        return _TITLE_CARD_TEMPLATE.format(
            display_title=html_module.escape(display_title or subtitle_text),
            **common,
        )
    else:
        return _STANDARD_CARD_TEMPLATE.format(**common)


async def _render_frames_async(
    html: str, times: list[float], outro_start: float, outro_duration: float
) -> list[np.ndarray]:
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
                """([t, outroStart, outroDuration]) => {
                    document.getAnimations({ subtree: true }).forEach(a => {
                        a.currentTime = t * 1000;
                        a.pause();
                    });
                    // フェードオーバーレイ制御（イントロ）
                    const fade = document.getElementById('fade');
                    if (fade) fade.style.opacity = Math.max(0, 1 - t / 0.25);
                    // カードのスクロールアップ（アウトロ）
                    const content = document.querySelector('.content');
                    const bottomBar = document.querySelector('.bottom-bar');
                    if (content && bottomBar) {
                        if (t > outroStart) {
                            const progress = Math.min(1, (t - outroStart) / outroDuration);
                            const ease = progress * progress;
                            const offsetPx = ease * 2000;
                            content.style.transform = 'translateY(-' + offsetPx + 'px)';
                            bottomBar.style.transform = 'translateY(-' + offsetPx + 'px)';
                        } else {
                            content.style.transform = '';
                            bottomBar.style.transform = '';
                        }
                    }
                }""",
                [t, outro_start, outro_duration],
            )
            screenshot = await page.screenshot(type="png")
            img = Image.open(io.BytesIO(screenshot)).convert("RGB")
            frames.append(np.array(img))

        await browser.close()

    return frames


def _render_frames(
    html: str, times: list[float], outro_start: float, outro_duration: float
) -> list[np.ndarray]:
    """同期ラッパー"""
    return asyncio.run(_render_frames_async(html, times, outro_start, outro_duration))


# ---- 公開 API ---------------------------------------------------------------

def generate_animated_clip(
    subtitle_text: str,
    source: str,
    source_url: str,
    duration: float,
    image_url: str | None = None,
    section_type: str = "main",
    display_title: str = "",
) -> VideoClip:
    """HTML/CSS アニメーション付き moviepy VideoClip を返す

    intro/hold/outro の 3 ゾーンでフレームを最小限だけレンダリングし、
    hold フレームは複製することでパフォーマンスを確保する。
    アウトロはカードが上方向へスクロールして退場する。
    """
    outro_start = max(INTRO_DURATION + 0.5, duration - OUTRO_DURATION)

    # 背景画像の準備
    bg_data_url = _image_to_data_url(image_url) if image_url else None
    html = _build_html(
        subtitle_text, source, source_url, bg_data_url or "",
        section_type=section_type, display_title=display_title,
    )

    # レンダリングが必要な時刻リスト
    intro_times = [i / FPS for i in range(int(INTRO_DURATION * FPS) + 1)]
    hold_times  = [INTRO_DURATION + 0.01]   # 1枚だけ
    outro_times = [
        outro_start + i / FPS
        for i in range(int(OUTRO_DURATION * FPS) + 1)
    ]
    all_times = intro_times + hold_times + outro_times

    logger.info("フレームレンダリング開始: %d 枚", len(all_times))
    rendered = _render_frames(html, all_times, outro_start, OUTRO_DURATION)

    # インデックス分割
    n_intro = len(intro_times)
    intro_frames = rendered[:n_intro]
    hold_frame   = rendered[n_intro]
    outro_frames = rendered[n_intro + 1:]

    # hold フレームの枚数
    n_hold = max(1, round((outro_start - INTRO_DURATION) * FPS))
    all_frames = intro_frames + [hold_frame] * n_hold + outro_frames

    def make_frame(t: float) -> np.ndarray:
        idx = min(int(t * FPS), len(all_frames) - 1)
        return all_frames[idx]

    logger.info("アニメーションクリップ準備完了: duration=%.1fs, frames=%d", duration, len(all_frames))
    return VideoClip(make_frame, duration=duration)


_BACKGROUND_ONLY_TEMPLATE = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    width: {width}px; height: {height}px;
    background: #0d1117; overflow: hidden; position: relative;
  }}
  .bg {{
    position: absolute; inset: 0;
    background-image: url('{bg_data_url}');
    background-size: cover; background-position: center;
    filter: blur(12px) brightness(0.22) saturate(0.8);
    transform: scale(1.06);
  }}
  .bg-overlay {{
    position: absolute; inset: 0;
    background: linear-gradient(180deg,
      rgba(5, 10, 30, 0.6) 0%, transparent 40%,
      transparent 60%, rgba(5, 10, 30, 0.8) 100%
    );
  }}
</style>
</head>
<body>
  <div class="bg"></div>
  <div class="bg-overlay"></div>
</body>
</html>
"""


def generate_background_clip(duration: float, image_url: str | None = None) -> VideoClip:
    """背景画像のみ（カードなし）の静止クリップを返す。セクション間のギャップ用。"""
    bg_data_url = _image_to_data_url(image_url) if image_url else ""
    html = _BACKGROUND_ONLY_TEMPLATE.format(
        width=WIDTH, height=HEIGHT, bg_data_url=bg_data_url
    )
    frames = _render_frames(html, [0.0], outro_start=999, outro_duration=OUTRO_DURATION)
    frame = frames[0]

    def make_frame(_t: float) -> np.ndarray:
        return frame

    return VideoClip(make_frame, duration=duration)
