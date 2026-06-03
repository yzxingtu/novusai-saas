"""
Embedding Text Cleaner / Embedding 文本清洗器

Pre-processes text before sending to embedding model, removing noise irrelevant to semantic retrieval:
在文本送入 Embedding 模型前进行预处理，去除对语义检索无意义的噪声：
- URL/links: replace with placeholder, preserving "has link" semantic signal
  URL/链接：替换为占位符，保留“有链接”的语义信号
- Bracket emojis: [玫瑰][大爱] → remove
  中括号表情：[玫瑰][大爱] → 移除
- Unicode emoji: 😊🌹 → remove
  Unicode 表情：😊🌹 → 移除
- Excessive whitespace/newlines: compress to single
  多余空白/换行：压缩为单个

Note: Cleaning is only for embedding vector generation, does not affect stored original chunk content.
注意：清洗仅用于 embedding 向量生成，不影响存储的原始 chunk 内容。
"""

from __future__ import annotations

_URL_PREFIXES = ("http://", "https://", "ftp://", "www.")
_URL_STOP_CHARS = frozenset({" ", "\t", "\n", "\r", "<", ">", '"', "'"})
_URL_TRAILING_PUNCTUATION = frozenset({"]", ")", ".", ",", ";", "!", "?"})

# IM platform bracket emoji whitelist (PDD/WeChat/Taobao common emoji tags)
# IM 平台中括号表情白名单（拼多多/微信/淘宝常见表情标签）
_KNOWN_BRACKET_EMOJIS = {
    "玫瑰",
    "大爱",
    "微笑",
    "偷笑",
    "大笑",
    "害羞",
    "流泪",
    "难过",
    "惊讶",
    "抓狂",
    "发怒",
    "得意",
    "调皮",
    "呲牙",
    "色色",
    "亲亲",
    "白眼",
    "奋斗",
    "鼓掌",
    "拥抱",
    "强壮",
    "胜利",
    "抱拳",
    "握手",
    "啤酒",
    "咖啡",
    "蛋糕",
    "礼物",
    "爱心",
    "心碎",
    "太阳",
    "月亮",
    "彩虹",
    "闪电",
    "火焰",
    "雪花",
    "星星",
    "庆祝",
    "红包",
    "发财",
    "福到",
    "恭喜",
    "比心",
    "OK",
    "加油",
    "赞",
    "踩",
}

_SYSTEM_TAG_EXACT = {"自动回复", "快捷回复", "系统消息", "已读", "未读", "商品推荐"}


def _strip_bracket_emojis(text: str) -> str:
    """Remove known IM emoji tags and system operation tags / 移除已知 IM 表情标签和系统操作标签"""
    pieces: list[str] = []
    index = 0
    while index < len(text):
        if text[index] != "[":
            pieces.append(text[index])
            index += 1
            continue
        closing = text.find("]", index + 1)
        if closing < 0:
            pieces.append(text[index])
            index += 1
            continue
        content = text[index + 1 : closing]
        if content in _KNOWN_BRACKET_EMOJIS or _is_system_operation_tag(content):
            index = closing + 1
            continue
        pieces.append(text[index : closing + 1])
        index = closing + 1
    return "".join(pieces)


def _collapse_spaces(text: str) -> str:
    """Replace consecutive spaces/tabs with a single space / 将连续空格/制表符合并为一个空格"""
    buffer: list[str] = []
    prev_space = False
    for ch in text:
        if ch in {" ", "\t"}:
            if not prev_space:
                buffer.append(" ")
            prev_space = True
            continue
        buffer.append(ch)
        prev_space = False
    return "".join(buffer)


def _compress_newlines(text: str) -> str:
    """Collapse long newline runs (>=3) to two newline characters / 将 3+ 个换行压缩为两个"""
    buffer: list[str] = []
    newline_count = 0
    for ch in text:
        if ch == "\n":
            newline_count += 1
            continue
        if newline_count:
            if newline_count >= 3:
                buffer.append("\n\n")
            else:
                buffer.append("\n" * newline_count)
            newline_count = 0
        buffer.append(ch)
    if newline_count:
        if newline_count >= 3:
            buffer.append("\n\n")
        else:
            buffer.append("\n" * newline_count)
    return "".join(buffer)


def _strip_urls(text: str) -> str:
    pieces: list[str] = []
    index = 0
    length = len(text)
    while index < length:
        if not _looks_like_url_at(text, index):
            pieces.append(text[index])
            index += 1
            continue
        end = index
        while end < length and text[end] not in _URL_STOP_CHARS:
            end += 1
        token = text[index:end]
        trimmed = token.rstrip("".join(_URL_TRAILING_PUNCTUATION))
        pieces.append(token[len(trimmed) :])
        index = end
    return "".join(pieces)


def _looks_like_url_at(text: str, index: int) -> bool:
    if index > 0 and not text[index - 1].isspace():
        return False
    return any(
        text[index : index + len(prefix)].lower() == prefix for prefix in _URL_PREFIXES
    )


def _is_system_operation_tag(content: str) -> bool:
    return (
        content in _SYSTEM_TAG_EXACT
        or content.startswith("常见问题")
        or content.startswith("当前用户来自")
    )


def _remove_unicode_emoji(text: str) -> str:
    return "".join(ch for ch in text if not _is_emoji_char(ch))


def _is_emoji_char(ch: str) -> bool:
    code = ord(ch)
    return (
        0x1F600 <= code <= 0x1F64F
        or 0x1F300 <= code <= 0x1F5FF
        or 0x1F680 <= code <= 0x1F6FF
        or 0x1F1E0 <= code <= 0x1F1FF
        or 0x2702 <= code <= 0x27B0
        or 0xFE00 <= code <= 0xFE0F
        or 0x1F900 <= code <= 0x1F9FF
        or 0x1FA00 <= code <= 0x1FA6F
        or 0x1FA70 <= code <= 0x1FAFF
        or 0x2600 <= code <= 0x26FF
        or code == 0x200D
        or 0x203C <= code <= 0x2FFF
    )


def clean_for_embedding(text: str) -> str:
    """
    Clean text to improve embedding vector quality.
    清洗文本以提升 Embedding 向量质量。

    Processing order / 处理顺序：
    1. URL → placeholder (preserve "has link" signal, remove random char noise)
    URL → 占位符（保留“有链接”的信号，去除随机字符噪声）
    2. Bracket emojis → remove
    中括号表情 → 移除
    3. Unicode emoji → remove
    Unicode 表情 → 移除
    4. Compress excess whitespace
    压缩多余空白

    Args:
        text: Raw text / 原始文本

    Returns:
        Cleaned text (for embedding, does not affect original storage)
        清洗后的文本（用于 embedding，不影响原始存储）
    """
    if not text:
        return text

    original = text

    # 1. URL → placeholder (preserve "has link" signal, remove random char noise)
    # URL → 占位符（保留“有链接”的信号，去除随机字符噪声）
    text = _strip_urls(text)

    # 2. Bracket emojis/tags → remove (whitelist + system tags)
    # 中括号表情/标签 → 移除（白名单 + 系统标签）
    text = _strip_bracket_emojis(text)

    # 3. Unicode emoji → remove / Unicode emoji → 移除
    text = _remove_unicode_emoji(text)

    # 4. Compress whitespace / 压缩空白
    text = _collapse_spaces(text)
    text = _compress_newlines(text)

    cleaned = text.strip()

    # Boundary protection: if cleaned text too short, fallback to original to avoid empty vectors
    # 边界保护：清洗后文本过短则回退到原始文本，避免空向量
    if len(cleaned) < 6:
        return original

    return cleaned


__all__ = ["clean_for_embedding"]
