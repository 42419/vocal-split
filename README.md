# vocal-split

**English** | [简体中文](README.zh-CN.md)

Split songs into vocals and instrumental with Mel-Band RoFormer. One command,
GPU-accelerated, works on single files or entire folders.

The default model (Duality V2) handles dense pop and DJ mixes noticeably better
than MDX or BS-RoFormer — less instrumental bleed in the vocal stem and fewer
artifacts around cymbals.

## Requirements

- **Python 3.12** (recommended). 3.10–3.13 work; **3.14 does not** — `diffq-fixed`
  ships wheels only up to cp313, so pip falls back to a source build that needs MSVC.
- ffmpeg on `PATH` — required. Every input is decoded to WAV through ffmpeg before
  separation, because the separator itself can only read formats libsndfile knows
- GPU optional — CUDA is used when available, CPU works too but is roughly 10× slower

## Install

```bash
git clone https://github.com/42419/vocal-split.git
cd vocal-split
python -m venv .venv

# Windows / Linux with CUDA 12.8 — install the torch stack first, pinned
.venv\Scripts\pip install torch==2.11.0+cu128 torchaudio==2.11.0+cu128 torchvision==0.26.0+cu128 --index-url https://download.pytorch.org/whl/cu128
.venv\Scripts\pip install "audio-separator[gpu]" audioread

# verify CUDA is visible before going further
.venv\Scripts\python -c "import torch; print(torch.cuda.is_available())"
```

On Linux / macOS replace `.venv\Scripts\` with `.venv/bin/` and drop the `+cu128`
suffix on macOS (CPU only).

> **Keep the version pins.** `audio-separator` pulls `onnx2torch-py313`, which
> requires `torchvision`. If torchvision is not installed yet, pip fetches the
> latest one from PyPI — and that release pins a newer torch, so pip silently
> **uninstalls your CUDA build and installs the CPU wheel**, leaving
> `torch.cuda.is_available()` at `False`. Installing the matching torchvision
> in the same step prevents it.

## Model download

First run downloads the default model automatically — no manual step:

| File | Size | Location |
|---|---|---|
| `melband_roformer_instvox_duality_v2.ckpt` | ~1.7 GB | `models/` |

A small checksum manifest is fetched at the same time. After that the tool works
offline; `models/` is git-ignored, so it survives `git pull` but not a fresh clone.

> **Two known pitfalls**
>
> 1. `audio-separator 0.47.1` imports `audioread` without declaring it, and librosa 1.0
>    no longer pulls it in. Without it the import fails with
>    `ModuleNotFoundError: No module named 'audioread'` — hence the explicit
>    `audioread` in the install command above.
> 2. The first run fetches a checksum list from `raw.githubusercontent.com`. Behind
>    the GFW this fails with `SSL: UNEXPECTED_EOF`. Set a proxy first:
>
>    ```bash
>    export HTTPS_PROXY=http://127.0.0.1:PORT HTTP_PROXY=http://127.0.0.1:PORT
>    export https_proxy=http://127.0.0.1:PORT http_proxy=http://127.0.0.1:PORT
>    ```
>
>    On Linux set the lowercase variants too — they take precedence over the
>    uppercase ones.

## Usage

> `python` below means the project virtualenv. If you have not activated it, use
> `.venv\Scripts\python` on Windows or `.venv/bin/python` on Linux/macOS —
> otherwise you get `audio-separator is not installed`, because the system Python
> knows nothing about this venv.

```bash
# single file
python tools/stem.py "music/song.flac"

# whole folder, recursive
python tools/stem.py "music/" -o output/stems

# overwrite existing output
python tools/stem.py song.wav --force
```

Output goes to `output/stems/` by default:

```
output/stems/<name>_vocals.wav
output/stems/<name>_instrumental.wav
```

Supported input: `wav` `flac` `mp3` `m4a` `aac` `ogg` `opus` `wma`, plus video
files such as `mp4` and `mkv`. Video is handled by decoding the audio track with
ffmpeg first — the separator never sees the container.

## Removing vocals that sit inside the backing track

The default model answers one question: *singing or not*. Anything that sings in
the backing track — harmonies, backing vocals, vocal chops, a sampled hook — is
therefore grouped into the vocal stem together with the lead.

To pull those out, run a second pass with a karaoke model:

```bash
# 1. vocals / instrumental -> output/stems/
python tools/stem.py "song.mp3"

# 2. lead vs everything else that sings -> output/lead/
python tools/stem.py "output/stems/song_vocals.wav" \
    --model mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt \
    -o output/lead
```

The second pass produces:

| File | Content |
|---|---|
| `output/lead/song_vocals_vocals.wav` | lead vocal |
| `output/lead/song_vocals_instrumental.wav` | the backing vocals that were removed |

Karaoke models that work:

| Model | Size | Notes |
|---|---|---|
| `mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt` | 913 MB | best quality, verified |
| `5_HP-Karaoke-UVR.pth` | 127 MB | smaller, one step down |
| `6_HP-Karaoke-UVR.pth` | 127 MB | same size, different training set |

The model is downloaded on first use, like the default one.

Limits worth knowing:

- Works when the backing vocal is clearly a separate part (harmony, ad-libs).
- Struggles when both sing in unison at the same pitch — expect bleed in both directions.
- If the "backing vocal" is really a sampled hook from another track, the model may
  keep it as lead, because it sounds like ordinary singing.

## Options

| Flag | Default | Description |
|---|---|---|
| `-o, --output` | `output/stems` | Output directory |
| `--model` | `melband_roformer_instvox_duality_v2.ckpt` | Any model supported by audio-separator |
| `--force` | off | Overwrite existing output |

## Performance

RTX 4050 Laptop, ~2 GB VRAM:

| Audio length | Time |
|---|---|
| 12 s | 5 s |
| 2 min | 50 s |
| 4 min | 1 min 32 s |

Roughly 2.5× realtime.

## Limitations

- `onnxruntime-gpu` may log `Failed to load cudart64_13.dll` / `cublasLt64_13.dll` at
  startup when it was built against CUDA 13 while torch ships CUDA 12. Harmless for
  the default model, which runs purely on torch — it only matters if you point
  `--model` at an ONNX file.
- Live recordings with heavy reverb: passages where the vocal is very quiet can
  be gated to silence by the separator. On one concert recording, 13% of the
  runtime had a vocal stem below -45 dB.
- Output is stereo 44.1 kHz. For mono, post-process with `ffmpeg -ac 1`.
- The whole file is loaded into memory; expect ~1.5 GB RAM for a 4-minute track.

## License

Script code is MIT. Model weights remain under their original authors' license.
