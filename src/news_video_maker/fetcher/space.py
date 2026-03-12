"""NASA APOD API + NASA RSS から宇宙・天文コンテンツを取得"""
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
import httpx

from news_video_maker.config import (
    NASA_API_KEY,
    PIPELINE_DIR,
    SPACE_FETCH_DAYS,
)
from news_video_maker.history import HistoryStore

logger = logging.getLogger(__name__)

NASA_APOD_URL = "https://api.nasa.gov/planetary/apod"
NASA_RSS_URL = "https://www.nasa.gov/rss/dyn/breaking_news.rss"


@dataclass
class SpaceItem:
    title: str
    url: str
    source: str  # "nasa_apod" | "nasa_rss"
    published_at: datetime
    description: str
    image_url: str
    media_type: str = "image"


def _fetch_apod(count: int = 10) -> list[SpaceItem]:
    """NASA APOD API から天文写真データを取得"""
    params = {"api_key": NASA_API_KEY, "count": count}
    try:
        response = httpx.get(NASA_APOD_URL, params=params, timeout=20)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        logger.warning("NASA APOD API エラー: %s", e)
        return []

    items = []
    for entry in data:
        media_type = entry.get("media_type", "")
        if media_type != "image":
            continue  # video (YouTube embed) は image_url がないためスキップ

        title = entry.get("title", "")
        image_url = entry.get("url", "")
        description = entry.get("explanation", "")[:1000]
        date_str = entry.get("date", "")
        apod_url = f"https://apod.nasa.gov/apod/ap{date_str.replace('-', '')[2:]}.html"

        try:
            published_at = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            published_at = datetime.now(timezone.utc)

        if not title or not image_url:
            continue

        items.append(SpaceItem(
            title=title,
            url=apod_url,
            source="nasa_apod",
            published_at=published_at,
            description=description,
            image_url=image_url,
            media_type="image",
        ))

    logger.info("NASA APOD: %d 件取得", len(items))
    return items


def _fetch_nasa_rss(days: int) -> list[SpaceItem]:
    """NASA ニュース RSS から最新記事を取得"""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    try:
        feed = feedparser.parse(NASA_RSS_URL)
    except Exception as e:
        logger.warning("NASA RSS 取得エラー: %s", e)
        return []

    items = []
    for entry in feed.entries:
        published = getattr(entry, "published_parsed", None)
        if published is None:
            continue
        try:
            published_at = datetime(*published[:6], tzinfo=timezone.utc)
        except Exception:
            continue

        if published_at < cutoff:
            continue

        title = getattr(entry, "title", "")
        url = getattr(entry, "link", "")
        description = getattr(entry, "summary", "")[:1000]

        # enclosure から画像 URL を取得
        image_url = ""
        enclosures = getattr(entry, "enclosures", [])
        for enc in enclosures:
            if enc.get("type", "").startswith("image/"):
                image_url = enc.get("href", "")
                break

        if not title or not url:
            continue

        items.append(SpaceItem(
            title=title,
            url=url,
            source="nasa_rss",
            published_at=published_at,
            description=description,
            image_url=image_url,
            media_type="image",
        ))

    logger.info("NASA RSS: %d 件取得", len(items))
    return items


def fetch_space() -> list[SpaceItem]:
    """APOD + NASA RSS から宇宙コンテンツを取得して返す"""
    seen_urls: set[str] = HistoryStore().seen_urls()

    apod_items = _fetch_apod(count=10)
    rss_items = _fetch_nasa_rss(days=SPACE_FETCH_DAYS)

    # マージ（重複除去）
    all_items_map: dict[str, SpaceItem] = {}
    for item in apod_items + rss_items:
        if item.url not in all_items_map:
            all_items_map[item.url] = item

    all_items = list(all_items_map.values())

    # 処理済みを除外
    new_items = [item for item in all_items if item.url not in seen_urls]

    if not new_items and all_items:
        logger.info("新規宇宙コンテンツなし（全 %d 件が処理済み）", len(all_items))
        return []

    # APOD 優先、次に RSS（画像あり優先）
    new_items.sort(key=lambda x: (x.source != "nasa_apod", not x.image_url, -x.published_at.timestamp()))
    return new_items


def save_space(items: list[SpaceItem], path: Path) -> None:
    data = [
        {
            "title": item.title,
            "url": item.url,
            "source": item.source,
            "published_at": item.published_at.isoformat(),
            "description": item.description,
            "image_url": item.image_url,
            "media_type": item.media_type,
        }
        for item in items
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("%d 件の宇宙コンテンツを %s に保存しました", len(items), path)


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logger.info("NASA から宇宙コンテンツを取得中...")
    items = fetch_space()
    output = PIPELINE_DIR / "01_space.json"
    if not items:
        save_space([], output)
        print("新規宇宙コンテンツなし: 全データが処理済みです")
        return
    save_space(items, output)
    apod_count = sum(1 for item in items if item.source == "nasa_apod")
    rss_count = sum(1 for item in items if item.source == "nasa_rss")
    print(f"取得完了: {len(items)} 件（APOD: {apod_count}件, RSS: {rss_count}件）→ {output}")


if __name__ == "__main__":
    main()
