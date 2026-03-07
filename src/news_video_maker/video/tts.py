"""VOICEVOX HTTP API クライアント"""
import logging
import time
from pathlib import Path

import httpx

from news_video_maker.config import AUDIO_DIR, VOICEVOX_SPEAKER_ID, VOICEVOX_URL

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_WAIT = 1.0


def synthesize(text: str, output_path: Path, speaker_id: int = VOICEVOX_SPEAKER_ID) -> Path:
    """テキストを音声合成してWAVファイルに保存する"""
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

        except httpx.ConnectError:
            raise RuntimeError(
                f"VOICEVOXに接続できません ({VOICEVOX_URL})。"
                "VOICEVOXが起動しているか確認してください。"
            )
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                logger.warning("音声合成失敗（%d/%d回目）: %s", attempt + 1, MAX_RETRIES, e)
                time.sleep(RETRY_WAIT)
            else:
                raise RuntimeError(f"音声合成に失敗しました: {e}") from e

    raise RuntimeError("音声合成に失敗しました（リトライ上限）")
