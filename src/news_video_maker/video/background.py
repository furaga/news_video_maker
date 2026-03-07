"""Stable Diffusion (SD 1.5) によるローカル背景画像生成"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

OUTPUT_SIZE = (1080, 1920)
MODEL_ID = "runwayml/stable-diffusion-v1-5"

_NEGATIVE_PROMPT = (
    "text, watermark, logo, signature, people, face, body parts, "
    "ugly, blurry, low quality, distorted, deformed, artifacts, "
    "cartoon, anime, painting, sketch"
)


def _build_prompt(article_title: str, keyword: str) -> tuple[str, str]:
    prompt = (
        f"Cinematic technology background, {keyword}, "
        "dark blue and cyan neon glow, bokeh, cinematic lighting, "
        "high detail, 8k, ultra realistic, vertical portrait"
    )
    return prompt, _NEGATIVE_PROMPT


def _load_sd_pipeline(device: str, dtype):
    from diffusers import StableDiffusionPipeline

    pipe = StableDiffusionPipeline.from_pretrained(
        MODEL_ID,
        torch_dtype=dtype,
        safety_checker=None,
    )
    pipe.enable_attention_slicing()
    if device == "cuda":
        try:
            pipe.enable_model_cpu_offload()
        except Exception:
            pipe = pipe.to(device)
    else:
        pipe = pipe.to(device)
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
        from diffusers import StableDiffusionPipeline  # noqa: F401
    except ImportError:
        logger.warning(
            "diffusers が未インストールのため背景画像生成をスキップします。"
            "インストール: uv add diffusers transformers accelerate"
        )
        return []

    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32

    if device == "cpu":
        logger.warning("GPU が検出されませんでした。CPU で生成します（1枚あたり数分かかります）")

    output_dir.mkdir(parents=True, exist_ok=True)

    # キーワードリスト: article_title + key_points を順番に使う（custom_prompts がない場合）
    keywords = [article_title] + list(key_points)
    results: list[tuple[Path, str]] = []
    prompts_data = []

    try:
        logger.info("Stable Diffusion モデルを読み込み中: %s", MODEL_ID)
        pipe = _load_sd_pipeline(device, dtype)

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
                height=1024,
                width=576,
                num_inference_steps=40,
                guidance_scale=12.0,
            ).images[0]

            image = image.resize(OUTPUT_SIZE, Image.LANCZOS)
            image.save(out_path)
            logger.info("背景画像生成完了: %s", out_path)

            results.append((out_path, prompt))
            prompts_data.append({
                "index": i,
                "path": str(out_path),
                "prompt": prompt,
                "keyword": keyword,
            })

    except Exception as e:
        logger.warning("背景画像生成に失敗しました: %s", e)
        return []

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
