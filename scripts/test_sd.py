"""Stable Diffusion 単体テストスクリプト

GPU/CPU 確認・プロンプト調整・パラメータ変更を簡単に試せる。

使用例:
    uv run scripts/test_sd.py --prompt "OpenAI releases GPT-5"
    uv run scripts/test_sd.py --prompt "AI chip wars" --steps 40 --guidance 12.0
    uv run scripts/test_sd.py --prompt "test" --force-cpu --steps 5
"""
import argparse
import subprocess
import sys
from pathlib import Path


def print_device_info(force_cpu: bool) -> str:
    """GPU/CPU 情報を表示してデバイス名を返す。"""
    try:
        import torch
    except ImportError:
        print("ERROR: torch がインストールされていません")
        sys.exit(1)

    print("=== デバイス情報 ===")
    print(f"PyTorch: {torch.__version__}")
    print(f"CUDA 使用可能: {torch.cuda.is_available()}")

    if torch.cuda.is_available():
        print(f"CUDA バージョン: {torch.version.cuda}")
        print(f"GPU 数: {torch.cuda.device_count()}")
        for i in range(torch.cuda.device_count()):
            props = torch.cuda.get_device_properties(i)
            vram_gb = props.total_memory / 1024**3
            print(f"  GPU {i}: {props.name} ({vram_gb:.1f} GB VRAM)")

    if force_cpu:
        device = "cpu"
        print("モード: CPU 強制（--force-cpu 指定）")
    elif torch.cuda.is_available():
        device = "cuda"
        print("モード: GPU")
    else:
        device = "cpu"
        print("モード: CPU（GPU が検出されませんでした）")

    print("=" * 20)
    return device


def run_sd(prompt: str, steps: int, guidance: float, output: Path, device: str) -> None:
    """Stable Diffusion を実行して画像を生成する。"""
    try:
        import torch
        from diffusers import StableDiffusionPipeline
        from PIL import Image
    except ImportError as e:
        print(f"ERROR: 必要なライブラリが不足しています: {e}")
        print("インストール: uv add diffusers transformers accelerate")
        sys.exit(1)

    model_id = "runwayml/stable-diffusion-v1-5"
    dtype = torch.float16 if device == "cuda" else torch.float32

    full_prompt = (
        f"Cinematic technology background, {prompt}, "
        "dark blue and cyan neon glow, bokeh, cinematic lighting, "
        "high detail, 8k, ultra realistic, vertical portrait"
    )
    negative_prompt = (
        "text, watermark, logo, signature, people, face, body parts, "
        "ugly, blurry, low quality, distorted, deformed, artifacts, "
        "cartoon, anime, painting, sketch"
    )

    print(f"\nプロンプト: {full_prompt}")
    print(f"ネガティブ: {negative_prompt}")
    print(f"Steps: {steps}, Guidance: {guidance}, Device: {device}")
    print(f"出力先: {output}\n")

    print("モデルを読み込み中...")
    pipe = StableDiffusionPipeline.from_pretrained(
        model_id,
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

    print("画像を生成中...")
    image = pipe(
        prompt=full_prompt,
        negative_prompt=negative_prompt,
        height=1024,
        width=576,
        num_inference_steps=steps,
        guidance_scale=guidance,
    ).images[0]

    image = image.resize((1080, 1920), Image.LANCZOS)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
    print(f"\n生成完了: {output}")


def open_image(path: Path) -> None:
    """OS のデフォルトビューワーで画像を開く。"""
    try:
        if sys.platform == "win32":
            subprocess.Popen(["start", str(path)], shell=True)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception as e:
        print(f"画像を自動で開けませんでした: {e}")


def main():
    parser = argparse.ArgumentParser(description="Stable Diffusion 単体テストスクリプト")
    parser.add_argument("--prompt", "-p", default="AI technology news", help="記事タイトル（プロンプトに埋め込まれる）")
    parser.add_argument("--steps", "-s", type=int, default=40, help="推論ステップ数（デフォルト: 40）")
    parser.add_argument("--guidance", "-g", type=float, default=12.0, help="guidance_scale（デフォルト: 12.0）")
    parser.add_argument("--output", "-o", type=Path, default=Path(".cache/images/test_sd.png"), help="出力ファイルパス")
    parser.add_argument("--force-cpu", action="store_true", help="GPU があっても CPU で実行")
    args = parser.parse_args()

    device = print_device_info(args.force_cpu)
    run_sd(args.prompt, args.steps, args.guidance, args.output, device)
    open_image(args.output)


if __name__ == "__main__":
    main()
