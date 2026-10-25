#!/usr/bin/env python3
"""Split audio into vocals and instrumental using Mel-Band RoFormer.

Usage:
    python tools/stem.py song.flac
    python tools/stem.py music/ -o output/stems
    python tools/stem.py clip.mp4
    python tools/stem.py clips/ -o output/songs --two-pass

Output (default):
    <output>/<name>_vocals.wav
    <output>/<name>_instrumental.wav

Output (--two-pass, a second karaoke model also strips vocals that sit in the
backing track):
    <output>/<name>_vocals.wav       clean lead
    <output>/<name>_instrumental.wav accompaniment
    <output>/<name>_backing.wav      backing vocals pulled out of the mix

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
KARAOKE_MODEL = "mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt"
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


def split(sep, src: Path, work_wav: Path, dst_vocals: Path, dst_inst: Path) -> None:
    """Run one separation pass and place the two stems at the given paths."""
    decode(src, work_wav)
    try:
        produced = sep.separate(str(work_wav))
        paths = [
            Path(p) if Path(p).is_absolute() else TEMP / Path(p).name
            for p in produced
        ]
        vocal = next((p for p in paths if "(vocals)" in p.name.lower()), None)
        inst = next((p for p in paths if "(instrumental)" in p.name.lower()), None)
        if vocal is None:
            raise RuntimeError("no vocal stem in separator output")
        shutil.move(str(vocal), str(dst_vocals))
        if inst is not None:
            shutil.move(str(inst), str(dst_inst))
    finally:
        work_wav.unlink(missing_ok=True)


def load(model: str):
    from audio_separator.separator import Separator

    sep = Separator(
        model_file_dir=str(MODELS),
        output_dir=str(TEMP),
        output_format="WAV",
    )
    sep.load_model(model_filename=model)
    return sep


def main() -> int:
    ap = argparse.ArgumentParser(description="Split audio into vocals and instrumental.")
    ap.add_argument("input", help="audio or video file, or a directory")
    ap.add_argument("-o", "--output", default="output/stems", help="output directory")
    ap.add_argument(
        "--model",
        default="melband_roformer_instvox_duality_v2.ckpt",
        help="any model supported by audio-separator",
    )
    ap.add_argument(
        "--two-pass",
        action="store_true",
        help="run a second, karaoke model to remove vocals inside the backing track",
    )
    ap.add_argument(
        "--karaoke-model",
        default=KARAOKE_MODEL,
        help="model used by --two-pass",
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
        import audio_separator  # noqa: F401
    except ModuleNotFoundError as exc:
        pkg = (exc.name or "").split(".")[0]
        if pkg == "audio_separator":
            print("[stem] audio-separator is not installed.")
            print('        pip install "audio-separator[gpu]" audioread')
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

    todo = [f for f in files if args.force or not (out / f"{f.stem}_vocals.wav").exists()]
    if not todo:
        print("[stem] everything already exists, nothing to do (use --force to redo)")
        return 0

    mode = "two-pass" if args.two_pass else "single-pass"
    print(f"[stem] {len(todo)} file(s) queued | {mode} | {args.output}")

    try:
        sep = load(args.model)
    except Exception as exc:  # noqa: BLE001
        print(f"[stem] cannot load model {args.model}: {type(exc).__name__}: {exc}")
        return 2

    sep_karaoke = None
    if args.two_pass:
        try:
            sep_karaoke = load(args.karaoke_model)
        except Exception as exc:  # noqa: BLE001
            print(f"[stem] cannot load karaoke model: {type(exc).__name__}: {exc}")
            return 2
        print(f"         karaoke: {args.karaoke_model}")

    ok = fail = 0
    for i, f in enumerate(todo, 1):
        stage = TEMP / f"{i}"
        stage.mkdir(parents=True, exist_ok=True)
        try:
            first_vocals = stage / "vocals.wav"
            split(sep, f, stage / "decoded.wav", first_vocals, stage / "instrumental.wav")

            if args.two_pass:
                split(
                    sep_karaoke,
                    first_vocals,
                    stage / "decoded2.wav",
                    stage / "lead.wav",
                    stage / "backing.wav",
                )
                shutil.move(str(stage / "lead.wav"), str(out / f"{f.stem}_vocals.wav"))
                shutil.move(str(stage / "backing.wav"), str(out / f"{f.stem}_backing.wav"))
                shutil.move(
                    str(stage / "instrumental.wav"), str(out / f"{f.stem}_instrumental.wav")
                )
            else:
                shutil.move(str(first_vocals), str(out / f"{f.stem}_vocals.wav"))
                shutil.move(
                    str(stage / "instrumental.wav"), str(out / f"{f.stem}_instrumental.wav")
                )
            ok += 1
            print(f"  [{i}/{len(todo)}] {f.name}")
        except Exception as exc:  # noqa: BLE001
            fail += 1
            print(f"  [{i}/{len(todo)}] failed {f.name}: {exc}")
        finally:
            shutil.rmtree(stage, ignore_errors=True)

    shutil.rmtree(TEMP, ignore_errors=True)
    print(f"\n[stem] done: {ok} ok, {fail} failed -> {out}")
    return 0 if fail == 0 else 3


if __name__ == "__main__":
    sys.exit(main())
