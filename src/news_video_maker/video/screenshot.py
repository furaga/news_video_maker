"""記事スクリーンショットの事前キャプチャ

compose_video() の前に実行し、Claude Code による画像検証を挟むためのスクリプト。
`python -m news_video_maker.video.screenshot` で実行可能。
"""
import json
import logging
import sys

from news_video_maker.config import IMAGES_DIR, PIPELINE_DIR

logger = logging.getLogger(__name__)

OUTPUT_FILENAME = "article_screenshot_full.png"


def capture_screenshot() -> bool:
    """03_script.json の情報をもとにスクリーンショットを撮影し保存する。

    Returns:
        True: スクリーンショット保存成功
        False: 失敗（image_url も source_url も使えなかった）
    """
    from news_video_maker.video.visuals import (
        image_to_data_url,
        screenshot_article_url,
    )
    import base64
    from PIL import Image
    import io

    script_path = PIPELINE_DIR / "03_script.json"
    if not script_path.exists():
        logger.error("03_script.json が見つかりません: %s", script_path)
        return False

    data = json.loads(script_path.read_text(encoding="utf-8"))
    image_url = data.get("image_url", "")
    source_url = data.get("source_url", "")

    output_path = IMAGES_DIR / OUTPUT_FILENAME
    data_url = ""

    # 1. RSS 画像を試行
    if image_url:
        logger.info("RSS画像を取得: %s", image_url)
        data_url = image_to_data_url(image_url) or ""

    # 2. Playwright スクリーンショットを試行
    if not data_url and source_url:
        logger.info("記事URLからスクリーンショットを取得: %s", source_url)
        data_url = screenshot_article_url(source_url) or ""

    if not data_url:
        logger.warning("スクリーンショットの取得に失敗しました")
        return False

    # data URL → PNG ファイルに保存
    try:
        _, b64_data = data_url.split(",", 1)
        img_bytes = base64.b64decode(b64_data)
        img = Image.open(io.BytesIO(img_bytes))
        img.save(output_path)
        logger.info("スクリーンショット保存完了: %s (%dx%d)", output_path, img.width, img.height)
        return True
    except Exception as e:
        logger.error("スクリーンショット保存失敗: %s", e)
        return False


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    success = capture_screenshot()
    sys.exit(0 if success else 1)
