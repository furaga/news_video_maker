"""moviepy 動画合成"""
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from moviepy import AudioFileClip, ImageClip, concatenate_videoclips

from news_video_maker.config import AUDIO_DIR, IMAGES_DIR, OUTPUT_DIR, PIPELINE_DIR
from news_video_maker.video.tts import synthesize
from news_video_maker.video.visuals import generate_text_card

logger = logging.getLogger(__name__)


@dataclass
class ScriptSection:
    type: Literal["hook", "main", "outro"]
    narration_text: str
    subtitle_text: str
    estimated_duration_sec: float


@dataclass
class VideoScript:
    title: str
    source_url: str
    total_duration_sec: float
    sections: list[ScriptSection]


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
    )


def compose_video(script: VideoScript, output_path: Path) -> Path:
    """台本から動画を生成してMP4に保存する"""
    clips = []

    for i, section in enumerate(script.sections):
        name = f"{i:02d}_{section.type}"

        # 音声合成
        wav_path = AUDIO_DIR / f"{name}.wav"
        synthesize(section.narration_text, wav_path)

        # 画像生成
        png_path = IMAGES_DIR / f"{name}.png"
        source_name = script.source_url.split("/")[2] if script.source_url else "unknown"
        generate_text_card(section.subtitle_text, source_name, png_path)

        # クリップ合成
        audio = AudioFileClip(str(wav_path))
        duration = audio.duration
        image_clip = ImageClip(str(png_path), duration=duration)
        video_clip = image_clip.with_audio(audio)
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


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    script_path = PIPELINE_DIR / "03_script.json"
    if not script_path.exists():
        raise FileNotFoundError(f"台本ファイルが見つかりません: {script_path}")

    script = load_script(script_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = OUTPUT_DIR / f"{timestamp}.mp4"

    compose_video(script, output_path)

    # パスファイルに保存
    path_file = PIPELINE_DIR / "04_video_path.txt"
    path_file.write_text(str(output_path.resolve()), encoding="utf-8")
    print(f"動画生成完了: {output_path}")


if __name__ == "__main__":
    main()
