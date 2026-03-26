"""ナレーション・BGM・SFX を CompositeAudioClip でミックスする。"""
import logging
import random
from pathlib import Path

from moviepy import AudioFileClip, CompositeAudioClip
from moviepy.audio.fx import AudioFadeIn, AudioFadeOut, AudioLoop, MultiplyVolume

from news_video_maker.config import BGM_VOLUME, SFX_TRANSITION_DIR, SFX_VOLUME

logger = logging.getLogger(__name__)


def mix_audio(
    narration_wavs: list[Path],
    section_starts: list[float],
    total_duration: float,
    bgm_path: Path | None = None,
    bgm_volume: float = BGM_VOLUME,
) -> CompositeAudioClip:
    """ナレーション・BGM・SFX を合成した AudioClip を返す。

    Args:
        narration_wavs: 各セクションのナレーション WAV パスリスト（順番通り）
        section_starts: 各セクションの動画内開始時刻リスト（narration_wavs と同じ長さ）
        total_duration: 最終動画の総尺（秒）
        bgm_path: BGM ファイルパス。None の場合は BGM なし
        bgm_volume: BGM 音量（0.0〜1.0）
    """
    tracks = []

    # ナレーション: 各 WAV を対応する開始時刻に配置
    for wav_path, start in zip(narration_wavs, section_starts):
        clip = AudioFileClip(str(wav_path)).with_start(start)
        tracks.append(clip)

    # BGM
    if bgm_path and bgm_path.exists():
        try:
            bgm = AudioFileClip(str(bgm_path))
            if bgm.duration < total_duration:
                bgm = bgm.with_effects([AudioLoop(duration=total_duration)])
            else:
                bgm = bgm.subclipped(0, total_duration)
            bgm = bgm.with_effects([
                MultiplyVolume(bgm_volume),
                AudioFadeIn(1.0),
                AudioFadeOut(2.0),
            ])
            tracks.append(bgm)
            logger.info("BGMをミックス: %s (volume=%.2f)", bgm_path.name, bgm_volume)
        except Exception as e:
            logger.warning("BGMミックス失敗（スキップ）: %s", e)
    else:
        if bgm_path:
            logger.warning("BGMファイルが見つかりません: %s", bgm_path)

    # SFX: section_starts[1:] のタイミングに遷移音を配置
    sfx_files = _get_sfx_files()
    if sfx_files and len(section_starts) > 1:
        sfx_path = random.choice(sfx_files)
        try:
            for start in section_starts[1:]:
                sfx = (
                    AudioFileClip(str(sfx_path))
                    .with_start(start)
                    .with_effects([MultiplyVolume(SFX_VOLUME)])
                )
                tracks.append(sfx)
            logger.info("SFX (%d箇所) をミックス: %s", len(section_starts) - 1, sfx_path.name)
        except Exception as e:
            logger.warning("SFXミックス失敗（スキップ）: %s", e)

    return CompositeAudioClip(tracks).with_duration(total_duration)


def _get_sfx_files() -> list[Path]:
    """assets/sfx/transition/ 内の音声ファイル一覧を返す。存在しない場合は空リスト。"""
    if not SFX_TRANSITION_DIR.exists():
        return []
    return [
        f for f in SFX_TRANSITION_DIR.iterdir()
        if f.suffix.lower() in {".wav", ".mp3", ".ogg"}
    ]
