"""
Embedding 文本清洗器

在文本送入 Embedding 模型前进行预处理，去除对语义检索无意义的噪声：
- URL/链接：替换为 [链接] 占位符，保留"有链接"的语义信号
- 中括号表情：[玫瑰][大爱][常见问题列表] → 移除或替换
- Unicode emoji：😊🌹 → 移除
- 多余空白/换行：压缩为单个

注意：清洗仅用于 embedding 向量生成，不影响存储的原始 chunk 内容。
"""

from __future__ import annotations

import re

# URL 正则（http/https/ftp + 裸域名）
_URL_PATTERN = re.compile(
    r"https?://[^\s<>\"\'\]\)]+|"
    r"ftp://[^\s<>\"\'\]\)]+|"
    r"www\.[^\s<>\"\'\]\)]+",
    re.IGNORECASE,
)

# IM 平台中括号表情白名单（拼多多/微信/淘宝常见表情标签）
_KNOWN_BRACKET_EMOJIS = {
    "玫瑰", "大爱", "微笑", "偷笑", "大笑", "害羞", "流泪", "难过",
    "惊讶", "抓狂", "发怒", "得意", "调皮", "呲牙", "色色", "亲亲",
    "白眼", "奋斗", "鼓掌", "拥抱", "强壮", "胜利", "抱拳", "握手",
    "啤酒", "咖啡", "蛋糕", "礼物", "爱心", "心碎", "太阳", "月亮",
    "彩虹", "闪电", "火焰", "雪花", "星星", "庆祝", "红包", "发财",
    "福到", "恭喜", "比心", "OK", "加油", "赞", "踩",
}

# 系统操作标签模式：[常见问题列表] [当前用户来自 xxx] [自动回复]
_SYSTEM_TAG_PATTERN = re.compile(
    r"\["
    r"(?:常见问题[列表]*|当前用户来自[^\]]*|自动回复|快捷回复|系统消息|已读|未读|商品推荐)"
    r"\]"
)


def _strip_bracket_emojis(text: str) -> str:
    """移除已知 IM 表情标签和系统操作标签"""
    # 1. 系统标签
    text = _SYSTEM_TAG_PATTERN.sub("", text)
    # 2. 白名单表情
    for emoji in _KNOWN_BRACKET_EMOJIS:
        text = text.replace(f"[{emoji}]", "")
    return text

# Unicode emoji 范围（Emoji_Presentation + Emoji_Modifier + 常见符号）
_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # Emoticons
    "\U0001F300-\U0001F5FF"  # Misc Symbols and Pictographs
    "\U0001F680-\U0001F6FF"  # Transport and Map
    "\U0001F1E0-\U0001F1FF"  # Flags
    "\U00002702-\U000027B0"  # Dingbats
    "\U0000FE00-\U0000FE0F"  # Variation Selectors
    "\U0001F900-\U0001F9FF"  # Supplemental Symbols
    "\U0001FA00-\U0001FA6F"  # Chess Symbols
    "\U0001FA70-\U0001FAFF"  # Symbols Extended-A
    "\U00002600-\U000026FF"  # Misc Symbols
    "\U0000200D"             # Zero Width Joiner
    "\U0000203C-\U00002FFF"  # Misc symbols (exclude CJK brackets 【】)
    "]+",
    re.UNICODE,
)

# 连续空白（含换行）压缩
_MULTI_WHITESPACE = re.compile(r"[ \t]+")
_MULTI_NEWLINE = re.compile(r"\n{3,}")


def clean_for_embedding(text: str) -> str:
    """
    清洗文本以提升 Embedding 向量质量。

    处理顺序：
    1. URL → [链接] 占位符
    2. 中括号表情 → 移除
    3. Unicode emoji → 移除
    4. 压缩多余空白

    Args:
        text: 原始文本

    Returns:
        清洗后的文本（用于 embedding，不影响原始存储）
    """
    if not text:
        return text

    original = text

    # 1. URL → 占位符（保留"有链接"的信号，去除随机字符噪声）
    text = _URL_PATTERN.sub("", text)

    # 2. 中括号表情/标签 → 移除（白名单 + 系统标签）
    text = _strip_bracket_emojis(text)

    # 3. Unicode emoji → 移除
    text = _EMOJI_PATTERN.sub("", text)

    # 4. 压缩空白
    text = _MULTI_WHITESPACE.sub(" ", text)
    text = _MULTI_NEWLINE.sub("\n\n", text)

    cleaned = text.strip()

    # 边界保护：清洗后文本过短则回退到原始文本，避免空向量
    if len(cleaned) < 6:
        return original

    return cleaned


__all__ = ["clean_for_embedding"]
