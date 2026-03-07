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
INTRO_DURATION = 0.6   # スクロールアニメーション時間

# スタックレイアウトの定数
CARD_HEIGHT = 280    # 固定カード高（px）
CARD_GAP = 60        # カード間隔（px）
CARD_STEP = CARD_HEIGHT + CARD_GAP  # 340px

# 上ゾーン（記事プレビュー）の定数
SCREENSHOT_HEIGHT = 700  # 記事プレビューゾーンの高さ（px）
STACK_CENTER = SCREENSHOT_HEIGHT + (HEIGHT - SCREENSHOT_HEIGHT) // 2  # = 1310

# セクションタイプごとのアクセントカラー定義
_SECTION_STYLES: dict[str, dict] = {
    "hook":   {"accent": "#00dcc2"},
    "main_1": {"accent": "#00dcc2"},
    "main_2": {"accent": "#4a8fff"},
    "main_3": {"accent": "#a855f7"},
    "main_4": {"accent": "#f59e0b"},
    "main_5": {"accent": "#f59e0b"},
    "main_6": {"accent": "#22c55e"},
    "main":   {"accent": "#00dcc2"},
    "outro":  {"accent": "#22c55e"},
}

# ---- HTML テンプレート -------------------------------------------------------

_STACK_TEMPLATE = """\
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
      rgba(5, 10, 30, 0.75) 0%, rgba(5, 10, 30, 0.3) 30%,
      rgba(5, 10, 30, 0.3) 70%, rgba(5, 10, 30, 0.8) 100%
    );
  }}
  /* --- 記事プレビューゾーン (上ゾーン: 0〜{screenshot_height}px) --- */
  .article-preview {{
    position: absolute;
    top: 0; left: 0; right: 0;
    height: {screenshot_height}px;
    overflow: hidden;
    display: flex; flex-direction: column;
    z-index: 10;
  }}
  .browser-chrome {{
    flex-shrink: 0;
    height: 60px;
    background: #1e2433;
    border-bottom: 1px solid rgba(255,255,255,0.08);
    display: flex; align-items: center; gap: 12px;
    padding: 0 24px;
  }}
  .chrome-dot {{ width: 14px; height: 14px; border-radius: 50%; }}
  .chrome-dot.red    {{ background: #ff5f57; }}
  .chrome-dot.yellow {{ background: #ffbd2e; }}
  .chrome-dot.green  {{ background: #28c940; }}
  .chrome-urlbar {{
    flex: 1; height: 34px;
    background: #0d1117; border-radius: 8px;
    display: flex; align-items: center; padding: 0 14px;
    font-size: 22px; color: #6a7a8a;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }}
  .article-image {{
    flex: 1;
    background-image: url('{bg_data_url}');
    background-size: cover; background-position: center top;
  }}
  .article-headline {{
    flex-shrink: 0;
    min-height: 210px;
    background: rgba(10, 15, 30, 0.92);
    padding: 24px 48px;
    display: flex; align-items: center;
    font-size: 52px; font-weight: 700;
    color: #f0f4ff; line-height: 1.45;
    border-top: 2px solid rgba(0, 220, 194, 0.35);
    overflow: hidden;
  }}
  #stack {{
    position: absolute;
    left: 70px; right: 70px;
    top: {screenshot_height}px;
  }}
  .card {{
    height: {card_height}px;
    width: 100%;
    background: rgba(12, 22, 45, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-left-width: 4px;
    border-left-style: solid;
    border-radius: 36px;
    margin-bottom: {card_gap}px;
    padding: 0 60px;
    display: flex; align-items: center;
    opacity: 0.35;
  }}
  .card-text {{
    font-size: 60px; font-weight: 700;
    color: #f0f4ff;
    line-height: 1.4; letter-spacing: 0.01em;
  }}
  .bottom-bar {{
    position: absolute; bottom: 56px; left: 60px; right: 60px;
    background: rgba(10, 18, 38, 0.75);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 20px; padding: 22px 32px;
    display: flex; align-items: center; gap: 18px;
    backdrop-filter: blur(16px);
  }}
  .bottom-dot {{ width: 7px; height: 7px; min-width: 7px; border-radius: 50%; background: #00dcc2; }}
  .bottom-source {{ font-size: 26px; font-weight: 700; color: #a0b8d8; white-space: nowrap; }}
  .bottom-url {{ font-size: 22px; color: #4a6888; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  #fade {{
    position: absolute; inset: 0; z-index: 100;
    background: #000; opacity: 0; pointer-events: none;
  }}
</style>
</head>
<body>
  <div class="bg"></div>
  <div class="bg-overlay"></div>
  <div class="article-preview">
    <div class="browser-chrome">
      <div class="chrome-dot red"></div>
      <div class="chrome-dot yellow"></div>
      <div class="chrome-dot green"></div>
      <div class="chrome-urlbar">{source_url}</div>
    </div>
    <div class="article-image"></div>
    <div class="article-headline">{article_title}</div>
  </div>
  <div id="stack">
{cards_html}
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

def image_to_data_url(image_url: str) -> str | None:
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


def _build_stack_html(
    all_cards: list[dict],
    active_index: int,
    prev_index: int,
    source: str,
    source_url: str,
    bg_data_url: str,
    article_title: str = "",
) -> str:
    """全カードを縦積みにしたHTML文字列を組み立てる"""
    cards_html = ""
    for card in all_cards:
        style = _SECTION_STYLES.get(card["type"], _SECTION_STYLES["main"])
        accent = style["accent"]
        subtitle = html_module.escape(card["subtitle"])
        cards_html += f'    <div class="card" style="border-left-color: {accent};"><div class="card-text">{subtitle}</div></div>\n'

    return _STACK_TEMPLATE.format(
        width=WIDTH,
        height=HEIGHT,
        bg_data_url=bg_data_url or "",
        source=html_module.escape(source),
        source_url=html_module.escape(source_url),
        card_height=CARD_HEIGHT,
        card_gap=CARD_GAP,
        cards_html=cards_html,
        screenshot_height=SCREENSHOT_HEIGHT,
        article_title=html_module.escape(article_title),
    )


async def _render_stack_frames_async(
    html: str,
    times: list[float],
    active_index: int,
    prev_index: int,
) -> list[np.ndarray]:
    """Playwright でスタックフレームをレンダリングする"""
    from playwright.async_api import async_playwright

    frames: list[np.ndarray] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})
        await page.set_content(html, wait_until="networkidle")

        for t in times:
            await page.evaluate(
                """([t, prevIdx, activeIdx, introDuration, cardStep, stackCenter, cardHalfH]) => {
                    const stack = document.getElementById('stack');
                    const cards = stack.querySelectorAll('.card');
                    const fade = document.getElementById('fade');

                    const prevOffset = stackCenter - (prevIdx * cardStep + cardHalfH);
                    const currentOffset = stackCenter - (activeIdx * cardStep + cardHalfH);

                    let offset, progress;
                    if (prevIdx === activeIdx) {
                        // 最初のカード: スクロールなし、フェードイン
                        offset = currentOffset;
                        progress = 1;
                        if (fade) fade.style.opacity = Math.max(0, 1 - t / introDuration);
                    } else {
                        if (fade) fade.style.opacity = 0;
                        if (t < introDuration) {
                            const raw = t / introDuration;
                            const eased = raw * raw * (3 - 2 * raw);
                            offset = prevOffset + (currentOffset - prevOffset) * eased;
                            progress = eased;
                        } else {
                            offset = currentOffset;
                            progress = 1;
                        }
                    }

                    stack.style.transform = 'translateY(' + offset + 'px)';

                    // カード不透明度の補間
                    cards.forEach((card, i) => {
                        let opacity;
                        if (prevIdx === activeIdx) {
                            opacity = i === activeIdx ? 1.0 : 0.35;
                        } else if (i === activeIdx && i === prevIdx) {
                            opacity = 1.0;
                        } else if (i === activeIdx) {
                            opacity = 0.35 + 0.65 * progress;
                        } else if (i === prevIdx) {
                            opacity = 1.0 - 0.65 * progress;
                        } else {
                            opacity = 0.35;
                        }
                        card.style.opacity = opacity;
                    });
                }""",
                [t, prev_index, active_index, INTRO_DURATION,
                 CARD_STEP, STACK_CENTER, CARD_HEIGHT // 2],
            )
            screenshot = await page.screenshot(type="png")
            img = Image.open(io.BytesIO(screenshot)).convert("RGB")
            frames.append(np.array(img))

        await browser.close()

    return frames


def _render_stack_frames(
    html: str,
    times: list[float],
    active_index: int,
    prev_index: int,
) -> list[np.ndarray]:
    """同期ラッパー"""
    return asyncio.run(_render_stack_frames_async(html, times, active_index, prev_index))


# ---- 公開 API ---------------------------------------------------------------

def generate_stack_clip(
    all_cards: list[dict],
    active_index: int,
    prev_index: int,
    source: str,
    source_url: str,
    duration: float,
    bg_data_url: str = "",
    article_title: str = "",
) -> VideoClip:
    """全カードを縦積みにして、active_index のカードを中央に表示する VideoClip を返す。

    all_cards: [{"subtitle": str, "type": str}] のリスト（全セクション分）
    active_index: 現在表示するカードのインデックス
    prev_index: ひとつ前のカードのインデックス（スクロールアニメーション用）
    article_title: 記事プレビューゾーンに表示する記事見出し
    """
    html = _build_stack_html(all_cards, active_index, prev_index, source, source_url, bg_data_url, article_title)

    # イントロ + ホールドの2段階レンダリング
    intro_times = [i / FPS for i in range(int(INTRO_DURATION * FPS) + 1)]
    hold_times = [INTRO_DURATION + 0.01]
    all_times = intro_times + hold_times

    logger.info("スタックフレームレンダリング開始: card=%d/%d, frames=%d",
                active_index + 1, len(all_cards), len(all_times))
    rendered = _render_stack_frames(html, all_times, active_index, prev_index)

    intro_frames = rendered[:len(intro_times)]
    hold_frame = rendered[len(intro_times)]

    n_hold = max(1, round((duration - INTRO_DURATION) * FPS))
    all_frames = intro_frames + [hold_frame] * n_hold

    def make_frame(t: float) -> np.ndarray:
        idx = min(int(t * FPS), len(all_frames) - 1)
        return all_frames[idx]

    logger.info("スタッククリップ準備完了: duration=%.1fs, frames=%d", duration, len(all_frames))
    return VideoClip(make_frame, duration=duration)
