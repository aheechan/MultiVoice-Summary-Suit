# Third-party components

MultiVoice Summary Suit is licensed under GPL-3.0. The portable package also
ships third-party software whose licenses are separate from this project.

| Component | Version | License | How it is used | Source |
|---|---|---|---|---|
| FFmpeg | 8.0 (gpl-shared build) | GPL-2.0-or-later | Audio extraction and probing | https://ffmpeg.org/download.html |
| CPython | 3.12 | PSF-2.0 | Bundled runtime | https://www.python.org/ |
| PySide6 / Qt | 6.x | LGPL-3.0 (dynamic linking) | Desktop UI | https://www.qt.io/ |
| PyTorch | 2.x | BSD-3-Clause | ASR inference | https://pytorch.org/ |
| transformers / tokenizers | — | Apache-2.0 | Model loading | https://huggingface.co/ |
| llama.cpp | — | MIT | Local LLM runtime (not bundled) | https://github.com/ggml-org/llama.cpp |
| Qwen3-ASR 0.6B | — | Apache-2.0 (model weights) | Speech recognition | https://huggingface.co/Qwen |
| Qwen3.5-9B | — | See model card | Local LLM (not bundled) | https://huggingface.co/Qwen |

## Distribution notes

- The portable package contains a **GPL build of FFmpeg**. When redistributing
  that package you must also make the corresponding FFmpeg source available
  (or provide a written offer) and keep its license text.
- Qt is dynamically linked; users must be able to replace the Qt libraries in
  `runtime/venv/Lib/site-packages/PySide6`.
- Model weights keep their upstream licenses; they are not relicensed by this
  project.
- The project name and logo are not covered by the GPL.

## Source for this project

https://github.com/aheechan/MultiVoice-Summary-Suit
