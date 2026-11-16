# MultiVoice-Summary-Suit

**把多语言语音，变成可用的文字资产。**
*Turn multilingual speech into usable text assets.*

从视频/音频里提取语音 → 识别 → 语义纠错 → 整理成三种成品：干净口播稿、知识点报告、简要快报。

---

**中文** | [English](#english)

## 这是什么

一条本地流水线：

```
音视频 → 抽音轨 → VAD/切片 → ASR → 纠错 → 结构化 → 三种成品
                                     └─ 双语 txt 供核对
```

- **输入**：本地文件，或网络链接（公开可下载内容）
- **语种**：中文、英文为第一梯队；日、韩、意、德、印地等为第二梯队
- **输出**：
  - `a` 干净口播稿（去掉口癖、重复、跑题，保留全部事实与观点）
  - `b` 知识点报告（每个知识点：是什么 / 为什么 / 怎么做 / 边界 / 关联）
  - `c` 简要快报（300–600 字 + 要点）
  - 以上三者可选输出中英文两个版本；生成前先出双语 txt 供核对

## 设计原则

1. **本地优先**：音频不出本机，模型可替换
2. **保真优先**：纠错只改错，不改写；每个结论可回溯到原文片段
3. **不丢信息**：a 稿删的是废话，不是内容
4. **可恢复**：任务按内容哈希缓存，中断可续

## 快速开始

```powershell
# 1. 准备配置
Copy-Item configs\paths.example.toml configs\paths.toml
Copy-Item configs\models.example.toml configs\models.toml

# 2. 环境自检
python -m multivoice doctor

# 3. 跑一条
python -m multivoice run --input "D:\media\sample.mp4" --lang auto

# 4. 托盘界面（全英文）
python -m multivoice tray
```

产物默认写到 `D:\Local Repositories\MultiVoice-Summary-Suit\output\<job-id>\`。

## 托盘界面

<p align="center"><img src="assets/icon.png" width="120" alt="MultiVoice Summary Suit"></p>

常驻系统托盘，右键菜单：

| 菜单项 | 作用 |
|---|---|
| **Transcribe file…** | 选一个音视频文件，后台跑完整流程 |
| **Open output folder** | 打开成品目录 |
| **Open config folder** | 打开配置目录 |
| **About** | 版本与说明 |
| **Quit** | 退出 |

任务在后台线程执行，完成后弹系统通知；失败会显示错误摘要。所有界面文案均为英文。

## 文档

- [设计说明](docs/DESIGN.md)
- [流水线与产物](docs/PIPELINE.md)

## 许可

代码 Apache-2.0；模型权重遵循各自上游许可。

## Support

If this project saved you some time, you can [buy me a coffee](https://ko-fi.com/ahee52).

---

## English

**What it is.** A local pipeline that turns video/audio into three deliverables: a clean spoken-word script, a knowledge report, and a short brief — with bilingual transcripts for review.

**Pipeline.** audio extraction → VAD/chunking → ASR → semantic correction → information-unit extraction → generation.

**Principles.** Local-first, fidelity over fluency, no information loss, resumable by content hash.

**Status.** Early scaffold. See [docs/DESIGN.md](docs/DESIGN.md).
