"""ニュース記事データモデル"""
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class NewsArticle:
    title: str
    url: str
    source: str  # "hackernews" | "techcrunch" | "theverge" | "arstechnica"
    published_at: datetime
    summary_text: str
    full_text: str = ""
    image_url: str = ""
