"""Stable Diffusion (SD 1.5) によるローカル背景画像生成"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

OUTPUT_SIZE = (1080, 1920)
MODEL_ID = "runwayml/stable-diffusion-v1-5"


def generate_background_image(article_title: str, output_path: Path) -> Path | None:
    """記事タイトルをもとに Stable Diffusion で背景画像を生成する。

    初回実行時はモデルをダウンロード（~4GB）。
    diffusers 未インストール、または生成失敗時は None を返す（フォールバック）。
    """
    try:
        import torch
        from diffusers import StableDiffusionPipeline
        from PIL import Image
    except ImportError:
        logger.warning(
            "diffusers が未インストールのため背景画像生成をスキップします。"
            "インストール: uv add diffusers transformers accelerate"
        )
        return None

    prompt = (
        f"Abstract futuristic technology background, {article_title}, "
        "dark blue and cyan neon glow, bokeh, cinematic lighting, "
        "no text, no people, vertical portrait"
    )
    negative_prompt = "text, watermark, logo, people, face, body parts, ugly, blurry"

    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32

    if device == "cpu":
        logger.warning("GPU が検出されませんでした。CPU で生成します（数分かかります）")

    try:
        logger.info("Stable Diffusion モデルを読み込み中: %s", MODEL_ID)
        pipe = StableDiffusionPipeline.from_pretrained(
            MODEL_ID,
            torch_dtype=dtype,
            safety_checker=None,
        )
        pipe.enable_attention_slicing()
        if device == "cuda":
            # GPU 使用時のみ CPU オフロードを有効化（accelerate が必要）
            try:
                pipe.enable_model_cpu_offload()
            except Exception:
                pipe = pipe.to(device)
        else:
            pipe = pipe.to(device)

        logger.info("背景画像を生成中...")
        image = pipe(
            prompt=prompt,
            negative_prompt=negative_prompt,
            height=1024,
            width=576,
            num_inference_steps=30,
            guidance_scale=7.5,
        ).images[0]

        image = image.resize(OUTPUT_SIZE, Image.LANCZOS)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path)
        logger.info("背景画像生成完了: %s", output_path)
        return output_path

    except Exception as e:
        logger.warning("背景画像生成に失敗しました: %s", e)
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    out = Path(".cache/images/test_bg.png")
    result = generate_background_image("OpenAI releases GPT-5", out)
    if result:
        print(f"生成完了: {result}")
    else:
        print("生成失敗（diffusers 未インストールまたはエラー）")
