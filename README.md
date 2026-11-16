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

## 梗词库与时效

网络梗、人物绰号、产品名变化很快，所以词库按**时效类型**管理：

| kind | 例子 | 有效期 |
|---|---|---|
| `evergreen` | 梁文锋、机构名、地名 | 10 年 |
| `product` | V4Flash、V4Pro、DeepSeek Harness | 120 天 |
| `current` | 斩杀线（当下网络热词） | 30 天 |
| `event` | 具体新闻事件 | 90 天 |

每个词条记录 `last_verified`、`sources`、`confidence`。识别前会：

1. **别名修复**：把已知的听错写法直接替换成正确词（`梁盛 → 梁圣`、`转差线 → 斩杀线`）
2. **按主题注入**：命中任一 DeepSeek 词条，就把整个 deepseek 主题包（人物、产品、梗）一起放进纠错提示
3. **现场检索**：遇到词库没有、或已过期的词，立刻搜 Bing + 让模型判断 `kind` 与有效期再入库；只收标题能对上的词，避免伪词条污染

```powershell
mvs glossary list
mvs glossary stale
mvs glossary add --term 梁圣 --alias 梁盛 --kind evergreen --topic deepseek --definition "..."
mvs glossary research --term 新梗
```

词库位置：`D:\Local Repositories\MultiVoice-Summary-Suit\glossary\terms.jsonl`（不在仓库内）。

## 托盘界面

<p align="center"><img src="assets/icon.png" width="120" alt="MultiVoice Summary Suit"></p>

双击 `Start-MultiVoice.bat` 启动，也可以把音视频文件直接拖到 bat 上，立即开始转写。

工作流是**两段式**，先看文稿再出成品：

| 步骤 | 操作 | 结果 |
|---|---|---|
| 1 | **Transcribe file…** | 识别 + 纠错 + 双语文本 |
| 2 | **Open outputs → Transcript** | 核对原文、译文、对照稿 |
| 3 | **Generate outputs (a / b / c)** | 生成口播稿、知识报告、快报 |

`Open outputs` 子菜单会列出六个入口，文件不存在时自动置灰：

| 菜单项 | 文件 |
|---|---|
| Transcript · original | `text\original.txt` |
| Transcript · translation | `text\translated.<lang>.txt` |
| Transcript · side by side | `text\bilingual.<src>-<tgt>.txt` |
| A · Spoken script | `a-script.md` |
| B · Knowledge report | `b-report.md` |
| C · Brief | `c-brief.md` |

所有界面文案为英文，任务在后台线程执行，完成与失败都会弹系统通知。

> 生成阶段有防编造守卫：如果模型输出的长度超过原文的 1.3–1.6 倍，直接回退到原文，宁可简短也不产出虚构内容。

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
