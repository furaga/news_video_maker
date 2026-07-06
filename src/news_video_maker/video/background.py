"""Stable Diffusion / SDXL Turbo による背景画像生成"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

OUTPUT_SIZE = (1080, 920)

_NEGATIVE_PROMPT = (
    "text, watermark, logo, signature, "
    "ugly, blurry, low quality, distorted, deformed, mutated, extra limbs, "
    "artifacts, cartoon, anime, painting, sketch, nsfw, oversaturated"
)


def _build_prompt(article_title: str, keyword: str) -> tuple[str, str]:
    prompt = (
        f"Cinematic technology background, {keyword}, "
        "dark blue and cyan neon glow, bokeh, cinematic lighting, "
        "high detail, 8k, ultra realistic, vertical portrait"
    )
    return prompt, _NEGATIVE_PROMPT


def _is_sdxl(model_id: str) -> bool:
    """モデルIDから SDXL 系かどうかを判定する（SD1.5 系との分岐用）。"""
    return "xl" in model_id.lower()


def _generation_params(model_id: str) -> dict:
    """モデル系統ごとの生成パラメータを返す。

    - SDXL Turbo 系: 832×704 / 7 steps / cfg 2.0
      （8GB VRAM 前提。0.6MP 以下 + CPUオフロードで動かすための解像度）
    - SD 1.5 系:     512×448 / 30 steps / cfg 7.5（従来パラメータ）

    いずれも最終的に OUTPUT_SIZE (1080×920) へリサイズする。
    """
    if _is_sdxl(model_id):
        return {"height": 704, "width": 832, "num_inference_steps": 7, "guidance_scale": 2.0}
    return {"height": 448, "width": 512, "num_inference_steps": 30, "guidance_scale": 7.5}


def _load_pipeline(model_id: str, device: str, dtype):
    """AutoPipelineForText2Image で SD1.5 / SDXL 双方をロードする。

    8GB VRAM 対策として GPU では enable_model_cpu_offload() + vae.enable_slicing() を使い、
    .to("cuda") は使わない（オフロードが自動でデバイス配置を管理するため）。
    スケジューラはモデル同梱設定をそのまま使う（Turbo 系は DPM++ SDE）。
    """
    from diffusers import AutoPipelineForText2Image

    load_kwargs = {"torch_dtype": dtype}
    if not _is_sdxl(model_id):
        # SD1.5 系は NSFW セーフティチェッカーを無効化（誤検知による黒塗りを防ぐ）
        load_kwargs["safety_checker"] = None

    if device == "cuda":
        # fp16 variant を優先し、無ければ通常の重みにフォールバック
        try:
            pipe = AutoPipelineForText2Image.from_pretrained(
                model_id, variant="fp16", **load_kwargs
            )
        except Exception:
            pipe = AutoPipelineForText2Image.from_pretrained(model_id, **load_kwargs)
        pipe.enable_model_cpu_offload()  # accelerate 必須。8GB VRAM でも SDXL が動く
        pipe.vae.enable_slicing()
    else:
        # CPU フォールバック（.to("cuda") もオフロードもしない）
        pipe = AutoPipelineForText2Image.from_pretrained(model_id, **load_kwargs)

    return pipe


def generate_background_images(
    article_title: str,
    key_points: list[str],
    num_images: int,
    output_dir: Path,
    custom_prompts: list[str] | None = None,
) -> list[tuple[Path, str]]:
    """num_images 枚の背景画像を生成し (Path, prompt) リストを返す。

    custom_prompts が渡された場合はそれをプロンプトとして使用する（bg_prompt フィールド対応）。
    それ以外は key_points を使って各画像のプロンプトを生成する。
    bg_prompts.json にプロンプト一覧を保存する。
    diffusers 未インストール、または生成失敗時は空リストを返す。
    """
    try:
        import torch
        from PIL import Image
        from diffusers import AutoPipelineForText2Image  # noqa: F401
    except ImportError:
        logger.warning(
            "diffusers が未インストールのため背景画像生成をスキップします。"
            "インストール: uv add diffusers transformers accelerate"
        )
        return []

    from news_video_maker.config import SD_MODEL_ID

    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32

    if device == "cpu":
        logger.warning("GPU が検出されませんでした。CPU で生成します（1枚あたり数分かかります）")

    output_dir.mkdir(parents=True, exist_ok=True)

    # キーワードリスト: article_title + key_points を順番に使う（custom_prompts がない場合）
    keywords = [article_title] + list(key_points)
    results: list[tuple[Path, str]] = []
    prompts_data = []

    # キャッシュチェック: すべての画像が既に存在する場合はスキップ
    all_cached = True
    for i in range(num_images):
        out_path = output_dir / f"bg_{i:02d}.png"
        if not out_path.exists():
            all_cached = False
            break

    if all_cached:
        logger.info("背景画像 %d 枚がキャッシュ済み。SD 生成をスキップします", num_images)
        for i in range(num_images):
            out_path = output_dir / f"bg_{i:02d}.png"
            prompt = (custom_prompts[i] if custom_prompts and i < len(custom_prompts)
                      else f"cached_{i}")
            results.append((out_path, prompt))
        return results

    try:
        logger.info("背景生成モデルを読み込み中: %s", SD_MODEL_ID)
        pipe = _load_pipeline(SD_MODEL_ID, device, dtype)
        gen_params = _generation_params(SD_MODEL_ID)
        logger.info("生成パラメータ: %s", gen_params)

        for i in range(num_images):
            out_path = output_dir / f"bg_{i:02d}.png"

            if custom_prompts and i < len(custom_prompts):
                # bg_prompt フィールドから直接プロンプトを使用
                prompt = custom_prompts[i]
                negative_prompt = _NEGATIVE_PROMPT
                keyword = prompt[:60] + "..." if len(prompt) > 60 else prompt
            else:
                keyword = keywords[i % len(keywords)]
                prompt, negative_prompt = _build_prompt(article_title, keyword)

            logger.info("背景画像 %d/%d 生成中... プロンプト: %s", i + 1, num_images, prompt[:80])
            image = pipe(
                prompt=prompt,
                negative_prompt=negative_prompt,
                **gen_params,
            ).images[0]

            image = image.resize(OUTPUT_SIZE, Image.LANCZOS)
            image.save(out_path)
            logger.info("背景画像生成完了: %s", out_path)

            results.append((out_path, prompt))
            if device == "cuda":
                import torch as _torch
                _torch.cuda.empty_cache()
            prompts_data.append({
                "index": i,
                "path": str(out_path),
                "prompt": prompt,
                "keyword": keyword,
            })

    except Exception as e:
        logger.warning("背景画像生成に失敗しました: %s", e)
        return []
    finally:
        # SD パイプラインを明示的に解放（Playwright レンダリング用のメモリを確保）
        if "pipe" in dir():
            del pipe
        import gc
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("SD パイプラインのメモリを解放しました")

    # プロンプト一覧を保存
    prompts_json = output_dir / "bg_prompts.json"
    prompts_json.write_text(json.dumps(prompts_data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("背景画像プロンプト保存完了: %s", prompts_json)

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    out_dir = Path(".cache/images")
    results = generate_background_images(
        "OpenAI releases GPT-5",
        ["artificial intelligence", "language model"],
        2,
        out_dir,
    )
    if results:
        print(f"生成完了: {[str(p) for p, _ in results]}")
    else:
        print("生成失敗（diffusers 未インストールまたはエラー）")
