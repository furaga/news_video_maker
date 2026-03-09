"""arXiv + HF Daily Papers から最新技術論文を取得"""
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

import feedparser
import httpx

from news_video_maker.config import (
    ARXIV_CATEGORIES,
    MAX_PAPERS,
    PAPER_FETCH_DAYS,
    PIPELINE_DIR,
)
from news_video_maker.history import HistoryStore

logger = logging.getLogger(__name__)

ARXIV_API_URL = "http://export.arxiv.org/api/query"
HF_DAILY_PAPERS_API = "https://huggingface.co/api/daily_papers"


@dataclass
class Paper:
    paper_id: str
    title: str
    authors: list[str]
    abstract: str
    arxiv_url: str
    pdf_url: str
    categories: list[str]
    submitted_at: datetime
    hf_featured: bool = False
    hf_upvotes: int = 0
    image_url: str = ""


def _parse_arxiv_feed(text: str, cutoff: datetime | None = None) -> list[Paper]:
    """arXiv API の Atom フィードをパースして Paper リストを返す"""
    feed = feedparser.parse(text)
    papers: list[Paper] = []

    for entry in feed.entries:
        published = getattr(entry, "published_parsed", None)
        if published is None:
            continue
        try:
            submitted_at = datetime(*published[:6], tzinfo=timezone.utc)
        except Exception:
            continue

        if cutoff and submitted_at < cutoff:
            continue

        arxiv_id_raw = entry.get("id", "")
        paper_id = arxiv_id_raw.split("/abs/")[-1].split("v")[0]
        if not paper_id:
            continue

        authors = [a.get("name", "") for a in entry.get("authors", [])][:5]
        tags = entry.get("tags", [])
        categories = [t.get("term", "") for t in tags if t.get("term", "")]
        abstract = (entry.get("summary", "") or "").replace("\n", " ").strip()[:1000]

        papers.append(Paper(
            paper_id=paper_id,
            title=entry.get("title", "").replace("\n", " ").strip(),
            authors=authors,
            abstract=abstract,
            arxiv_url=f"https://arxiv.org/abs/{paper_id}",
            pdf_url=f"https://arxiv.org/pdf/{paper_id}",
            categories=categories,
            submitted_at=submitted_at,
        ))

    return papers


def _fetch_latest_arxiv(cutoff: datetime) -> list[Paper]:
    """arXiv から最新論文をカテゴリ検索で取得（直近3日程度）"""
    category_query = " OR ".join(f"cat:{c}" for c in ARXIV_CATEGORIES)
    params = {
        "search_query": category_query,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": MAX_PAPERS * 2,
    }
    query_string = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
    url = f"{ARXIV_API_URL}?{query_string}"
    try:
        response = httpx.get(url, timeout=30, follow_redirects=True)
        response.raise_for_status()
        return _parse_arxiv_feed(response.text, cutoff)
    except Exception as e:
        logger.error("arXiv カテゴリ検索エラー: %s", e)
        return []


def _fetch_arxiv_by_ids(paper_ids: list[str]) -> list[Paper]:
    """指定された arXiv ID の論文を個別取得"""
    if not paper_ids:
        return []
    id_list = ",".join(paper_ids)
    url = f"{ARXIV_API_URL}?id_list={id_list}&max_results={len(paper_ids)}"
    try:
        response = httpx.get(url, timeout=30, follow_redirects=True)
        response.raise_for_status()
        return _parse_arxiv_feed(response.text, cutoff=None)
    except Exception as e:
        logger.error("arXiv ID検索エラー: %s", e)
        return []


def _fetch_hf_papers(num_days: int) -> dict[str, int]:
    """HF Daily Papers API から paper_id → upvotes のマップを取得"""
    today = datetime.now(timezone.utc)
    upvotes: dict[str, int] = {}
    for i in range(num_days):
        date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        try:
            response = httpx.get(
                HF_DAILY_PAPERS_API,
                params={"date": date},
                timeout=10,
                follow_redirects=True,
            )
            response.raise_for_status()
            for item in response.json():
                paper_info = item.get("paper", {})
                paper_id = paper_info.get("id", "")
                votes = paper_info.get("upvotes", 0)
                if paper_id:
                    upvotes[paper_id] = max(upvotes.get(paper_id, 0), votes)
        except Exception as e:
            logger.warning("HF Daily Papers API エラー (date=%s): %s", date, e)
    return upvotes


def fetch_papers() -> list[Paper]:
    """arXiv + HF から論文を取得して返す。全件処理済みの場合は空リストを返す"""
    cutoff = datetime.now(timezone.utc) - timedelta(days=PAPER_FETCH_DAYS)
    seen_urls: set[str] = HistoryStore().seen_urls()

    # 1. HF Daily Papers の注目論文IDと upvotes を取得
    hf_upvotes = _fetch_hf_papers(PAPER_FETCH_DAYS)
    hf_ids = set(hf_upvotes.keys())
    logger.info("HF Daily Papers: %d 件の論文ID取得", len(hf_ids))

    # 2. arXiv から最新論文を取得（カテゴリ検索）
    latest_papers = _fetch_latest_arxiv(cutoff)
    logger.info("arXiv 最新論文: %d 件", len(latest_papers))

    # 3. HF 掲載論文のうち arXiv 検索結果にないものを個別フェッチ
    latest_ids = {p.paper_id for p in latest_papers}
    missing_hf_ids = [pid for pid in hf_ids if pid not in latest_ids]
    if missing_hf_ids:
        logger.info("HF 掲載論文を個別フェッチ: %d 件", len(missing_hf_ids))
        hf_only_papers = _fetch_arxiv_by_ids(missing_hf_ids)
    else:
        hf_only_papers = []

    # 4. マージ（重複除去）
    all_papers_map: dict[str, Paper] = {}
    for p in latest_papers + hf_only_papers:
        if p.paper_id not in all_papers_map:
            all_papers_map[p.paper_id] = p

    # 5. HF フラグ・upvotes を付与
    for paper in all_papers_map.values():
        votes = hf_upvotes.get(paper.paper_id, 0)
        paper.hf_featured = votes > 0
        paper.hf_upvotes = votes

    all_papers = list(all_papers_map.values())

    # 6. 重複除外（投稿済みURL）
    new_papers = [p for p in all_papers if p.arxiv_url not in seen_urls]

    if not new_papers and all_papers:
        logger.info("新規論文なし（全 %d 件が処理済み）", len(all_papers))
        return []

    # 7. HF 掲載 → upvotes 降順 → 投稿日降順 でソート
    new_papers.sort(key=lambda p: (not p.hf_featured, -p.hf_upvotes, -p.submitted_at.timestamp()))
    return new_papers[:MAX_PAPERS]


def save_papers(papers: list[Paper], path: Path) -> None:
    data = [
        {
            "paper_id": p.paper_id,
            "title": p.title,
            "authors": p.authors,
            "abstract": p.abstract,
            "arxiv_url": p.arxiv_url,
            "pdf_url": p.pdf_url,
            "categories": p.categories,
            "submitted_at": p.submitted_at.isoformat(),
            "hf_featured": p.hf_featured,
            "hf_upvotes": p.hf_upvotes,
            "image_url": p.image_url,
        }
        for p in papers
    ]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("%d 件の論文を %s に保存しました", len(papers), path)


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logger.info("arXiv + HF Daily Papers から論文を取得中...")
    papers = fetch_papers()
    output = PIPELINE_DIR / "01_papers.json"
    if not papers:
        save_papers([], output)
        print("新規論文なし: 全論文が処理済みです")
        return
    save_papers(papers, output)
    hf_count = sum(1 for p in papers if p.hf_featured)
    print(f"取得完了: {len(papers)} 件（うち HF 掲載 {hf_count} 件）→ {output}")


if __name__ == "__main__":
    main()
