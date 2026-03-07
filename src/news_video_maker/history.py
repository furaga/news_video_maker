"""投稿済み記事の履歴管理"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from news_video_maker.config import HISTORY_PATH

logger = logging.getLogger(__name__)


class HistoryStore:
    def __init__(self, path: Path = HISTORY_PATH):
        self._path = path
        self._data: dict = self._load()

    def _load(self) -> dict:
        if not self._path.exists():
            return {"version": 1, "entries": []}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("history.json 読み込み失敗。空データで起動: %s", e)
            return {"version": 1, "entries": []}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def seen_urls(self) -> set[str]:
        """投稿済みURLのセットを返す"""
        return {e["url"] for e in self._data.get("entries", [])}

    def is_seen(self, url: str) -> bool:
        """URLが投稿済みかチェック"""
        return url in self.seen_urls()

    def record(self, url: str, title: str, source: str, youtube_url: str) -> None:
        """アップロード成功後に記録して保存"""
        entry = {
            "url": url,
            "title": title,
            "source": source,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "youtube_url": youtube_url,
        }
        self._data.setdefault("entries", []).append(entry)
        try:
            self._save()
            logger.info("履歴に記録: %s", url)
        except Exception as e:
            logger.warning("履歴保存失敗: %s", e)
