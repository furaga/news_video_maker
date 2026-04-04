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

# ---- HTML テンプレート -------------------------------------------------------

_SUBTITLE_TEMPLATE = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=M+PLUS+1p:wght@900&display=swap" rel="stylesheet">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    width: {width}px; height: {height}px;
    background: #111111;
    font-family: 'M PLUS 1p', 'BIZ UDGothic', 'Noto Sans JP', 'Meiryo', 'Yu Gothic', sans-serif;
    overflow: hidden;
    display: flex; flex-direction: column;
  }}
  /* 上部タイトル帯 */
  .title-band {{
    flex-shrink: 0;
    background: #111111;
    padding: 40px 40px 30px;
    z-index: 20;
  }}
  .title-text {{
    font-size: 90px; font-weight: 900;
    color: #FFFFFF;
    line-height: 1.3;
    letter-spacing: -1px;
  }}
  .title-text .kw {{
    color: #FF2222;
  }}
  /* 中央画像エリア */
  .image-area {{
    flex: 1;
    position: relative;
    overflow: hidden;
  }}
  .bg {{
    position: absolute; inset: 0;
    background-image: url('{bg_data_url}');
    background-size: cover; background-position: center;
    transform: scale(1.0);
    transform-origin: center center;
  }}
  /* 下部字幕帯
     NewsPicks ザブトンスタイル: 白背景 + 黒文字、キーワードは黄色背景 */
  .subtitle-band {{
    flex-shrink: 0;
    background: #111111;
    padding: 30px 50px 120px;
    min-height: 400px;
    z-index: 20;
  }}
  .subtitle-area {{
    text-align: left;
  }}
  .subtitle-line {{
    display: inline;
    background: #ffffff;
    color: #111111;
    font-size: 64px; font-weight: 900;
    line-height: 1.85;
    padding: 6px 14px;
    -webkit-box-decoration-break: clone;
    box-decoration-break: clone;
    letter-spacing: -1px;
  }}
  .subtitle-line .kw {{
    background: #FFE000;
    color: #111111;
  }}
  .subtitle-line ruby {{
    ruby-position: over;
  }}
  .subtitle-line rt {{
    font-size: 24px;
    font-weight: 700;
    color: #666666;
    background: #ffffff;
    padding: 0 4px;
  }}
</style>
</head>
<body>
  <div class="title-band">
    <div class="title-text">{title_html}</div>
  </div>
  <div class="image-area">
    <div class="bg" id="bg"></div>
  </div>
  <div class="subtitle-band">
    <div class="subtitle-area">
      <span class="subtitle-line" id="subtitle">{subtitle_html}</span>
    </div>
  </div>
</body>
</html>
"""

_CTA_TEMPLATE = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=M+PLUS+1p:wght@900&display=swap" rel="stylesheet">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    width: {width}px; height: {height}px;
    background: #0d1117;
    font-family: 'M PLUS 1p', 'BIZ UDGothic', 'Noto Sans JP', 'Meiryo', 'Yu Gothic', sans-serif;
    overflow: hidden; position: relative;
  }}
  .bg {{
    position: absolute; inset: 0;
    background-image: url('{bg_data_url}');
    background-size: cover; background-position: center;
    transform: scale(1.0);
    transform-origin: center center;
  }}
  .cta-center {{
    position: absolute; inset: 0;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    z-index: 20;
    padding: 0 60px;
  }}
  .cta-emoji {{
    font-size: 180px; line-height: 1; margin-bottom: 60px;
    text-align: center;
  }}
  .cta-line {{
    display: inline;
    background: #ffffff;
    color: #111111;
    font-size: 68px; font-weight: 900;
    line-height: 2.0;
    padding: 6px 20px;
    -webkit-box-decoration-break: clone;
    box-decoration-break: clone;
    letter-spacing: -1px;
  }}
</style>
</head>
<body>
  <div class="bg" id="bg"></div>
  <div class="cta-center">
    <div class="cta-emoji">👍🔔</div>
    <div style="text-align: center;">
      <span class="cta-line">高評価とチャンネル登録<br>よろしくお願いします！</span>
    </div>
  </div>
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


def _chunk_to_html(chunk: str, annotations: dict[str, str] | None = None) -> str:
    """**keyword** マークアップを HTML span (.kw) に変換する。

    annotations が指定されている場合、キーワードに ruby 注釈を付ける。
    """
    result = ""
    last = 0
    for m in re.finditer(r'\*\*(.+?)\*\*', chunk):
        result += html_module.escape(chunk[last:m.start()])
        kw = m.group(1)
        kw_escaped = html_module.escape(kw)
        if annotations and kw in annotations:
            rt_text = html_module.escape(annotations[kw])
            result += f'<ruby class="kw"><span class="kw">{kw_escaped}</span><rt>{rt_text}</rt></ruby>'
        else:
            result += f'<span class="kw">{kw_escaped}</span>'
        last = m.end()
    result += html_module.escape(chunk[last:])
    return result


# 助詞（チャンク先頭に来ると不自然な語）
_PARTICLES = set("はがをにでともへのやか")
_PARTICLE_MULTI = {"から", "まで", "より", "など", "って", "では", "には", "とは", "ので", "のに", "けど"}
_MIN_CHUNK_CHARS = 10


def _postprocess_chunks(chunks: list[str]) -> list[str]:
    """助詞で始まるチャンク・短いチャンクを前のチャンクにマージする。"""
    if len(chunks) <= 1:
        return chunks

    result: list[str] = []
    for chunk in chunks:
        if not result:
            result.append(chunk)
            continue
        stripped = chunk.lstrip()
        starts_with_particle = stripped and (
            stripped[0] in _PARTICLES
            or any(stripped.startswith(p) for p in _PARTICLE_MULTI)
        )
        if starts_with_particle or (stripped and len(stripped) < _MIN_CHUNK_CHARS):
            result[-1] += chunk
        else:
            result.append(chunk)

    return result


def _split_chunks_ginza(text: str, max_chars: int = 26) -> list[str]:
    """ginza（spaCy日本語モデル）でトークン化し、トークン単位でチャンク分割する。

    token.idx を使って元テキストからスライスし、空白を正確に保持する。
    """
    import spacy
    nlp = spacy.load("ja_ginza")
    text = text.strip()
    doc = nlp(text)

    chunks: list[str] = []
    chunk_start = 0

    for token in doc:
        is_punct = token.text in "。！？、"
        token_end = token.idx + len(token.text)

        # このトークンを含めると max_chars を超える場合、手前で切る
        if token_end - chunk_start > max_chars and token.idx > chunk_start:
            chunks.append(text[chunk_start:token.idx])
            chunk_start = token.idx

        # 句読点で区切る（自然な区切り点）
        if is_punct:
            chunks.append(text[chunk_start:token_end])
            chunk_start = token_end

    # 残りのテキスト
    if chunk_start < len(text):
        chunks.append(text[chunk_start:])

    chunks = _postprocess_chunks(chunks)
    return [c for c in chunks if c.strip()] or [text]


def _split_chunks_fallback(text: str, max_chars: int = 26) -> list[str]:
    """フォールバック: 正規表現ベースの分割ロジック。"""
    raw = re.split(r'(?<=[。！？])', text.strip())
    raw = [s.strip() for s in raw if s.strip()]

    chunks = []
    for sentence in raw:
        if len(sentence) <= max_chars:
            chunks.append(sentence)
            continue
        parts = re.split(r'(?<=、)', sentence)
        current = ""
        for part in parts:
            if len(current) + len(part) <= max_chars:
                current += part
            else:
                if current:
                    chunks.append(current)
                sub_parts = re.split(r'(?<=[てで])(?=[^\s、。！？])', part)
                sub_current = ""
                for sp in sub_parts:
                    if len(sub_current) + len(sp) <= max_chars:
                        sub_current += sp
                    else:
                        if sub_current:
                            chunks.append(sub_current)
                        while len(sp) > max_chars:
                            chunks.append(sp[:max_chars])
                            sp = sp[max_chars:]
                        sub_current = sp
                if sub_current:
                    current = sub_current
                else:
                    current = ""
        if current:
            chunks.append(current)

    chunks = _postprocess_chunks(chunks)
    return chunks if chunks else [text]


def split_into_subtitle_chunks(text: str, max_chars: int = 26) -> list[str]:
    """narration_text を字幕チャンクのリストに分割する（形態素解析ベース）。

    ginza でトークン化し、トークン単位で積み上げてチャンク分割する。
    句読点（。！？、）は自然な区切り点として優先的に使用。
    """
    try:
        return _split_chunks_ginza(text, max_chars)
    except Exception:
        logger.warning("ginza が利用できません。フォールバックの分割を使用します。")
        return _split_chunks_fallback(text, max_chars)


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
    annotations: dict[str, str] | None = None,
) -> list[np.ndarray]:
    """Playwright でフレームをレンダリングする。

    Ken Burns 効果: セクションローカル時間で scale 1.0→1.20 ＋ ゆっくりパン。
    パン方向: section_start が偶数秒帯なら右パン (+1)、奇数秒帯なら左パン (-1)。
    """
    from playwright.async_api import async_playwright

    # セクション全体の長さ（Ken Burns 進行計算用）
    section_duration = max(sum(chunk_durations), 0.1)
    pan_dir = 1 if int(section_start) % 2 == 0 else -1

    frames: list[np.ndarray] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})
        await page.set_content(html, wait_until="networkidle")
        # networkidle は「ネットワーク通信なし」を保証するが、背景画像（data URL）の
        # デコード・描画完了は保証しない。初回フレームが白くなる問題を防ぐために待機する。
        await page.wait_for_timeout(500)

        # フレーム数を事前計算し、丸め誤差を最終チャンクで吸収
        total_needed = max(1, round(section_duration * FPS))
        frame_counts = [max(1, round(d * FPS)) for d in chunk_durations]
        frame_counts[-1] = max(1, frame_counts[-1] + total_needed - sum(frame_counts))

        elapsed = 0.0
        for chunk_idx, (chunk, chunk_dur) in enumerate(zip(subtitle_chunks, chunk_durations)):
            # 字幕テキストを更新（CTAテンプレートは subtitle 要素なし）
            if not is_cta:
                chunk_html = _chunk_to_html(chunk, annotations)
                await page.evaluate(
                    "([html]) => { document.getElementById('subtitle').innerHTML = html; }",
                    [chunk_html],
                )

            n_frames = frame_counts[chunk_idx]
            for frame_i in range(n_frames):
                t_in_chunk = frame_i / FPS
                local_elapsed = elapsed + t_in_chunk

                await page.evaluate(
                    """([localElapsed, sectionDuration, panDir]) => {
                        const bgEl = document.getElementById('bg');
                        if (bgEl) {
                            const progress = Math.min(localElapsed / sectionDuration, 1.0);
                            const bgScale = 1.0 + 0.20 * progress;
                            const panX = panDir * 40 * progress;
                            const panY = -15 * progress;
                            bgEl.style.transform =
                                'scale(' + bgScale + ') translate(' + panX + 'px, ' + panY + 'px)';
                        }
                    }""",
                    [local_elapsed, section_duration, pan_dir],
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
    annotations: dict[str, str] | None = None,
) -> list[np.ndarray]:
    """同期ラッパー"""
    return asyncio.run(_render_frames_async(
        html, subtitle_chunks, chunk_durations, section_start, total_duration, is_cta, annotations
    ))


# ---- 公開 API ---------------------------------------------------------------

def generate_subtitle_clip(
    title: str,
    subtitle_chunks: list[str],
    chunk_durations: list[float],
    bg_data_url: str,
    duration: float,
    section_start: float = 0.0,
    total_duration: float = 60.0,
    annotations: dict[str, str] | None = None,
) -> VideoClip:
    """字幕スタイルの VideoClip を返す。

    subtitle_chunks: 表示する字幕テキストのリスト（**keyword** マークアップ対応）
    chunk_durations: 各チャンクの表示時間（秒）
    annotations: キーワードの注釈辞書（ruby テキストとして表示）
    """
    html = _SUBTITLE_TEMPLATE.format(
        width=WIDTH,
        height=HEIGHT,
        bg_data_url=bg_data_url or "",
        title_html=_chunk_to_html(title),
        subtitle_html=_chunk_to_html(subtitle_chunks[0] if subtitle_chunks else "", annotations),
    )

    logger.info("字幕クリップレンダリング開始: %d チャンク, %.1fs", len(subtitle_chunks), duration)
    rendered = _render_frames(html, subtitle_chunks, chunk_durations, section_start, total_duration, annotations=annotations)

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
