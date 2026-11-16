# 流水线与产物

## 一次任务的目录

```
D:\Local Repositories\MultiVoice-Summary-Suit\
├─ work\<内容哈希>\
│  ├─ audio.wav                 16 kHz 单声道提取结果
│  ├─ segments.raw.json         ASR 原始分段（含内部时间戳）
│  ├─ segments.corrected.json   纠错后分段
│  ├─ transcript.txt            纯文本（无时间线）
│  ├─ units.json                信息单元
│  └─ manifest.json             任务元信息
└─ output\<同一 job 名>\
   ├─ a-script.md               干净口播稿
   ├─ b-report.md               知识点报告
   ├─ c-brief.md                简要快报
   └─ text\
      ├─ original.txt           纠错后的原文
      ├─ translated.en.txt      译文
      └─ bilingual.zh-en.txt    段段对照
```

任务目录名就是**源文件内容的哈希前 12 位**，所以同一个文件重复跑不会产生新目录，而是复用已有产物。

## 阶段开关

```powershell
# 只做识别，先看质量
python -m multivoice run --input "D:\media\a.mp3" --stages asr

# 识别 + 纠错 + 双语
python -m multivoice run --input "D:\media\a.mp3" --stages asr,correct,translate

# 全流程
python -m multivoice run --input "D:\media\a.mp3"

# 忽略缓存，从头重跑
python -m multivoice run --input "D:\media\a.mp3" --no-resume
```

## 断点续跑

只要 `work\<哈希>\` 里的产物还在，重跑时会跳过已完成的阶段：

| 已有文件 | 跳过的阶段 |
|---|---|
| `audio.wav` | 音轨提取 |
| `segments.raw.json` | ASR |
| `segments.corrected.json` | 纠错 |
| `units.json` | 信息单元抽取 |

这是按内容哈希而非文件路径判断的，所以改文件名不影响缓存。

## 双语输出

`configs/paths.toml` 里的 `[output] languages` 决定要哪些语言。识别出源语言后，**与源语言不同的目标语言**会各生成一组文件：

```
text\original.txt          原文
text\translated.en.txt     目标语言译文
text\bilingual.zh-en.txt   原文与译文段段对照，用 --- 分隔
```

源语言由 ASR 引擎返回；识别不出来时默认按中文处理。

## VAD 切片

`[vad]` 段控制切片行为，默认值按 **16 GB 显存**设定：

| 参数 | 默认 | 说明 |
|---|---|---|
| `enabled` | `true` | 关掉则整段送识别 |
| `max_seconds` | `30` | 单块上限。16 GB 下 30 秒是安全值，再长只增加峰值显存和延迟 |
| `min_silence` | `0.45` | 判定静音的最短时长（秒） |
| `noise_db` | `-32` | 静音阈值，BGM 重的素材可调到 `-25` |

切分逻辑：先用 ffmpeg `silencedetect` 找语音段，再把相邻段合并到不超过 `max_seconds`，末尾过短的碎片并入前一块。每块单独识别后，时间戳按块偏移还原成全局时间。

## BGM 强度与警告

不做人声分离，先判断背景音乐是否已经影响识别。指标是**语音电平与噪声底的分位差**（90% 分位减 10% 分位），不需要真的存在静音段：

| gap | 判定 | 提示 |
|---|---|---|
| ≥ 27 dB | clean | 背景干净，可直接识别 |
| 18–27 dB | light | 有背景音乐，通常仍可正常识别 |
| 10–18 dB | heavy | 背景音乐偏响，识别可能出错，建议核对文稿 |
| < 10 dB | severe | 背景接近或盖过语音，建议先做人声分离 |

结果写进 `work\<哈希>\bgm.json`，也汇总在 `manifest.json` 的 `bgm` 字段里。

### 实测（2026-11-16，Qwen3-ASR 0.6B，CPU）

用 `tools/bgm_limit.py` 对干净样本逐级加噪，以无噪转写为基准算 CER：

| SNR | gap | CER | 现象 |
|---|---|---|---|
| 20 dB | 23.3 | 4.3% | 几乎无损 |
| 15 dB | 18.7 | 2.1% | 几乎无损 |
| 10 dB | 14.3 | 11.8% | 人名开始错（桂永清→顾永兴） |
| 5 dB | 9.7 | 8.5% | 人名继续错 |
| 0 dB | 5.5 | 20.0% | 句子结构开始崩 |
| −5 dB | 2.5 | 72.7% | 完全失效 |

**结论：不做人声分离。** 三条真实样本中 BGM 最重的 exp2（gap 10.3 dB）仍输出通顺文本，只有专有名词需要人工核对；真正崩溃发生在 gap < 5 dB。阈值为此按实测校准为 20 / 14 / 8。

## 纠错模型实测

`tools/llm_check.py` 用三个含已知错误的句子测当前配置的模型：

| 用例 | 结果 |
|---|---|
| 语音转**雪** → 语音转**写** | 修正，但同句的"音**平**"未改成"音**频**" |
| 准**去**率 → 准**确**率 | 修正 |
| 长句 + 人名 | **返回空字符串** |

结论：1.7B 级模型只能处理高频同音字，漏改和空输出都存在，不适合承担正式文稿的纠错。代码已做兜底——模型少返回的行会保留原文，不会丢内容；但要真正可用，建议换 7–8B 以上的模型，或改用云端接口。

## 当前实现状态

| 阶段 | 状态 | 说明 |
|---|---|---|
| 音轨提取 | ✅ | ffmpeg，16 kHz 单声道 |
| VAD 切片 | ✅ | 静音检测 + 30 秒上限合并，时间戳还原 |
| BGM 评估 | ✅ | 分位差指标 + 四级警告 |
| ASR | ✅ | qwen3 / whisper 两个适配器，模型路径由配置决定 |
| 纠错 | ✅ | 逐段调用，只改错不改写 |
| 双语翻译 | ✅ | 段落级，源语言自动判断 |
| 信息单元抽取 | ✅ | 输出 JSON，带原文证据 |
| 三种成品 | ✅ | a / b / c 三份 markdown |
| 断点续跑 | ✅ | 按内容哈希复用产物 |
| 托盘界面 | ✅ | 全英文，PySide6，后台线程执行 |
| 人声分离 | ⏳ | 视 BGM 实测结果决定是否需要 |
| 实时字幕 | ⏳ | 不在当前范围 |
