"""生成動画の自動検証（技術チェック + フレーム抽出）"""
import json
import subprocess
from pathlib import Path


def get_video_info(video_path: str) -> dict:
    """ffprobe で動画の技術情報を取得する"""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", "-show_format", str(video_path),
    ]
    out = subprocess.check_output(cmd, text=True)
    return json.loads(out)


def extract_frames(video_path: str, out_dir: Path, duration: float, count: int = 4) -> list[Path]:
    """動画から等間隔にフレームを抽出して PNG 保存する"""
    out_dir.mkdir(parents=True, exist_ok=True)
    frames = []
    for i in range(1, count + 1):
        t = duration * i / (count + 1)
        out = out_dir / f"frame_{i:02d}.png"
        subprocess.run(
            ["ffmpeg", "-ss", str(t), "-i", str(video_path),
             "-frames:v", "1", str(out), "-y"],
            check=True, capture_output=True,
        )
        frames.append(out)
    return frames


def validate_video(video_path: str, frames_dir: Path) -> dict:
    """動画の技術チェックとフレーム抽出を行い、検証結果を返す"""
    path = Path(video_path)
    result: dict = {"ok": True, "errors": [], "warnings": [], "info": {}, "frames": []}

    if not path.exists():
        result["ok"] = False
        result["errors"].append(f"ファイルが存在しない: {video_path}")
        return result

    size_mb = path.stat().st_size / 1024 / 1024
    result["info"]["size_mb"] = round(size_mb, 2)
    if size_mb < 0.5:
        result["ok"] = False
        result["errors"].append(f"ファイルサイズが小さすぎる: {size_mb:.2f}MB")

    try:
        info = get_video_info(video_path)
        duration = float(info.get("format", {}).get("duration", 0))
        result["info"]["duration_sec"] = round(duration, 1)

        if duration < 15:
            result["ok"] = False
            result["errors"].append(f"動画が短すぎる: {duration:.1f}秒（最低15秒）")
        elif duration > 120:
            result["warnings"].append(f"動画が長い: {duration:.1f}秒（目標30〜60秒）")

        streams = info.get("streams", [])
        has_audio = any(s.get("codec_type") == "audio" for s in streams)
        has_video = any(s.get("codec_type") == "video" for s in streams)

        if not has_audio:
            result["ok"] = False
            result["errors"].append("音声トラックがない")
        if not has_video:
            result["ok"] = False
            result["errors"].append("映像トラックがない")

        # フレーム抽出（視覚チェック用）
        if has_video and duration > 0:
            frames = extract_frames(video_path, frames_dir, duration)
            result["frames"] = [str(f) for f in frames]

    except FileNotFoundError:
        result["warnings"].append("ffprobe/ffmpeg が見つからない。技術チェックをスキップ")
    except Exception as e:
        result["warnings"].append(f"ffprobe 実行失敗: {e}")

    return result


if __name__ == "__main__":
    from news_video_maker.config import PIPELINE_DIR

    video_path_file = PIPELINE_DIR / "04_video_path.txt"
    if not video_path_file.exists():
        raise SystemExit(f"ERROR: {video_path_file} が見つからない")

    video_path = video_path_file.read_text(encoding="utf-8").strip()
    frames_dir = PIPELINE_DIR / "frames"

    result = validate_video(video_path, frames_dir)

    out = PIPELINE_DIR / "04_validation.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if not result["ok"]:
        raise SystemExit(1)
