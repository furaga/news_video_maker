"""VOICEVOX HTTP API クライアント"""
import logging
import subprocess
import time
from pathlib import Path

import httpx

from news_video_maker.config import AUDIO_DIR, VOICEVOX_SPEAKER_ID, VOICEVOX_URL

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_WAIT = 1.0

VOICEVOX_EXE = r"C:\Users\furag\AppData\Local\Programs\VOICEVOX\VOICEVOX.exe"
VOICEVOX_STARTUP_TIMEOUT = 60   # seconds
VOICEVOX_STARTUP_POLL = 2       # seconds


def _ensure_voicevox_running() -> None:
    """VOICEVOXが起動していなければ自動起動し、準備完了を待つ"""
    try:
        r = httpx.get(f"{VOICEVOX_URL}/version", timeout=2)
        if r.status_code == 200:
            return  # already running
    except Exception:
        pass

    logger.info("VOICEVOXが起動していません。自動起動します: %s", VOICEVOX_EXE)
    subprocess.Popen(
        [VOICEVOX_EXE],
        creationflags=subprocess.CREATE_NO_WINDOW,
    )

    deadline = time.monotonic() + VOICEVOX_STARTUP_TIMEOUT
    while time.monotonic() < deadline:
        time.sleep(VOICEVOX_STARTUP_POLL)
        try:
            r = httpx.get(f"{VOICEVOX_URL}/version", timeout=2)
            if r.status_code == 200:
                logger.info("VOICEVOX起動完了")
                return
        except Exception:
            pass

    raise RuntimeError(
        f"VOICEVOXが{VOICEVOX_STARTUP_TIMEOUT}秒以内に起動しませんでした。"
        "手動で起動してから再試行してください。"
    )


def synthesize(text: str, output_path: Path, speaker_id: int = VOICEVOX_SPEAKER_ID) -> Path:
    """テキストを音声合成してWAVファイルに保存する"""
    _ensure_voicevox_running()
    for attempt in range(MAX_RETRIES):
        try:
            # audio_query を生成
            r = httpx.post(
                f"{VOICEVOX_URL}/audio_query",
                params={"text": text, "speaker": speaker_id},
                timeout=30,
            )
            r.raise_for_status()
            query = r.json()
            query["speedScale"] = 1.2  # 読み上げ速度を20%上げる

            # 音声合成
            r2 = httpx.post(
                f"{VOICEVOX_URL}/synthesis",
                params={"speaker": speaker_id},
                json=query,
                timeout=60,
            )
            r2.raise_for_status()

            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(r2.content)
            logger.info("音声合成完了: %s", output_path)
            return output_path

        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                logger.warning("音声合成失敗（%d/%d回目）: %s", attempt + 1, MAX_RETRIES, e)
                time.sleep(RETRY_WAIT)
            else:
                raise RuntimeError(f"音声合成に失敗しました: {e}") from e

    raise RuntimeError("音声合成に失敗しました（リトライ上限）")
