"""OpenTDB から雑学・豆知識クイズデータを取得"""
import hashlib
import html
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from news_video_maker.config import (
    PIPELINE_DIR,
    TRIVIA_CATEGORIES,
    TRIVIA_FETCH_PER_CATEGORY,
)
from news_video_maker.history import HistoryStore

logger = logging.getLogger(__name__)

OPENTDB_API_URL = "https://opentdb.com/api.php"


@dataclass
class TriviaItem:
    question: str
    correct_answer: str
    incorrect_answers: list[str]
    category: str
    difficulty: str
    image_url: str = ""
    url: str = ""  # "opentdb://{hash}" 形式（重複防止用キー）


def _make_url(question: str) -> str:
    """質問テキストから一意の URL キーを生成"""
    digest = hashlib.sha256(question.encode()).hexdigest()[:16]
    return f"opentdb://{digest}"


def _fetch_category(category_id: int, amount: int) -> list[TriviaItem]:
    """指定カテゴリから雑学クイズを取得"""
    params = {
        "amount": amount,
        "category": category_id,
        "type": "multiple",
    }
    try:
        response = httpx.get(OPENTDB_API_URL, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        logger.warning("OpenTDB カテゴリ %d 取得エラー: %s", category_id, e)
        return []

    if data.get("response_code") != 0:
        logger.warning("OpenTDB カテゴリ %d: response_code=%d", category_id, data.get("response_code"))
        return []

    items = []
    for result in data.get("results", []):
        question = html.unescape(result.get("question", ""))
        correct = html.unescape(result.get("correct_answer", ""))
        incorrect = [html.unescape(a) for a in result.get("incorrect_answers", [])]
        category = html.unescape(result.get("category", ""))
        difficulty = result.get("difficulty", "medium")

        if not question or not correct:
            continue

        items.append(TriviaItem(
            question=question,
            correct_answer=correct,
            incorrect_answers=incorrect,
            category=category,
            difficulty=difficulty,
            image_url="",
            url=_make_url(question),
        ))

    return items


def fetch_trivia() -> list[TriviaItem]:
    """全カテゴリから雑学クイズを取得して返す。全件処理済みの場合は空リストを返す"""
    seen_urls: set[str] = HistoryStore().seen_urls()
    all_items: list[TriviaItem] = []

    for i, category_id in enumerate(TRIVIA_CATEGORIES):
        if i > 0:
            time.sleep(5)  # OpenTDB レート制限対策（429 回避）
        items = _fetch_category(category_id, TRIVIA_FETCH_PER_CATEGORY)
        logger.info("カテゴリ %d: %d 件取得", category_id, len(items))
        all_items.extend(items)

    # 重複除外
    new_items = [item for item in all_items if item.url not in seen_urls]

    if not new_items and all_items:
        logger.info("新規雑学なし（全 %d 件が処理済み）", len(all_items))
        return []

    return new_items


def save_trivia(items: list[TriviaItem], path: Path) -> None:
    data = [
        {
            "question": item.question,
            "correct_answer": item.correct_answer,
            "incorrect_answers": item.incorrect_answers,
            "category": item.category,
            "difficulty": item.difficulty,
            "image_url": item.image_url,
            "url": item.url,
        }
        for item in items
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("%d 件の雑学データを %s に保存しました", len(items), path)


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logger.info("OpenTDB から雑学データを取得中...")
    items = fetch_trivia()
    output = PIPELINE_DIR / "01_trivia.json"
    if not items:
        save_trivia([], output)
        print("新規雑学なし: 全データが処理済みです")
        return
    save_trivia(items, output)
    print(f"取得完了: {len(items)} 件 → {output}")


if __name__ == "__main__":
    main()
