"""moviepy 動画合成"""
import base64
import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from moviepy import AudioFileClip, concatenate_videoclips

from news_video_maker.config import AUDIO_DIR, IMAGES_DIR, OUTPUT_DIR, PIPELINE_DIR
from news_video_maker.video.background import generate_background_images
from news_video_maker.video.tts import synthesize
from news_video_maker.video.visuals import (
    generate_cta_clip,
    generate_subtitle_clip,
    split_into_subtitle_chunks,
)


def _split_display_text(display_text: str, max_chars: int = 26) -> list[str]:
    """**keyword** マークアップを保持しながら字幕チャンク分割する。

    マークアップなし版でチャンク位置を決め、対応するマークアップ付きテキストを抽出する。
    """
    clean = re.sub(r'\*\*(.+?)\*\*', r'\1', display_text)
    clean_chunks = split_into_subtitle_chunks(clean, max_chars)

    result = []
    orig_pos = 0

    for chunk in clean_chunks:
        markup_chunk = ""
        consumed = 0
        i = orig_pos

        while consumed < len(chunk) and i < len(display_text):
            m = re.match(r'\*\*(.+?)\*\*', display_text[i:])
            if m:
                kw = m.group(1)
                if consumed + len(kw) <= len(chunk):
                    markup_chunk += m.group(0)
                    consumed += len(kw)
                    i += len(m.group(0))
                else:
                    # キーワードがチャンク境界をまたぐ（まれ）→ プレーンテキストとして分割
                    needed = len(chunk) - consumed
                    markup_chunk += kw[:needed]
                    consumed += needed
            else:
                markup_chunk += display_text[i]
                consumed += 1
                i += 1

        result.append(markup_chunk)
        orig_pos = i

    # 残りがあれば追加
    if orig_pos < len(display_text) and display_text[orig_pos:].strip():
        result.append(display_text[orig_pos:].strip())

    return result if result else [display_text]


def _calc_chunk_durations(
    chunks: list[str], total_duration: float
) -> list[float]:
    """文字数比で各チャンクの表示時間を配分する（マークアップ除外）。

    同一文内のサブチャンク按分に使用する。
    文をまたいだタイミングは _get_sentence_durations で VOICEVOX 実測値を使うこと。
    """
    clean_lens = [len(re.sub(r'\*\*(.+?)\*\*', r'\1', c)) for c in chunks]
    total_chars = sum(clean_lens)
    if total_chars == 0:
        return [total_duration / len(chunks)] * len(chunks)
    durs = [total_duration * cl / total_chars for cl in clean_lens]
    # 浮動小数点の丸め誤差を最終チャンクで吸収
    durs[-1] += total_duration - sum(durs)
    return durs


def _split_at_sentence_boundaries(text: str) -> list[str]:
    """。！？ で分割し、区切り文字を末尾に残したチャンクを返す。"""
    parts = re.split(r'(?<=[。！？])', text)
    return [p for p in parts if p.strip()]


def _get_sentence_durations(
    narration_sentences: list[str],
    total_duration: float,
    cache_dir: Path,
) -> list[float]:
    """各文を VOICEVOX で個別合成して音声長を測定し、total_duration に正規化して返す。

    個別合成 WAV は cache_dir/sentences/ にキャッシュする。
    """
    if len(narration_sentences) <= 1:
        return [total_duration]

    sent_durations = []
    for i, sentence in enumerate(narration_sentences):
        key = hashlib.md5(sentence.encode()).hexdigest()[:8]
        wav_path = cache_dir / "sentences" / f"{key}_{i}.wav"
        wav_path.parent.mkdir(parents=True, exist_ok=True)
        if not wav_path.exists():
            synthesize(sentence, wav_path)
        audio = AudioFileClip(str(wav_path))
        sent_durations.append(audio.duration)
        audio.close()

    total_sent = sum(sent_durations)
    if total_sent == 0:
        return [total_duration / len(narration_sentences)] * len(narration_sentences)

    return [d / total_sent * total_duration for d in sent_durations]

logger = logging.getLogger(__name__)

# CTAナレーション
CTA_NARRATION = "高評価とチャンネル登録、よろしくおねがいします！"


@dataclass
class ScriptSection:
    type: str  # hook / main_1 / main_2 / main_3 / main_4 / main / outro
    narration_text: str
    subtitle_text: str
    estimated_duration_sec: float
    bg_prompt: str = field(default="")
    display_text: str = field(default="")  # 字幕表示用（**keyword** マークアップ、原語表記）
    annotations: dict[str, str] = field(default_factory=dict)


@dataclass
class VideoScript:
    title: str
    source_url: str
    total_duration_sec: float
    sections: list[ScriptSection]
    image_url: str = ""


def load_script(path: Path) -> VideoScript:
    data = json.loads(path.read_text(encoding="utf-8"))
    sections = [
        ScriptSection(
            type=s["type"],
            narration_text=s["narration_text"],
            subtitle_text=s["subtitle_text"],
            estimated_duration_sec=s["estimated_duration_sec"],
            bg_prompt=s.get("bg_prompt", ""),
            display_text=s.get("display_text", ""),
            annotations=s.get("annotations", {}),
        )
        for s in data["sections"]
    ]
    return VideoScript(
        title=data["title"],
        source_url=data["source_url"],
        total_duration_sec=data["total_duration_sec"],
        sections=sections,
        image_url=data.get("image_url", ""),
    )


def _path_to_data_url(path: Path) -> str:
    """画像ファイルを base64 data URL に変換する"""
    ext = path.suffix.lower()
    mime = "image/png" if ext == ".png" else "image/jpeg"
    b64 = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime};base64,{b64}"


def compose_video(script: VideoScript, output_path: Path) -> Path:
    """台本から動画を生成してMP4に保存する"""
    source_name = script.source_url.split("/")[2] if script.source_url else "unknown"

    # 02_selected.json から英語タイトルと key_points を取得
    article_title_en = script.title
    key_points: list[str] = []
    selected_path = PIPELINE_DIR / "02_selected.json"
    if selected_path.exists():
        selected = json.loads(selected_path.read_text(encoding="utf-8"))
        article_title_en = selected.get("title", selected.get("title_en", script.title))
        key_points = selected.get("ja_key_points", [])

    # 全セクションの音声を先に合成して total_duration を確定
    # (スクリプトのセクション + CTAセクション)
    all_sections = list(script.sections)
    cta_wav_path = AUDIO_DIR / f"{len(all_sections):02d}_cta.wav"
    synthesize(CTA_NARRATION, cta_wav_path)
    cta_audio = AudioFileClip(str(cta_wav_path))
    cta_duration = cta_audio.duration
    cta_audio.close()

    wav_paths = []
    durations = []
    for i, section in enumerate(all_sections):
        name = f"{i:02d}_{section.type}"
        wav_path = AUDIO_DIR / f"{name}.wav"
        synthesize(section.narration_text, wav_path)
        audio = AudioFileClip(str(wav_path))
        wav_paths.append(wav_path)
        durations.append(audio.duration)
        audio.close()

    total_duration = sum(durations) + cta_duration

    # 背景画像を複数生成（セクション数に基づいて枚数決定）
    # hookセクションは記事スクリーンショットを使うため、AI生成は残りセクション分
    num_ai_images = max(1, len(all_sections))  # セクションごとに1枚

    # hookセクション用: 事前キャプチャ済みスクリーンショット（ステージ3.5で検証済み）
    hook_bg_data_url = ""
    pre_captured = IMAGES_DIR / "article_screenshot_full.png"
    if pre_captured.exists():
        logger.info("検証済みスクリーンショットを使用: %s", pre_captured)
        hook_bg_data_url = _path_to_data_url(pre_captured)
    else:
        logger.info("スクリーンショットなし。SD生成画像をhookセクションに使用します")

    # セクションごとの bg_prompt を収集（存在する場合）
    section_bg_prompts = [s.bg_prompt for s in all_sections]
    custom_prompts = section_bg_prompts if any(section_bg_prompts) else None

    # AI生成背景画像（全セクション共通のフォールバック兼、hookセクション以外用）
    bg_list: list[str] = []
    ai_bg_results = generate_background_images(
        article_title_en,
        key_points,
        num_ai_images,
        IMAGES_DIR,
        custom_prompts=custom_prompts,
    )
    for bg_path, _ in ai_bg_results:
        bg_list.append(_path_to_data_url(bg_path))

    # AI生成に失敗した場合、hookスクリーンショットを全セクションで使い回す
    if not bg_list:
        fallback = hook_bg_data_url or ""
        bg_list = [fallback] * num_ai_images

    # hookセクションのbg: スクリーンショット優先、なければAI生成の最初の1枚
    if not hook_bg_data_url and bg_list:
        hook_bg_data_url = bg_list[0]

    # クリップ生成
    clips = []
    section_start = 0.0

    for i, section in enumerate(all_sections):
        wav_path = wav_paths[i]
        duration = durations[i]

        # セクションに対応する背景画像を選択
        if section.type == "hook" and hook_bg_data_url:
            bg_data_url = hook_bg_data_url
        else:
            bg_idx = i % len(bg_list)
            bg_data_url = bg_list[bg_idx]

        # 字幕チャンク生成: display_text があればマークアップ保持で分割、なければ narration_text を使用
        if section.display_text:
            display_sentences = _split_at_sentence_boundaries(section.display_text)
            narration_sentences = _split_at_sentence_boundaries(section.narration_text)
            if len(display_sentences) != len(narration_sentences):
                logger.warning(
                    "display_textとnarration_textの文数が一致しません (%d vs %d): %s",
                    len(display_sentences), len(narration_sentences), section.type,
                )
                display_sentences = [section.display_text]
                sentence_durs = [duration]
            else:
                sentence_durs = _get_sentence_durations(narration_sentences, duration, AUDIO_DIR)
            chunks = []
            chunk_durs = []
            for display_sent, sent_dur in zip(display_sentences, sentence_durs):
                sub_chunks = _split_display_text(display_sent)
                sub_durs = _calc_chunk_durations(sub_chunks, sent_dur)
                chunks.extend(sub_chunks)
                chunk_durs.extend(sub_durs)
        else:
            chunks = split_into_subtitle_chunks(section.narration_text)
            chunk_durs = _calc_chunk_durations(chunks, duration)

        audio = AudioFileClip(str(wav_path))
        video_clip = generate_subtitle_clip(
            title=script.title,
            subtitle_chunks=chunks,
            chunk_durations=chunk_durs,
            bg_data_url=bg_data_url,
            duration=duration,
            section_start=section_start,
            total_duration=total_duration,
            annotations=section.annotations or None,
        )
        video_clip = video_clip.with_audio(audio)
        clips.append(video_clip)
        section_start += duration

    # CTAセクション
    cta_bg = bg_list[-1] if bg_list else hook_bg_data_url or ""
    cta_audio = AudioFileClip(str(cta_wav_path))
    cta_video = generate_cta_clip(
        bg_data_url=cta_bg,
        duration=cta_duration,
        section_start=section_start,
        total_duration=total_duration,
    )
    cta_video = cta_video.with_audio(cta_audio)
    clips.append(cta_video)

    # 全セクションを結合
    final = concatenate_videoclips(clips)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    final.write_videofile(
        str(output_path),
        codec="libx264",
        audio_codec="aac",
        fps=30,
        logger=None,
    )
    logger.info("動画生成完了: %s", output_path)
    return output_path


def save_metadata(script: VideoScript, output_path: Path) -> Path:
    """動画と同名の .json メタデータファイルを output/ に保存する"""
    # YouTube用タイトルから **keyword** マークアップを除去
    clean_title = re.sub(r'\*\*(.+?)\*\*', r'\1', script.title)
    meta_path = output_path.with_suffix(".json")
    meta = {
        "title": clean_title,
        "source_url": script.source_url,
        "image_url": script.image_url,
        "video_path": str(output_path.resolve()),
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("メタデータ保存完了: %s", meta_path)

    # YouTube用マークダウンファイルも出力
    md_path = output_path.with_suffix(".md")
    md_content = (
        f"# タイトル\n"
        f"{clean_title}\n"
        f"\n"
        f"# 説明文\n"
        f"この動画はAIを活用して海外テックニュースの情報収集・翻訳・編集を一部自動化して制作したものです。\n"
        f"\n"
        f"元記事: {script.source_url}\n"
        f"#テックニュース #AI #セキュリティ\n"
    )
    md_path.write_text(md_content, encoding="utf-8")
    logger.info("マークダウンメタデータ保存完了: %s", md_path)

    return meta_path


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    script_path = PIPELINE_DIR / "03_script.json"
    if not script_path.exists():
        raise FileNotFoundError(f"台本ファイルが見つかりません: {script_path}")

    script = load_script(script_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = OUTPUT_DIR / f"{timestamp}.mp4"

    compose_video(script, output_path)
    meta_path = save_metadata(script, output_path)

    # パスファイルに保存
    path_file = PIPELINE_DIR / "04_video_path.txt"
    path_file.write_text(str(output_path.resolve()), encoding="utf-8")
    print(f"動画生成完了: {output_path}")
    print(f"メタデータ保存: {meta_path}")


if __name__ == "__main__":
    main()
