"""プロジェクト設定"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ディレクトリ
BASE_DIR = Path(__file__).parent.parent.parent
CACHE_DIR = BASE_DIR / ".cache"
PIPELINE_DIR = CACHE_DIR / "pipeline"
AUDIO_DIR = CACHE_DIR / "audio"
IMAGES_DIR = CACHE_DIR / "images"
OUTPUT_DIR = BASE_DIR / "output"

# RSSフィード
FEEDS = [
    "https://hnrss.org/newest?points=100",
    "https://techcrunch.com/feed/",
    "https://www.theverge.com/rss/index.xml",
    "https://feeds.arstechnica.com/arstechnica/index",
]
FETCH_HOURS = 24
MAX_ARTICLES = 30

# VOICEVOX
VOICEVOX_URL = os.getenv("VOICEVOX_URL", "http://localhost:50021")
VOICEVOX_SPEAKER_ID = 13  # 青山龍星

# YouTube
YOUTUBE_CLIENT_SECRET_PATH = Path(
    os.getenv("YOUTUBE_CLIENT_SECRET_PATH", "./client_secret.json")
)
YOUTUBE_TOKEN_PATH = BASE_DIR / "token.json"
YOUTUBE_PRIVACY = "unlisted"
YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# ディレクトリ自動作成
for _d in [PIPELINE_DIR, AUDIO_DIR, IMAGES_DIR, OUTPUT_DIR]:
    _d.mkdir(parents=True, exist_ok=True)
