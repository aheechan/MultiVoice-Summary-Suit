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

## 词库：类型与领域

词条描述的是客观存在的事物，**不会过期**。入库时回答两个问题，都用于检索与关联，不用于计时：

| 问题 | 选项 | 用途 |
|---|---|---|
| 它是什么？ | 人物 / 机构 / 产品 / 工具 / 乐器 / 作品 / 人文概念 / 热词 / 理论 / 事件 / 地点 / 其他 | 描述事物性质 |
| 它属于哪个领域？ | AI 与科技 / 商业财经 / 历史政治 / 科学医学 / 文化艺术 / 生活日常 / 其他 | 归入领域，便于按主题查阅 |

每个词条记录 `category`、`domain`、`topic`、`sources`、`confidence`。识别前会：

1. **别名修复**：把已知的听错写法直接替换成正确词（`梁盛 → 梁圣`、`转差线 → 斩杀线`）
2. **按主题注入**：命中任一 DeepSeek 词条，就把整个 deepseek 主题包（人物、产品、梗）一起放进纠错提示
3. **新词进审查队列，不静默入库**：转写时遇到词库没有的词先排队；空闲时统一做中英检索并生成双语摘要；只有你在审查窗口点"写入知识库"才正式入库

```powershell
mvs glossary list
mvs glossary stale
mvs glossary pending      # 搜不到、待人工确认的词
mvs glossary stats        # 词条数、主题数、待审数
mvs glossary add --term 梁圣 --alias 梁盛 --domain ai --topic deepseek --definition "..."
mvs glossary research --term 新梗
```

搜不到的词不会硬塞进词库，而是进入 `pending.jsonl` 排队，等人工确认后再 `add`。

## 设置与模型

托盘右键 **Settings…** 可以调整：

| 项 | 说明 |
|---|---|
| Research unknown terms on the web | 是否自动联网核实新词/过期词 |
| Search for new terms every day | 每天空闲时自动搜索新词，塞进待审队列 |
| Max lookups per job | 单次任务最多查几个词（控制耗时） |
| Model provider | `local` / `lan` / `cloud` 三选一 |
| **Export knowledge base…** | 把词条、主题、待审队列导出成一个 JSON |

每日自动搜索：启动 15 秒后跑一次（若当前没有任务），之后每 24 小时一次。发现的候选只进入待审队列，不会直接入库。待审词条 14 天或 3 次尝试后自动清除。

设置写在 `configs/settings.json`，下次任务生效。

云端走 DeepSeek 官方 API（`configs/models.example.toml` 的 `cloud` 段）：

```toml
[[llm.providers]]
name = "cloud"
base_url = "https://api.deepseek.com/v1"
model = "deepseek-chat"
api_key_env = "DEEPSEEK_API_KEY"
```

> 注意：**API 本身不联网搜索**。搜索是程序做的（Bing + 维基），检索结果再交给 DeepSeek 抽取和判断。所以"用 DeepSeek 4.1 自动上网"实际是"本地检索 + DeepSeek 理解"。

词库位置：`D:\Local Repositories\MultiVoice-Summary-Suit\glossary\terms.jsonl`（不在仓库内）。

## 托盘界面

<p align="center"><img src="assets/icon.png" width="120" alt="MultiVoice Summary Suit"></p>

双击 `Start-MultiVoice.bat` 启动，也可以把音视频文件直接拖到 bat 上，立即开始转写。

工作流是**两段式**，先看文稿再出成品：

| 步骤 | 操作 | 结果 |
|---|---|---|
| 1 | **Transcribe file…** | 识别 + 纠错 + 双语文本 |
| 2 | **Open outputs → Transcript** | 核对原文、译文、对照稿 |
| 3 | 三选一：**Clean spoken script** / **Knowledge report** / **Brief** | 只生成你选的那一份 |

三个成品按钮各自标注了产出内容：

| 按钮 | 产出 |
|---|---|
| Clean spoken script | 可直接朗读的第一人称稿，去掉口癖与废话 |
| Knowledge report | 逐点讲解：是什么 / 为什么 / 怎么做 / 边界 |
| Brief | 300–600 字摘要，附要点清单 |

界面支持 **EN / ZH 切换**，主界面、托盘菜单、审查窗口、设置窗口全部跟随切换。

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
