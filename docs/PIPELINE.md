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

## 当前实现状态

| 阶段 | 状态 | 说明 |
|---|---|---|
| 音轨提取 | ✅ | ffmpeg，16 kHz 单声道 |
| ASR | ✅ | qwen3 / whisper 两个适配器，模型路径由配置决定 |
| 纠错 | ✅ | 逐段调用，只改错不改写 |
| 双语翻译 | ✅ | 段落级，源语言自动判断 |
| 信息单元抽取 | ✅ | 输出 JSON，带原文证据 |
| 三种成品 | ✅ | a / b / c 三份 markdown |
| 断点续跑 | ✅ | 按内容哈希复用产物 |
| VAD 切片 | ⏳ | 当前整段送入，长音频需后续补 |
| 人声分离 | ⏳ | 重 BGM 时启用 |
| 实时字幕 | ⏳ | 不在当前范围 |
