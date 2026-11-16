# 流水线与产物

## 一次任务的目录

```
D:\Local Repositories\MultiVoice-Summary-Suit\
├─ work\<时间戳>-<内容哈希>\
│  ├─ audio.wav                 16 kHz 单声道提取结果
│  ├─ segments.raw.json         ASR 原始分段（含内部时间戳）
│  ├─ segments.corrected.json   纠错后分段
│  ├─ transcript.txt            纯文本（无时间线）
│  ├─ units.json                信息单元
│  └─ manifest.json             任务元信息
└─ output\<同一 job 名>\
   ├─ a-script.md               干净口播稿
   ├─ b-report.md               知识点报告
   └─ c-brief.md                简要快报
```

## 阶段开关

```powershell
# 只做识别，先看质量
python -m multivoice run --input "D:\media\a.mp3" --stages asr

# 识别 + 纠错
python -m multivoice run --input "D:\media\a.mp3" --stages asr,correct

# 全流程
python -m multivoice run --input "D:\media\a.mp3"
```

## 当前实现状态

| 阶段 | 状态 | 说明 |
|---|---|---|
| 音轨提取 | ✅ | ffmpeg，16 kHz 单声道 |
| ASR | ✅ | qwen3 / whisper 两个适配器，模型路径由配置决定 |
| 纠错 | ✅ | 逐段调用，只改错不改写 |
| 信息单元抽取 | ✅ | 输出 JSON，带原文证据 |
| 三种成品 | ✅ | a / b / c 三份 markdown |
| 语种识别 | ✅ | 由 ASR 引擎返回 |
| VAD 切片 | ⏳ | 当前整段送入，长音频需后续补 |
| 人声分离 | ⏳ | 重 BGM 时启用 |
| 双语对照 | ⏳ | 待接翻译与段落对齐 |
