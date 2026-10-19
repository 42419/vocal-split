#!/usr/bin/env python3
"""Split audio into vocals and instrumental using Mel-Band RoFormer.

Usage:
    python tools/stem.py song.flac
    python tools/stem.py music/ -o output/stems
    python tools/stem.py song.wav --model melband_roformer_instvox_duality_v2.ckpt

Output:
    <output>/<name>_vocals.wav
    <output>/<name>_instrumental.wav
"""

from __future__ import annotations

import argparse
import shutil
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


def main() -> int:
    ap = argparse.ArgumentParser(description="Split audio into vocals and instrumental.")
    ap.add_argument("input", help="audio file or directory")
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

    try:
        from audio_separator.separator import Separator
    except ImportError:
        print('[stem] missing dependency. Run: pip install "audio-separator[gpu]"')
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
        try:
            produced = sep.separate(str(f))
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

    shutil.rmtree(TEMP, ignore_errors=True)
    print(f"\n[stem] done: {ok} ok, {fail} failed -> {out}")
    return 0 if fail == 0 else 3


if __name__ == "__main__":
    sys.exit(main())
