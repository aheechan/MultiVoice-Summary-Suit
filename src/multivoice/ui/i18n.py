"""Minimal bilingual strings for the desktop UI (English default)."""
from __future__ import annotations

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "app_name": "MultiVoice Summary Suit",
        "subtitle": "Speech → transcript → spoken script, report and brief",
        "transcribe": "Transcribe file…",
        "gen_a": "Clean spoken script",
        "gen_a_desc": "Readable first-person draft, filler removed",
        "gen_b": "Knowledge report",
        "gen_b_desc": "Every point explained: what / why / how / limits",
        "gen_c": "Brief",
        "gen_c_desc": "300–600 word summary with key points",
        "gen_hint": "Transcribe a file first, then choose an output.",
        "review": "Review pending terms ({n})",
        "open_output": "Open output folder",
        "settings": "Settings…",
        "about": "About",
        "quit": "Quit",
        "panel": "Open panel",
        "status_idle": "Idle",
        "status_working": "Working: {name}",
        "status_transcript": "Transcript ready",
        "status_outputs": "Outputs ready",
        "status_failed": "Failed",
        "language": "中文",
        "export": "Export knowledge base…",
        "auto_research": "Research unknown terms on the web",
        "auto_discover": "Search for new terms every day",
        "max_lookups": "Max lookups per job",
        "provider": "Model provider",
        "save": "Save",
        "cancel": "Cancel",
        "close": "Close",
        "review_title": "Pending terms",
        "review_hint": "Found online but not confirmed. Research again or drop them.",
        "research_selected": "Research selected",
        "drop_selected": "Drop selected",
        "nothing_pending": "Nothing to review.",
        "export_done": "Exported {count} entries to:\n{path}",
        "settings_saved": "Settings saved. They apply to the next job.",
        "working_alert": "A job is already running.",
        "started": "Started: {name}",
        "transcript_ready_msg": "Transcript ready. Review it, then generate an output.",
        "outputs_ready": "Output ready: {kind}",
        "failed_msg": "Job failed:\n{message}",
        "about_text": (
            "{name} {version}\n\n"
            "Turns multilingual speech into clean transcripts,\n"
            "knowledge reports and short briefs.\n\n"
            "Workflow: transcribe → review the bilingual transcript → generate outputs."
        ),
        "tray_hint": "Running in the system tray. Double-click the icon to open the panel.",
    },
    "zh": {
        "app_name": "MultiVoice Summary Suit",
        "subtitle": "语音 → 文稿 → 口播稿、知识报告与快报",
        "transcribe": "转写文件…",
        "gen_a": "干净口播稿",
        "gen_a_desc": "可直接朗读的第一人称稿，去掉口癖与废话",
        "gen_b": "知识点报告",
        "gen_b_desc": "逐点讲解：是什么 / 为什么 / 怎么做 / 边界",
        "gen_c": "简要快报",
        "gen_c_desc": "300–600 字摘要，附要点清单",
        "gen_hint": "先转写，再选择输出类型。",
        "review": "审查待定词条（{n}）",
        "open_output": "打开输出目录",
        "settings": "设置…",
        "about": "关于",
        "quit": "退出",
        "panel": "打开主界面",
        "status_idle": "空闲",
        "status_working": "正在处理：{name}",
        "status_transcript": "文稿已就绪",
        "status_outputs": "成品已生成",
        "status_failed": "失败",
        "language": "EN",
        "export": "导出知识库…",
        "auto_research": "自动联网核实新词",
        "auto_discover": "每天自动搜索新词",
        "max_lookups": "单次任务检索上限",
        "provider": "模型来源",
        "save": "保存",
        "cancel": "取消",
        "close": "关闭",
        "review_title": "待定词条",
        "review_hint": "这些词搜到过但未确认。可以再查一次，或直接丢弃。",
        "research_selected": "重新检索所选",
        "drop_selected": "丢弃所选",
        "nothing_pending": "没有待审查的词条。",
        "export_done": "已导出 {count} 条到：\n{path}",
        "settings_saved": "设置已保存，下一个任务生效。",
        "working_alert": "已有任务在运行。",
        "started": "开始处理：{name}",
        "transcript_ready_msg": "文稿已就绪，核对后生成成品。",
        "outputs_ready": "已生成：{kind}",
        "failed_msg": "任务失败：\n{message}",
        "about_text": (
            "{name} {version}\n\n"
            "把多语言语音整理成文稿、知识报告与快报。\n\n"
            "流程：转写 → 核对双语稿 → 生成成品。"
        ),
        "tray_hint": "程序常驻托盘。双击图标打开主界面。",
    },
}

_lang = "en"


def set_language(lang: str) -> None:
    global _lang
    _lang = lang if lang in STRINGS else "en"


def language() -> str:
    return _lang


def t(key: str, **fmt) -> str:
    table = STRINGS.get(_lang, STRINGS["en"])
    text = table.get(key) or STRINGS["en"].get(key, key)
    return text.format(**fmt) if fmt else text
