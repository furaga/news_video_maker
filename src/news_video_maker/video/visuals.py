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

from news_video_maker.config import CHANNEL_NAME

logger = logging.getLogger(__name__)

WIDTH, HEIGHT = 1080, 1920
FPS = 30
INTRO_DURATION = 0.6   # スクロールアニメーション時間
OUTRO_DURATION = 0.4   # アウトロスクロール時間

# セクションタイプごとの視覚スタイル定義
_SECTION_STYLES: dict[str, dict] = {
    "hook":   {"badge": CHANNEL_NAME,   "accent": "#00dcc2", "card_bg": "rgba(0, 55, 58, 0.90)",  "is_title": True,  "number": ""},
    "main_1": {"badge": "概要",         "accent": "#00dcc2", "card_bg": "rgba(0, 28, 50, 0.86)",  "number": "01"},
    "main_2": {"badge": "詳細",         "accent": "#4a8fff", "card_bg": "rgba(8, 22, 62, 0.86)",  "number": "02"},
    "main_3": {"badge": "関連情報",     "accent": "#a855f7", "card_bg": "rgba(30, 8, 58, 0.86)",  "number": "03"},
    "main_4": {"badge": "補足",         "accent": "#f59e0b", "card_bg": "rgba(42, 22, 4, 0.86)",  "number": "04"},
    "main":   {"badge": "解説",         "accent": "#00dcc2", "card_bg": "rgba(12, 22, 45, 0.84)", "number": ""},
    "outro":  {"badge": "まとめ",       "accent": "#22c55e", "card_bg": "rgba(4, 34, 18, 0.86)",  "number": ""},
}

# ---- HTML テンプレート -------------------------------------------------------

# スクロールスタック全体テンプレート（全セクション共通）
_SCROLLING_STACK_TEMPLATE = """\
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
    filter: blur(12px) brightness(0.20) saturate(0.8);
    transform: scale(1.06);
  }}
  .bg-overlay {{
    position: absolute; inset: 0;
    background: linear-gradient(180deg,
      rgba(5,10,30,0.75) 0%, rgba(5,10,30,0.15) 35%,
      rgba(5,10,30,0.15) 65%, rgba(5,10,30,0.75) 100%
    );
  }}
  /* カードスタック：translateYはJSで制御 */
  #stack {{
    position: absolute;
    left: 70px; right: 70px; top: 0;
    display: flex; flex-direction: column; gap: 20px;
  }}
  /* ---- 全カード共通レイアウト ---- */
  .card {{
    border-radius: 36px;
    padding: 50px 60px 58px;
    backdrop-filter: blur(24px);
    -webkit-backdrop-filter: blur(24px);
  }}
  /* ---- アクティブカード（追加スタイルのみ） ---- */
  .card.active {{
  }}
  .news-badge {{
    display: inline-flex; align-items: center; gap: 12px;
    font-size: 28px; font-weight: 700;
    letter-spacing: 0.18em; text-transform: uppercase;
    margin-bottom: 28px;
    opacity: 0;
    animation: fade-in {intro_ms}ms 100ms ease-out forwards;
  }}
  .badge-dot {{
    width: 11px; height: 11px; border-radius: 50%;
  }}
  .title-text {{
    font-size: 60px; font-weight: 700;
    color: #ffffff; line-height: 1.35;
    margin-bottom: 28px;
    opacity: 0;
    animation: text-enter {intro_ms}ms 80ms cubic-bezier(0.16, 1, 0.3, 1) forwards;
  }}
  .sub-text {{
    font-size: 42px; font-weight: 500;
    color: #a0c0e0; line-height: 1.4;
    opacity: 0;
    animation: fade-in {intro_ms}ms 250ms ease-out forwards;
  }}
  .card-header {{
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 22px;
    opacity: 0;
    animation: fade-in {intro_ms}ms 120ms ease-out forwards;
  }}
  .badge {{
    font-size: 27px; font-weight: 700;
    letter-spacing: 0.12em;
    padding: 8px 22px; border-radius: 10px;
    border: 2px solid transparent;
  }}
  .section-number {{
    font-size: 58px; font-weight: 700;
    letter-spacing: 0.05em; line-height: 1;
  }}
  .divider {{
    height: 1px; margin-bottom: 34px;
    opacity: 0;
    animation: fade-in {intro_ms}ms 180ms ease-out forwards;
  }}
  .main-text {{
    font-size: 68px; font-weight: 700;
    color: #f0f4ff; line-height: 1.4;
    opacity: 0;
    animation: text-enter {intro_ms}ms 80ms cubic-bezier(0.16, 1, 0.3, 1) forwards;
  }}
  @keyframes text-enter {{
    from {{ opacity: 0; transform: translateY(20px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
  }}
  @keyframes fade-in {{
    from {{ opacity: 0; }} to {{ opacity: 1; }}
  }}
  /* ---- 非アクティブカード（フルサイズ・透明度のみ下げる） ---- */
  .card.inactive {{
    opacity: 0.42;
  }}
  /* 非アクティブカードの内部要素はアニメーションせず最終状態で表示 */
  .card.inactive * {{
    animation: none !important;
    opacity: 1 !important;
    transform: none !important;
  }}
  /* ---- ボトムバー ---- */
  .bottom-bar {{
    position: absolute; bottom: 56px; left: 60px; right: 60px;
    background: rgba(10, 18, 38, 0.75);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 20px; padding: 22px 32px;
    display: flex; align-items: center; gap: 18px;
    backdrop-filter: blur(16px);
    opacity: 0;
    animation: fade-in {intro_ms}ms 320ms ease-out forwards;
  }}
  .bottom-dot {{ width: 7px; height: 7px; min-width: 7px; border-radius: 50%; }}
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
  <div id="stack">
    {cards_html}
  </div>
  <div class="bottom-bar">
    <div class="bottom-dot" style="background:{accent}"></div>
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


# 画像URLのキャッシュ
_bg_cache: dict[str, str | None] = {}


def _image_to_data_url(image_url: str) -> str | None:
    """記事画像をダウンロードして base64 data URL に変換する（キャッシュ付き）"""
    if image_url in _bg_cache:
        return _bg_cache[image_url]
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
        result = f"data:{content_type};base64,{b64}"
    except Exception as e:
        logger.warning("記事画像の取得に失敗: %s", e)
        result = None
    _bg_cache[image_url] = result
    return result


def _build_stack_html_cards(all_cards: list[dict], active_idx: int) -> str:
    """全カードのHTML片を生成する（アクティブ/非アクティブ振り分け）"""
    parts = []
    for i, card in enumerate(all_cards):
        is_active = (i == active_idx)
        section_type = card.get("section_type", "main")
        style = _SECTION_STYLES.get(section_type, _SECTION_STYLES["main"])
        accent = style["accent"]
        card_bg = style["card_bg"]
        badge = html_module.escape(card.get("badge", ""))
        subtitle = html_module.escape(card.get("subtitle_text", ""))

        acc_08 = _hex_to_rgba(accent, 0.08)
        acc_18 = _hex_to_rgba(accent, 0.18)
        acc_20 = _hex_to_rgba(accent, 0.20)
        acc_30 = _hex_to_rgba(accent, 0.30)
        acc_35 = _hex_to_rgba(accent, 0.35)
        acc_40 = _hex_to_rgba(accent, 0.40)

        if is_active:
            is_title = style.get("is_title", False)
            if is_title:
                display_title = html_module.escape(card.get("display_title", "") or card.get("subtitle_text", ""))
                content = (
                    f'<div class="news-badge" style="color:{accent}">'
                    f'<span class="badge-dot" style="background:{accent};box-shadow:0 0 8px {accent}"></span>'
                    f'{badge}</div>'
                    f'<div class="title-text">{display_title}</div>'
                    f'<div class="divider" style="background:linear-gradient(90deg,transparent,{acc_35},transparent)"></div>'
                    f'<div class="sub-text">{subtitle}</div>'
                )
                border = f"border-top: 4px solid {accent}"
            else:
                number = html_module.escape(style.get("number", ""))
                content = (
                    f'<div class="card-header">'
                    f'<div class="badge" style="color:{accent};border-color:{acc_40};background:{acc_08}">{badge}</div>'
                    f'<div class="section-number" style="color:{acc_20}">{number}</div>'
                    f'</div>'
                    f'<div class="divider" style="background:linear-gradient(90deg,transparent,{acc_35},transparent)"></div>'
                    f'<div class="main-text">{subtitle}</div>'
                )
                border = f"border-left: 4px solid {accent}"

            parts.append(
                f'<div class="card active" style="'
                f'background:{card_bg};border:1px solid {acc_18};{border};'
                f'box-shadow:0 0 0 1px {acc_08},0 24px 80px rgba(0,0,0,0.65),'
                f'inset 0 1px 0 rgba(255,255,255,0.06)">'
                f'{content}'
                f'</div>'
            )
        else:
            # 非アクティブ：アクティブと同じフルサイズ構造（透明度のみ下げる）
            number = html_module.escape(style.get("number", ""))
            is_title = style.get("is_title", False)
            if is_title:
                content = (
                    f'<div class="news-badge" style="color:{accent}">'
                    f'<span class="badge-dot" style="background:{accent}"></span>'
                    f'{badge}</div>'
                    f'<div class="title-text" style="opacity:1;transform:none">{subtitle}</div>'
                )
                border = f"border-top: 4px solid {accent}"
            else:
                content = (
                    f'<div class="card-header">'
                    f'<div class="badge" style="color:{accent};border-color:{acc_40};background:{acc_08}">{badge}</div>'
                    f'<div class="section-number" style="color:{acc_20}">{number}</div>'
                    f'</div>'
                    f'<div class="divider" style="background:linear-gradient(90deg,transparent,{acc_35},transparent)"></div>'
                    f'<div class="main-text" style="opacity:1;transform:none">{subtitle}</div>'
                )
                border = f"border-left: 4px solid {accent}"
            parts.append(
                f'<div class="card inactive" style="'
                f'background:{card_bg};border:1px solid {acc_18};{border};'
                f'box-shadow:0 0 0 1px {acc_08},0 24px 80px rgba(0,0,0,0.65),'
                f'inset 0 1px 0 rgba(255,255,255,0.06)">'
                f'{content}'
                f'</div>'
            )

    return "\n".join(parts)


def _build_html(
    all_cards: list[dict],
    active_idx: int,
    source: str,
    source_url: str,
    bg_data_url: str,
) -> str:
    """スクロールスタック HTML を組み立てる"""
    style = _SECTION_STYLES.get(
        all_cards[active_idx].get("section_type", "main"),
        _SECTION_STYLES["main"],
    )
    accent = style["accent"]
    cards_html = _build_stack_html_cards(all_cards, active_idx)
    return _SCROLLING_STACK_TEMPLATE.format(
        width=WIDTH,
        height=HEIGHT,
        intro_ms=int(INTRO_DURATION * 1000),
        bg_data_url=bg_data_url or "",
        source=source,
        source_url=source_url,
        accent=accent,
        cards_html=cards_html,
    )


async def _render_frames_async(
    html: str,
    duration: float,
    prev_top: float | None,
    has_outro: bool,
) -> tuple[list[np.ndarray], float]:
    """Playwright でフレームをレンダリングし、(frames, curr_top) を返す

    curr_top: アクティブカードが画面中央に来るときのスタックの translateY 値
    """
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})
        await page.set_content(html, wait_until="networkidle")

        # アクティブカードの自然なレイアウト位置を測定
        # （CSS アニメーション・transform を一時無効にして純粋なレイアウト高さを取得）
        card_center = await page.evaluate("""() => {
            const style = document.createElement('style');
            style.id = 'measure-override';
            style.textContent = '* { animation: none !important; transition: none !important; transform: none !important; opacity: 1 !important; }';
            document.head.appendChild(style);
            const card = document.querySelector('.card.active');
            const rect = card.getBoundingClientRect();
            const center = rect.top + rect.height / 2;
            document.head.removeChild(style);
            return center;
        }""")

        # アクティブカードを画面中央 (HEIGHT/2) に合わせる translateY
        curr_top = HEIGHT / 2 - card_center

        # 前セクションの終了位置（スクロール開始点）
        from_top = (curr_top + 700) if prev_top is None else prev_top

        outro_start = max(INTRO_DURATION + 0.5, duration - OUTRO_DURATION)

        # レンダリング時刻リスト
        intro_times = [i / FPS for i in range(int(INTRO_DURATION * FPS) + 1)]
        hold_times  = [INTRO_DURATION + 0.01]
        outro_times = (
            [outro_start + i / FPS for i in range(int(OUTRO_DURATION * FPS) + 1)]
            if has_outro else []
        )
        all_times = intro_times + hold_times + outro_times

        logger.info("フレームレンダリング開始: %d 枚 (curr_top=%.1f, from_top=%.1f)", len(all_times), curr_top, from_top)

        frames: list[np.ndarray] = []
        for t in all_times:
            await page.evaluate(
                """([t, fromTop, currTop, introDuration, outroStart, outroDuration, hasOutro]) => {
                    // CSS アニメーション（テキストのフェードイン等）をシーク
                    document.getAnimations({ subtree: true }).forEach(a => {
                        a.currentTime = t * 1000;
                        a.pause();
                    });

                    // フェードオーバーレイは常に非表示
                    const fade = document.getElementById('fade');
                    fade.style.opacity = 0;

                    // スタックの translateY を計算
                    const stack = document.getElementById('stack');
                    const bottomBar = document.querySelector('.bottom-bar');
                    let stackY;

                    if (t <= introDuration) {
                        // イントロ: fromTop → currTop へスクロール（cubic ease-out）
                        const p = t / introDuration;
                        const ease = 1 - Math.pow(1 - p, 3);
                        stackY = fromTop + (currTop - fromTop) * ease;
                    } else if (hasOutro && t > outroStart) {
                        // アウトロ: currTop からさらに上へスクロール
                        const p = Math.min(1, (t - outroStart) / outroDuration);
                        const ease = p * p;
                        const extra = ease * 700;
                        stackY = currTop - extra;
                        bottomBar.style.transform = 'translateY(-' + extra + 'px)';
                    } else {
                        stackY = currTop;
                        bottomBar.style.transform = '';
                    }

                    stack.style.transform = 'translateY(' + stackY + 'px)';
                }""",
                [t, from_top, curr_top, INTRO_DURATION, outro_start, OUTRO_DURATION, has_outro],
            )
            screenshot = await page.screenshot(type="png")
            img = Image.open(io.BytesIO(screenshot)).convert("RGB")
            frames.append(np.array(img))

        await browser.close()

    return frames, curr_top


def _render_frames(
    html: str,
    duration: float,
    prev_top: float | None,
    has_outro: bool,
) -> tuple[list[np.ndarray], float]:
    """同期ラッパー"""
    return asyncio.run(_render_frames_async(html, duration, prev_top, has_outro))


# ---- 公開 API ---------------------------------------------------------------

def get_card_info(section_type: str, subtitle_text: str) -> dict:
    """カード情報dictを返す（composer.py で all_cards リストを組み立てるために使う）"""
    style = _SECTION_STYLES.get(section_type, _SECTION_STYLES["main"])
    return {
        "section_type": section_type,
        "subtitle_text": subtitle_text,
        "badge": style.get("badge", ""),
        "accent": style["accent"],
        "card_bg": style["card_bg"],
        "display_title": "",   # hook セクションのみ composer.py 側で設定する
    }


def generate_animated_clip(
    all_cards: list[dict],
    active_idx: int,
    source: str,
    source_url: str,
    duration: float,
    image_url: str | None = None,
    has_outro: bool = False,
    prev_top: float | None = None,
) -> tuple[VideoClip, float]:
    """HTML/CSS スクロールスタックアニメーション付き VideoClip を返す

    Returns:
        (VideoClip, curr_top): クリップと次セクションへ渡す curr_top 値
    """
    bg_data_url = _image_to_data_url(image_url) if image_url else None
    html = _build_html(all_cards, active_idx, source, source_url, bg_data_url or "")

    rendered, curr_top = _render_frames(html, duration, prev_top, has_outro)

    # intro / hold / outro に分割
    n_intro = int(INTRO_DURATION * FPS) + 1
    intro_frames = rendered[:n_intro]
    hold_frame   = rendered[n_intro]
    outro_frames = rendered[n_intro + 1:]

    outro_start = max(INTRO_DURATION + 0.5, duration - OUTRO_DURATION)
    n_hold = max(1, round((outro_start - INTRO_DURATION) * FPS))
    all_frames = intro_frames + [hold_frame] * n_hold + outro_frames

    def make_frame(t: float) -> np.ndarray:
        idx = min(int(t * FPS), len(all_frames) - 1)
        return all_frames[idx]

    logger.info("クリップ完了: duration=%.1fs, curr_top=%.1f", duration, curr_top)
    return VideoClip(make_frame, duration=duration), curr_top
