"""AnimateDiff v3 による背景動画フレーム生成"""
import base64
import io
import itertools
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

OUTPUT_SIZE = (1080, 1920)
_ANIMATEDIFF_ADAPTER = "guoyww/animatediff-motion-adapter-v1-5-3"
_ANIMATE_FRAMES = 16   # AnimateDiff 生成フレーム数
_ANIMATE_FPS = 8       # AnimateDiff 生成 fps

_NEGATIVE_PROMPT = (
    "text, watermark, logo, people, face, hands, ugly, blurry, "
    "low quality, distorted, deformed, artifacts, nsfw, oversaturated"
)


def generate_background_video_frames(
    article_title: str,
    key_points: list[str],
    num_videos: int,
    output_dir: Path,
    section_durations: list[float],
    fps: int = 30,
    custom_prompts: list[str] | None = None,
) -> list[list[str]] | None:
    """各セクション用の背景フレームリスト（base64 PNG 文字列）を返す。

    AnimateDiff v3 で 16フレームのループを生成し、section_duration に合わせて繰り返す。
    失敗時または animatediff 未インストール時は None を返す。
    """
    try:
        import torch
        from PIL import Image
        from diffusers import AnimateDiffPipeline, MotionAdapter  # noqa: F401
    except ImportError:
        logger.warning(
            "diffusers[animatediff] が未インストールのため背景動画生成をスキップします。"
            "インストール: uv add diffusers transformers accelerate"
        )
        return None

    from news_video_maker.config import SD_MODEL_ID

    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32

    if device == "cpu":
        logger.warning("GPU が検出されませんでした。CPU で生成します（非常に遅い可能性があります）")

    output_dir.mkdir(parents=True, exist_ok=True)

    # プロンプト準備
    keywords = [article_title] + list(key_points)
    if custom_prompts:
        prompts = custom_prompts
    else:
        prompts = [
            (
                f"Cinematic technology background, {keywords[i % len(keywords)]}, "
                "dark blue and cyan neon glow, bokeh, cinematic lighting, "
                "high detail, ultra realistic"
            )
            for i in range(num_videos)
        ]

    try:
        logger.info(
            "AnimateDiff パイプラインを読み込み中: adapter=%s, base=%s",
            _ANIMATEDIFF_ADAPTER, SD_MODEL_ID,
        )
        adapter = MotionAdapter.from_pretrained(_ANIMATEDIFF_ADAPTER, torch_dtype=dtype)
        pipe = AnimateDiffPipeline.from_pretrained(
            SD_MODEL_ID,
            motion_adapter=adapter,
            torch_dtype=dtype,
        )
        pipe.enable_attention_slicing()
        pipe = pipe.to(device)

        result: list[list[str]] = []

        for i in range(num_videos):
            section_dur = section_durations[i] if i < len(section_durations) else 5.0
            target_frames = max(1, round(section_dur * fps))

            # キャッシュチェック
            cache_dir = output_dir / f"vid_{i:02d}"
            cached = _load_cached_frames(cache_dir, target_frames)
            if cached:
                logger.info("背景動画 %d/%d キャッシュ済み", i + 1, num_videos)
                result.append(cached)
                continue

            prompt = prompts[i] if i < len(prompts) else prompts[-1]
            logger.info("背景動画 %d/%d 生成中... プロンプト: %s", i + 1, num_videos, prompt[:80])

            output = pipe(
                prompt=prompt,
                negative_prompt=_NEGATIVE_PROMPT,
                num_inference_steps=20,
                guidance_scale=7.5,
                num_frames=_ANIMATE_FRAMES,
                height=512,
                width=288,
            )
            raw_frames: list = output.frames[0]  # list[PIL.Image]

            # section_duration に合わせてフレームをループ展開し target_frames 枚にする
            cycle_iter = itertools.cycle(raw_frames)
            expanded = [next(cycle_iter) for _ in range(target_frames)]

            # 1080x1920 にリサイズしてキャッシュ保存 + base64 変換
            cache_dir.mkdir(parents=True, exist_ok=True)
            frames_b64: list[str] = []
            for j, frame in enumerate(expanded):
                frame_resized = frame.resize(OUTPUT_SIZE, Image.LANCZOS)
                cache_path = cache_dir / f"frame_{j:04d}.png"
                frame_resized.save(cache_path)
                buf = io.BytesIO()
                frame_resized.save(buf, format="PNG")
                b64 = base64.b64encode(buf.getvalue()).decode()
                frames_b64.append(f"data:image/png;base64,{b64}")

            result.append(frames_b64)
            if device == "cuda":
                torch.cuda.empty_cache()

        return result

    except Exception as e:
        logger.warning("背景動画生成に失敗しました: %s", e)
        return None
    finally:
        if "pipe" in dir():
            del pipe
        import gc
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("AnimateDiff パイプラインのメモリを解放しました")


def _load_cached_frames(cache_dir: Path, target_frames: int) -> list[str] | None:
    """キャッシュ済みフレームを読み込んで base64 リストを返す。なければ None。"""
    if not cache_dir.exists():
        return None
    frames = sorted(cache_dir.glob("frame_*.png"))
    if len(frames) != target_frames:
        return None
    result = []
    for path in frames:
        b64 = base64.b64encode(path.read_bytes()).decode()
        result.append(f"data:image/png;base64,{b64}")
    return result
