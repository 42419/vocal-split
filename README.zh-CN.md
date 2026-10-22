# vocal-split

[English](README.md) | **简体中文**

把歌曲拆成人声与伴奏。一条命令搞定，支持显卡加速，单个文件或整个目录都行。

默认模型 Duality V2 对流行、DJ 这类密集编曲的处理明显好于 MDX 和 BS-RoFormer——
人声轨里的伴奏残留更少，镲片附近的毛刺也更轻。

## 环境要求

- **Python 3.12**（推荐）。3.10–3.13 可用；**3.14 不行** —— `diffq-fixed` 只发到 cp313
  的轮子，pip 会退回源码编译，需要 MSVC，基本必失败
- ffmpeg 在 `PATH` 中（处理非 WAV 输入和视频文件时用到）
- 显卡可选。有 CUDA 时自动走显卡，没有也能跑，速度慢约 10 倍

## 安装

```bash
git clone https://github.com/42419/vocal-split.git
cd vocal-split
python -m venv .venv

# Windows / Linux（CUDA 12.8）—— 先装 pytorch 三件套，版本必须钉住
.venv\Scripts\pip install torch==2.11.0+cu128 torchaudio==2.11.0+cu128 torchvision==0.26.0+cu128 --index-url https://download.pytorch.org/whl/cu128
.venv\Scripts\pip install "audio-separator[gpu]" audioread

# 装完先确认显卡可见，再继续
.venv\Scripts\python -c "import torch; print(torch.cuda.is_available())"
```

Linux / macOS 把 `.venv\Scripts\` 换成 `.venv/bin/`；macOS 去掉 `+cu128` 后缀（只有 CPU 版）。

> **版本不要放开。** `audio-separator` 会拉 `onnx2torch-py313`，它依赖 `torchvision`。
> 如果环境里还没有 torchvision，pip 会从 PyPI 装最新版，而这个版本绑定了更新的 torch，
> 于是 pip 会**把你刚装好的 CUDA 版 torch 卸载掉，换成 PyPI 上的 CPU 版**，
> 结果 `torch.cuda.is_available()` 变成 `False`。同一步里把匹配的 torchvision 装好即可避免。

## 模型下载

首次运行会自动下载默认模型，不需要手动操作：

| 文件 | 大小 | 位置 |
|---|---|---|
| `melband_roformer_instvox_duality_v2.ckpt` | 约 1.7 GB | `models/` |

同时会拉一个小的校验清单。下载完成后即可离线使用；`models/` 已在 git 忽略列表中，
`git pull` 不会覆盖它，但重新 clone 需要重新下载。

> **两个已知坑**
>
> 1. `audio-separator 0.47.1` 代码里 `import audioread`，但没写进依赖声明；librosa 1.0
>    又移除了这个依赖，所以必须手动装 `audioread`，否则 import 阶段就报
>    `ModuleNotFoundError: No module named 'audioread'`。
> 2. 首次运行要访问 `raw.githubusercontent.com` 拉模型校验清单。国内直连通常会
>    `SSL: UNEXPECTED_EOF`，先设代理再跑：
>
>    ```powershell
>    $env:HTTPS_PROXY="http://127.0.0.1:你的端口"
>    $env:HTTP_PROXY="http://127.0.0.1:你的端口"
>    $env:https_proxy="http://127.0.0.1:你的端口"
>    $env:http_proxy="http://127.0.0.1:你的端口"
>    ```
>
>    requests 优先读小写变量，只设大写可能不生效。

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
以及 `mp4`、`mkv` 这类带音轨的视频文件。所有输入都会先用 ffmpeg 解码成 WAV
再交给分离器——分离器本身只认 libsndfile 支持的格式，读不了视频容器。

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

- 启动时可能打印 `Failed to load cudart64_13.dll` / `cublasLt64_13.dll`：这是
  `onnxruntime-gpu` 按 CUDA 13 编译、而 torch 带的是 CUDA 12 导致的。默认模型
  纯走 torch，不影响使用；只有你把 `--model` 换成 ONNX 模型时才需要处理
- 混响极重的现场录音：人声很弱的段落会被分离器切成静音。实测某演唱会版有 13%
  的时长里人声轨低于 -45dB
- 输出为立体声 44.1kHz。需要单声道请自行后处理：`ffmpeg -ac 1`
- 整段音频会载入内存，4 分钟的曲子约占用 1.5GB

## 许可

脚本部分为 MIT。模型权重版权归原作者，使用前请确认其许可条款。
