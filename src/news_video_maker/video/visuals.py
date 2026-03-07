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
SCREENSHOT_HEIGHT = 550   # 記事プレビューゾーンの高さ（px）
CARD_TOP_PADDING = 40     # 記事プレビューとカードの間隔（px）
# translateY は #stack の top 位置からの相対: stackCenter = CARD_TOP_PADDING + CARD_HEIGHT // 2
STACK_CENTER = CARD_TOP_PADDING + CARD_HEIGHT // 2  # = 180

# ソース別ブランドカラー
SOURCE_COLORS: dict[str, str] = {
    "techcrunch": "#1a7f37",
    "arstechnica": "#dd3333",
    "theverge": "#fa4718",
    "hackernews": "#ff6600",
}

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
  /* 記事プレビューゾーン: 記事ページのスクリーンショットを全幅表示 */
  .article-preview {{
    position: absolute;
    top: 0; left: 0; right: 0;
    height: {screenshot_height}px;
    z-index: 10;
    overflow: hidden;
  }}
  .article-img-panel {{
    width: 100%; height: 100%;
    background-image: url('{bg_data_url}');
    background-size: 100% 100%;
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
    <div class="article-img-panel"></div>
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


_SCREENSHOT_VIEWPORT_W = 1200
_SCREENSHOT_VIEWPORT_H = _SCREENSHOT_VIEWPORT_W * 2  # 2400px（横幅×2）


_CLAUDE_PREVIEW_W = 600   # Claude に渡すプレビュー画像の幅（処理を軽くするため縮小）


def _get_best_crop_y(orig_img: Image.Image) -> int:
    """Claude Code (claude -p --allowedTools Read) で最適クロップY位置を返す。失敗時は 0。

    orig_img: 元のフルページスクリーンショット（リサイズ前）
    戻り値: 元画像座標でのクロップY位置
    """
    import os
    import re
    import subprocess
    import tempfile

    orig_w, orig_h = orig_img.size
    panel_h_in_orig = int(SCREENSHOT_HEIGHT * orig_w / WIDTH)  # 元画像座標でのパネル高
    max_y = orig_h - panel_h_in_orig
    if max_y <= 0:
        return 0

    # Claude 用プレビュー画像を作成（幅を縮小してファイルサイズを削減）
    preview_scale = _CLAUDE_PREVIEW_W / orig_w
    preview_h = int(orig_h * preview_scale)
    preview_img = orig_img.resize((_CLAUDE_PREVIEW_W, preview_h), Image.LANCZOS)
    panel_h_in_preview = int(panel_h_in_orig * preview_scale)
    max_y_preview = preview_h - panel_h_in_preview

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            preview_img.save(f, format="PNG")
            tmp_path = f.name

        prompt = (
            f"Read the image at {tmp_path}. "
            f"This is a news article page screenshot ({preview_h}px tall, {_CLAUDE_PREVIEW_W}px wide). "
            f"I need a {panel_h_in_preview}px-tall crop for a short video thumbnail. "
            f"Which Y offset (integer, 0 to {max_y_preview}) shows the most visually interesting content "
            "(article hero image, main photo)? Skip navigation bars and headers. "
            "Reply with ONLY a single integer."
        )
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
        result = subprocess.run(
            ["claude", "-p", prompt, "--allowedTools", "Read"],
            capture_output=True, text=True, timeout=120,
            env=env,
        )
        numbers = re.findall(r"\d+", result.stdout)
        if not numbers:
            raise ValueError(f"整数が見つからない: {result.stdout!r}")
        y_preview = int(numbers[-1])
        y_preview = max(0, min(y_preview, max_y_preview))
        # プレビュー座標を元画像座標に変換
        y_orig = int(y_preview / preview_scale)
        return max(0, min(y_orig, max_y))
    except Exception as e:
        logger.warning("Claude Code クロップ判定失敗、y=0 にフォールバック: %s", e)
        return 0
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


async def _screenshot_article_url_async(url: str) -> str | None:
    """Playwright でページ全体をキャプチャし、Claude Code で最適クロップして data URL を返す"""
    from news_video_maker.config import IMAGES_DIR

    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(
                viewport={"width": _SCREENSHOT_VIEWPORT_W, "height": _SCREENSHOT_VIEWPORT_H}
            )
            await page.goto(url, wait_until="load", timeout=30000)
            # viewport 範囲のみキャプチャ（横幅×2高さ = 1200×2400px）
            screenshot_bytes = await page.screenshot(type="png")
            await browser.close()

        # 元スクリーンショットを保存（デバッグ用）
        orig_path = IMAGES_DIR / "article_screenshot_orig.png"
        orig_path.write_bytes(screenshot_bytes)
        img = Image.open(io.BytesIO(screenshot_bytes))
        logger.info("スクリーンショット取得完了: %dx%d → %s", img.width, img.height, orig_path)

        # Claude Code でベストクロップY位置を判定（元画像を渡す）
        crop_y = _get_best_crop_y(img)
        logger.info("クロップY位置: %d (元画像座標)", crop_y)

        # Pillow でリサイズ → クロップ（WIDTH x SCREENSHOT_HEIGHT に整形）
        scale = WIDTH / img.width
        new_h = int(img.height * scale)
        img_resized = img.resize((WIDTH, new_h), Image.LANCZOS)
        crop_y_scaled = int(crop_y * scale)
        img_cropped = img_resized.crop(
            (0, crop_y_scaled, WIDTH, crop_y_scaled + SCREENSHOT_HEIGHT)
        )

        # クロップ済み画像を保存（デバッグ用）
        crop_path = IMAGES_DIR / "article_screenshot_crop.png"
        img_cropped.save(crop_path)
        logger.info("クロップ済み画像保存: %s", crop_path)

        buf = io.BytesIO()
        img_cropped.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        return f"data:image/png;base64,{b64}"
    except Exception as e:
        logger.warning("記事ページのスクリーンショット取得に失敗: %s", e)
        return None


def screenshot_article_url(url: str) -> str | None:
    """記事ページのスクリーンショットを撮り base64 data URL を返す（同期ラッパー）"""
    return asyncio.run(_screenshot_article_url_async(url))


def _build_stack_html(
    all_cards: list[dict],
    active_index: int,
    prev_index: int,
    source: str,
    source_url: str,
    bg_data_url: str,
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
    )


async def _render_stack_frames_async(
    html: str,
    times: list[float],
    active_index: int,
    prev_index: int,
    section_start: float = 0.0,
    total_duration: float = 60.0,
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
                """([t, prevIdx, activeIdx, introDuration, cardStep, stackCenter, cardHalfH, sectionStart, totalDuration]) => {
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

                    // Ken Burns: 背景をゆっくりズーム（全体で 1.06 → 1.14）
                    const globalT = sectionStart + t;
                    const bgScale = 1.06 + 0.08 * (globalT / totalDuration);
                    const bgEl = document.querySelector('.bg');
                    if (bgEl) bgEl.style.transform = 'scale(' + bgScale + ')';
                }""",
                [t, prev_index, active_index, INTRO_DURATION,
                 CARD_STEP, STACK_CENTER, CARD_HEIGHT // 2,
                 section_start, total_duration],
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
    section_start: float = 0.0,
    total_duration: float = 60.0,
) -> list[np.ndarray]:
    """同期ラッパー"""
    return asyncio.run(_render_stack_frames_async(
        html, times, active_index, prev_index, section_start, total_duration
    ))


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
    source_color: str = "#1a7f37",
    section_start: float = 0.0,
    total_duration: float = 60.0,
) -> VideoClip:
    """全カードを縦積みにして、active_index のカードを中央に表示する VideoClip を返す。

    all_cards: [{"subtitle": str, "type": str}] のリスト（全セクション分）
    active_index: 現在表示するカードのインデックス
    prev_index: ひとつ前のカードのインデックス（スクロールアニメーション用）
    """
    html = _build_stack_html(
        all_cards, active_index, prev_index,
        source, source_url, bg_data_url,
    )

    # イントロ + ホールドの2段階レンダリング
    intro_times = [i / FPS for i in range(int(INTRO_DURATION * FPS) + 1)]
    hold_times = [INTRO_DURATION + 0.01]
    all_times = intro_times + hold_times

    logger.info("スタックフレームレンダリング開始: card=%d/%d, frames=%d",
                active_index + 1, len(all_cards), len(all_times))
    rendered = _render_stack_frames(
        html, all_times, active_index, prev_index, section_start, total_duration
    )

    intro_frames = rendered[:len(intro_times)]
    hold_frame = rendered[len(intro_times)]

    n_hold = max(1, round((duration - INTRO_DURATION) * FPS))
    all_frames = intro_frames + [hold_frame] * n_hold

    def make_frame(t: float) -> np.ndarray:
        idx = min(int(t * FPS), len(all_frames) - 1)
        return all_frames[idx]

    logger.info("スタッククリップ準備完了: duration=%.1fs, frames=%d", duration, len(all_frames))
    return VideoClip(make_frame, duration=duration)
