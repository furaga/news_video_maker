"""moviepy 動画合成"""
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from moviepy import AudioFileClip, concatenate_videoclips

from news_video_maker.config import AUDIO_DIR, OUTPUT_DIR, PIPELINE_DIR
from news_video_maker.video.tts import synthesize
from news_video_maker.video.visuals import generate_stack_clip, image_to_data_url

logger = logging.getLogger(__name__)


@dataclass
class ScriptSection:
    type: str  # hook / main_1 / main_2 / main_3 / main_4 / main / outro
    narration_text: str
    subtitle_text: str
    estimated_duration_sec: float


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


def compose_video(script: VideoScript, output_path: Path) -> Path:
    """台本から動画を生成してMP4に保存する"""
    source_name = script.source_url.split("/")[2] if script.source_url else "unknown"

    # 背景画像を一度だけダウンロード
    bg_data_url = image_to_data_url(script.image_url) if script.image_url else ""

    # 全セクションのカードデータを事前収集
    all_cards = [
        {"subtitle": s.subtitle_text, "type": s.type}
        for s in script.sections
    ]

    clips = []
    for i, section in enumerate(script.sections):
        name = f"{i:02d}_{section.type}"

        # 音声合成
        wav_path = AUDIO_DIR / f"{name}.wav"
        synthesize(section.narration_text, wav_path)

        # スタッククリップ生成
        audio = AudioFileClip(str(wav_path))
        duration = audio.duration
        prev_index = i - 1 if i > 0 else 0

        video_clip = generate_stack_clip(
            all_cards=all_cards,
            active_index=i,
            prev_index=prev_index,
            source=source_name,
            source_url=script.source_url,
            duration=duration,
            bg_data_url=bg_data_url or "",
        )
        video_clip = video_clip.with_audio(audio)
        clips.append(video_clip)

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
    meta_path = output_path.with_suffix(".json")
    meta = {
        "title": script.title,
        "source_url": script.source_url,
        "image_url": script.image_url,
        "video_path": str(output_path.resolve()),
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("メタデータ保存完了: %s", meta_path)
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
