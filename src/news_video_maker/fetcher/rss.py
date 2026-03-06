"""RSSフィード取得・記事変換"""
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser
import httpx

from news_video_maker.config import (
    FETCH_HOURS,
    FEEDS,
    MAX_ARTICLES,
    PIPELINE_DIR,
)
from news_video_maker.fetcher.models import NewsArticle

logger = logging.getLogger(__name__)

SOURCE_MAP = {
    "hnrss.org": "hackernews",
    "techcrunch.com": "techcrunch",
    "theverge.com": "theverge",
    "arstechnica.com": "arstechnica",
}


def _detect_source(feed_url: str) -> str:
    for domain, name in SOURCE_MAP.items():
        if domain in feed_url:
            return name
    return "unknown"


def _parse_time(entry) -> datetime | None:
    """エントリの日時をパース"""
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return None


def _fetch_full_text(url: str) -> str:
    """本文を httpx で取得（失敗時は空文字）"""
    try:
        r = httpx.get(
            url,
            headers={"User-Agent": "news-video-maker/0.1"},
            timeout=10,
            follow_redirects=True,
        )
        r.raise_for_status()
        return r.text[:3000]
    except Exception as e:
        logger.warning("本文取得失敗 %s: %s", url, e)
        return ""


def fetch_articles() -> list[NewsArticle]:
    """全フィードから記事を取得してリストで返す"""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=FETCH_HOURS)
    seen_urls: set[str] = set()
    articles: list[NewsArticle] = []

    for feed_url in FEEDS:
        source = _detect_source(feed_url)
        try:
            feed = feedparser.parse(feed_url)
            if feed.bozo and not feed.entries:
                logger.warning("フィード取得エラー %s: %s", feed_url, feed.bozo_exception)
                continue

            for entry in feed.entries:
                pub = _parse_time(entry)
                if pub is None:
                    continue
                if pub < cutoff:
                    continue

                url = entry.get("link", "")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)

                summary = entry.get("summary", "") or entry.get("description", "")
                article = NewsArticle(
                    title=entry.get("title", ""),
                    url=url,
                    source=source,
                    published_at=pub,
                    summary_text=summary,
                )

                if len(summary) < 200:
                    article.full_text = _fetch_full_text(url)

                articles.append(article)

        except Exception as e:
            logger.warning("フィード処理エラー %s: %s", feed_url, e)
            continue

    if not articles:
        raise RuntimeError("全フィードから記事を取得できませんでした")

    articles.sort(key=lambda a: a.published_at, reverse=True)
    return articles[:MAX_ARTICLES]


def save_articles(articles: list[NewsArticle], path: Path) -> None:
    data = [
        {
            "title": a.title,
            "url": a.url,
            "source": a.source,
            "published_at": a.published_at.isoformat(),
            "summary_text": a.summary_text,
            "full_text": a.full_text,
        }
        for a in articles
    ]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("%d 件の記事を %s に保存しました", len(articles), path)


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logger.info("RSSフィードから記事を取得中...")
    articles = fetch_articles()
    output = PIPELINE_DIR / "01_articles.json"
    save_articles(articles, output)
    print(f"取得完了: {len(articles)} 件 → {output}")


if __name__ == "__main__":
    main()
