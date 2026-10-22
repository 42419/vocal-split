#!/usr/bin/env python3
"""Split audio into vocals and instrumental using Mel-Band RoFormer.

Usage:
    python tools/stem.py song.flac
    python tools/stem.py music/ -o output/stems
    python tools/stem.py clip.mp4
    python tools/stem.py song.wav --model melband_roformer_instvox_duality_v2.ckpt

Output:
    <output>/<name>_vocals.wav
    <output>/<name>_instrumental.wav

Every input is decoded to a temporary 44.1 kHz stereo WAV with ffmpeg before it
reaches the separator. The separator itself reads files through libsndfile,
which cannot open video containers or some compressed formats.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "models"
TEMP = ROOT / ".tmp" / "stem_tmp"
AUDIO_EXT = {
    ".wav", ".flac", ".mp3", ".m4a", ".aac",
    ".ogg", ".opus", ".wma", ".mp4", ".mkv",
}


def collect(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    return sorted(p for p in target.rglob("*") if p.suffix.lower() in AUDIO_EXT)


def decode(src: Path, dst: Path) -> None:
    """Transcode any input to a plain 44.1 kHz stereo WAV."""
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(src), "-vn", "-ar", "44100", "-ac", "2",
        "-c:a", "pcm_s16le", str(dst),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip().splitlines()[-1] or "ffmpeg failed")


def main() -> int:
    ap = argparse.ArgumentParser(description="Split audio into vocals and instrumental.")
    ap.add_argument("input", help="audio or video file, or a directory")
    ap.add_argument("-o", "--output", default="output/stems", help="output directory")
    ap.add_argument(
        "--model",
        default="melband_roformer_instvox_duality_v2.ckpt",
        help="any model supported by audio-separator",
    )
    ap.add_argument("--force", action="store_true", help="overwrite existing output")
    args = ap.parse_args()

    src = Path(args.input)
    if not src.exists():
        print(f"[stem] not found: {src}")
        return 1

    if shutil.which("ffmpeg") is None:
        print("[stem] ffmpeg not found on PATH; it is required to decode inputs")
        return 2

    try:
        from audio_separator.separator import Separator
    except ModuleNotFoundError as exc:
        pkg = (exc.name or "").split(".")[0]
        if pkg == "audio_separator":
            print("[stem] audio-separator is not installed.")
            print('        pip install "audio-separator[gpu]"')
        else:
            print(f"[stem] audio-separator imports '{pkg}', which is missing.")
            print(f"        pip install {pkg}")
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"[stem] cannot import audio-separator: {type(exc).__name__}: {exc}")
        return 2

    files = collect(src)
    if not files:
        print(f"[stem] no supported audio in {src}")
        return 1

    out = Path(args.output)
    if not out.is_absolute():
        out = ROOT / out
    out.mkdir(parents=True, exist_ok=True)
    TEMP.mkdir(parents=True, exist_ok=True)
    decode_dir = TEMP / "decoded"
    decode_dir.mkdir(parents=True, exist_ok=True)

    todo = [f for f in files if args.force or not (out / f"{f.stem}_vocals.wav").exists()]
    if not todo:
        print("[stem] everything already exists, nothing to do (use --force to redo)")
        return 0

    print(f"[stem] {len(todo)} file(s) queued | model: {args.model}")
    sep = Separator(
        model_file_dir=str(MODELS),
        output_dir=str(TEMP),
        output_format="WAV",
    )
    sep.load_model(model_filename=args.model)

    ok = fail = 0
    for i, f in enumerate(todo, 1):
        decoded = decode_dir / f"{i}.wav"
        try:
            decode(f, decoded)
            produced = sep.separate(str(decoded))
            paths = [
                Path(p) if Path(p).is_absolute() else TEMP / Path(p).name
                for p in produced
            ]
            vocal = next((p for p in paths if "(vocals)" in p.name.lower()), None)
            inst = next((p for p in paths if "(instrumental)" in p.name.lower()), None)
            if vocal is None:
                raise RuntimeError("no vocal stem in separator output")
            shutil.move(str(vocal), str(out / f"{f.stem}_vocals.wav"))
            if inst is not None:
                shutil.move(str(inst), str(out / f"{f.stem}_instrumental.wav"))
            ok += 1
            print(f"  [{i}/{len(todo)}] {f.name}")
        except Exception as exc:  # noqa: BLE001
            fail += 1
            print(f"  [{i}/{len(todo)}] failed {f.name}: {exc}")
        finally:
            decoded.unlink(missing_ok=True)

    shutil.rmtree(TEMP, ignore_errors=True)
    print(f"\n[stem] done: {ok} ok, {fail} failed -> {out}")
    return 0 if fail == 0 else 3


if __name__ == "__main__":
    sys.exit(main())
