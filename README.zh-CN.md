# vocal-split

[English](README.md) | **简体中文**

把歌曲拆成人声与伴奏。一条命令搞定，支持显卡加速，单个文件或整个目录都行。

默认模型 Duality V2 对流行、DJ 这类密集编曲的处理明显好于 MDX 和 BS-RoFormer——
人声轨里的伴奏残留更少，镲片附近的毛刺也更轻。

## 环境要求

- Python 3.10+
- ffmpeg 在 `PATH` 中（处理非 WAV 输入和视频文件时用到）
- 显卡可选。有 CUDA 时自动走显卡，没有也能跑，速度慢约 10 倍

## 安装

```bash
git clone https://github.com/42419/vocal-split.git
cd vocal-split
python -m venv .venv

# Windows
.venv\Scripts\pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128
.venv\Scripts\pip install "audio-separator[gpu]"

# Linux / macOS
.venv/bin/pip install torch torchaudio
.venv/bin/pip install "audio-separator[gpu]"
```

首次运行时模型权重（约 1.7GB）会自动下载到 `models/`。

## 用法

```bash
# 单个文件
python tools/stem.py "music/song.flac"

# 整个目录（递归）
python tools/stem.py "music/" -o output/stems

# 覆盖已有结果
python tools/stem.py song.wav --force
```

默认输出到 `output/stems/`：

```
output/stems/<文件名>_vocals.wav        # 人声
output/stems/<文件名>_instrumental.wav  # 伴奏
```

支持的输入格式：`wav` `flac` `mp3` `m4a` `aac` `ogg` `opus` `wma`，
以及 `mp4`、`mkv` 这类带音轨的视频文件（依赖 ffmpeg）。

## 参数

| 参数 | 默认值 | 说明 |
|---|---|---|
| `-o, --output` | `output/stems` | 输出目录 |
| `--model` | `melband_roformer_instvox_duality_v2.ckpt` | 可换用 audio-separator 支持的其他模型 |
| `--force` | 关 | 覆盖已有结果 |

## 性能

RTX 4050 Laptop，显存占用约 2GB：

| 音频时长 | 耗时 |
|---|---|
| 12 秒 | 5 秒 |
| 2 分钟 | 50 秒 |
| 4 分钟 | 1 分 32 秒 |

约 2.5 倍实时速度。

## 已知限制

- 混响极重的现场录音：人声很弱的段落会被分离器切成静音。实测某演唱会版有 13%
  的时长里人声轨低于 -45dB
- 输出为立体声 44.1kHz。需要单声道请自行后处理：`ffmpeg -ac 1`
- 整段音频会载入内存，4 分钟的曲子约占用 1.5GB

## 许可

脚本部分为 MIT。模型权重版权归原作者，使用前请确认其许可条款。
