"""Regex-free text semantics helpers for AI runtime flows."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any
from urllib.parse import parse_qs, urlparse

_MODEL_FC_BLOCK_START = "<｜DSML｜function_calls>"
_MODEL_FC_BLOCK_END = "</｜DSML｜function_calls>"
_MODEL_FC_TAG_PREFIXES = ("<｜", "</｜")

_TRAILING_REPLY_PUNCTUATION = frozenset({"!", ".", "?", "！", "。", "？", "…"})
_CONFIRMATION_REPLIES = frozenset(
    {
        "确认执行",
        "确认",
        "执行",
        "好的",
        "好",
        "好吧",
        "是",
        "是的",
        "是吧",
        "可以",
        "行",
        "嗯",
        "没问题",
        "妥了",
        "confirm",
        "yes",
        "ok",
        "okay",
        "sure",
        "yep",
        "yeah",
        "go ahead",
        "proceed",
    }
)
_REJECTION_REPLIES = frozenset(
    {
        "取消",
        "拒绝",
        "不执行",
        "不要",
        "不要了",
        "不",
        "算了",
        "别",
        "甭",
        "cancel",
        "no",
        "reject",
        "abort",
        "stop",
        "nope",
    }
)
_QUESTION_INDICATORS = (
    "为什么",
    "怎么样",
    "怎么办",
    "怎么回事",
    "怎么",
    "如何",
    "啥",
    "哪个",
    "哪样",
    "哪里",
    "哪些",
    "哪种",
    "是不是",
    "对吗",
    "对不对",
    "咋样",
    "咋办",
    "咋",
    "几个",
    "几点",
    "几号",
    "几时",
    "多少",
    "多大",
    "多长",
    "多久",
)
_CAPABILITY_DENIAL_TERMS = (
    "无法",
    "不能",
    "不可以",
    "做不到",
    "没法",
    "没有",
    "没有权限",
    "不具备",
    "缺少权限",
    "只读",
    "read only",
    "readonly",
    "lacking",
    "lack",
    "can't",
    "cannot",
    "unable",
    "no access",
    "not able",
    "don't have",
    "do not have",
    "doesn't have",
)
_TOOL_PLANNING_LEAK_TERMS = (
    "to fulfill the user's request",
    "to fulfill the users request",
    "according to workflow",
    "first call ",
    "calling ",
    "invoking ",
    "invoke ",
    "正在调用",
    "调用 ",
    "then ",
)
_FORBID_INSTRUCTION_TERMS = (
    "不要",
    "别",
    "不用",
    "无需",
    "勿",
    "甭",
    "dont",
    "don't",
    "do not",
    "without",
    "no need",
)
_WEATHER_TERMS = (
    "天气",
    "气温",
    "温度",
    "气候",
    "降雨",
    "湿度",
    "weather",
    "temperature",
)
_RAIL_TICKET_TERMS = (
    "高铁票",
    "动车票",
    "火车票",
    "车票",
    "12306",
    "列车票",
    "高铁",
)
_PAGE_SUMMARY_TERMS = (
    "本页面",
    "当前页面",
    "页面里有什么",
    "页面上有什么",
    "页面都有什么",
    "阅读页面",
    "读一下页面",
    "看看页面",
    "页面有什么内容",
)
_PAGE_DETAIL_OPERATION_TERMS = (
    "创建",
    "新增",
    "添加",
    "编辑",
    "修改",
    "删除",
    "提交",
    "填写",
    "表单",
    "搜索",
    "筛选",
    "刷新",
    "截图",
    "截屏",
    "可见行",
    "可见记录",
    "列表明细",
    "表格明细",
    "read_current_view",
    "read_visible_rows",
    "create_record",
    "fill_form",
    "submit_form",
    "get_form_",
    "pageop_",
    "invoke_page_operation",
)
_WEB_SEARCH_PREFIXES = ("search results for:",)
_FETCH_URL_PREFIXES = ("content from http://", "content from https://")


def collapse_whitespace(text: str | None) -> str:
    return " ".join((text or "").split())


def normalize_match_text(text: str | None) -> str:
    return collapse_whitespace(text).strip().lower()


def contains_any_phrase(text: str | None, phrases: Iterable[str]) -> bool:
    normalized = normalize_match_text(text)
    return any(str(phrase or "").lower() in normalized for phrase in phrases if phrase)


def strip_trailing_reply_punctuation(text: str | None) -> str:
    normalized = collapse_whitespace(text).strip()
    while normalized and normalized[-1] in _TRAILING_REPLY_PUNCTUATION:
        normalized = normalized[:-1].rstrip()
    return normalized


def is_confirmation_reply(text: str | None) -> bool:
    normalized = normalize_match_text(strip_trailing_reply_punctuation(text))
    return bool(normalized and normalized in _CONFIRMATION_REPLIES)


def is_rejection_reply(text: str | None) -> bool:
    normalized = normalize_match_text(strip_trailing_reply_punctuation(text))
    return bool(normalized and normalized in _REJECTION_REPLIES)


def has_question_indicator(text: str | None) -> bool:
    return contains_any_phrase(text, _QUESTION_INDICATORS)


def has_capability_denial_phrase(text: str | None) -> bool:
    return contains_any_phrase(text, _CAPABILITY_DENIAL_TERMS)


def has_tool_planning_leak_phrase(text: str | None) -> bool:
    return contains_any_phrase(text, _TOOL_PLANNING_LEAK_TERMS)


def has_forbid_instruction_phrase(text: str | None) -> bool:
    return contains_any_phrase(text, _FORBID_INSTRUCTION_TERMS)


def mentions_weather(text: str | None) -> bool:
    return contains_any_phrase(text, _WEATHER_TERMS)


def mentions_rail_ticket(text: str | None) -> bool:
    return contains_any_phrase(text, _RAIL_TICKET_TERMS)


def mentions_page_summary(text: str | None) -> bool:
    return contains_any_phrase(text, _PAGE_SUMMARY_TERMS)


def mentions_page_detail_operation(text: str | None) -> bool:
    return contains_any_phrase(text, _PAGE_DETAIL_OPERATION_TERMS)


def strip_model_function_call_markup(text: str | None) -> str:
    raw = text or ""
    if "｜" not in raw:
        return raw

    cleaned = raw
    while True:
        start = cleaned.find(_MODEL_FC_BLOCK_START)
        if start < 0:
            break
        end = cleaned.find(_MODEL_FC_BLOCK_END, start + len(_MODEL_FC_BLOCK_START))
        if end < 0:
            cleaned = cleaned[:start]
            break
        cleaned = cleaned[:start] + cleaned[end + len(_MODEL_FC_BLOCK_END) :]

    result: list[str] = []
    idx = 0
    length = len(cleaned)
    while idx < length:
        if cleaned.startswith(_MODEL_FC_TAG_PREFIXES[0], idx) or cleaned.startswith(
            _MODEL_FC_TAG_PREFIXES[1],
            idx,
        ):
            close = cleaned.find(">", idx)
            if close < 0:
                break
            idx = close + 1
            continue
        result.append(cleaned[idx])
        idx += 1
    return "".join(result)


def remove_trailing_json_commas(text: str) -> str:
    chars = list(text)
    result: list[str] = []
    in_string = False
    escape_next = False
    length = len(chars)
    idx = 0
    while idx < length:
        ch = chars[idx]
        if in_string:
            result.append(ch)
            if escape_next:
                escape_next = False
            elif ch == "\\":
                escape_next = True
            elif ch == '"':
                in_string = False
            idx += 1
            continue

        if ch == '"':
            in_string = True
            result.append(ch)
            idx += 1
            continue

        if ch == ",":
            look_ahead = idx + 1
            while look_ahead < length and chars[look_ahead] in {" ", "\t", "\r", "\n"}:
                look_ahead += 1
            if look_ahead < length and chars[look_ahead] in {"}", "]"}:
                idx += 1
                continue

        result.append(ch)
        idx += 1
    return "".join(result)


def extract_textual_tool_call_names(
    text: str | None,
    *,
    alias_to_tool_name: dict[str, str],
    known_tool_names: set[str] | None = None,
) -> list[str]:
    normalized = collapse_whitespace(text)
    lowered = normalized.lower()
    if not lowered:
        return []

    matched: list[str] = []

    def _append(candidate: str) -> None:
        actual = alias_to_tool_name.get(candidate, candidate)
        if (
            actual
            and (known_tool_names is None or actual in known_tool_names)
            and actual not in matched
        ):
            matched.append(actual)

    for alias, actual in alias_to_tool_name.items():
        alias_key = normalize_match_text(alias)
        if not alias_key:
            continue
        markers = (
            f"functions.{alias_key}",
            f"{alias_key}(",
            f"call {alias_key}",
            f"calling {alias_key}",
            f"invoking {alias_key}",
            f"invoke {alias_key}",
            f"正在调用{alias_key}",
            f"正在调用 {alias_key}",
            f"调用{alias_key}",
            f"调用 {alias_key}",
            f"then {alias_key}",
            f"next {alias_key}",
        )
        if any(marker in lowered for marker in markers):
            _append(actual)

    if any(lowered.startswith(prefix) for prefix in _WEB_SEARCH_PREFIXES):
        _append("web_search")
    if any(lowered.startswith(prefix) for prefix in _FETCH_URL_PREFIXES):
        _append("fetch_url")
    if "candidate url" in lowered and "fetch_url" in lowered:
        _append("fetch_url")

    return matched


def extract_fenced_json_block(text: str | None) -> str | None:
    raw = text or ""
    start = 0
    while True:
        fence = raw.find("```", start)
        if fence < 0:
            return None
        header_end = raw.find("\n", fence + 3)
        if header_end < 0:
            return None
        header = raw[fence + 3 : header_end].strip().lower()
        if header in {"", "json"}:
            close = raw.find("```", header_end + 1)
            if close < 0:
                return None
            return raw[header_end + 1 : close].strip()
        start = header_end + 1


def extract_first_json_object(text: str | None) -> dict[str, Any] | None:
    raw = text or ""
    for candidate in iter_json_objects(raw):
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def extract_first_json_array(text: str | None) -> list[Any] | None:
    raw = text or ""
    for candidate in iter_json_arrays(raw):
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        if isinstance(parsed, list):
            return parsed
    return None


def extract_first_json_object_with_key(
    text: str | None,
    required_key: str,
) -> dict[str, Any] | None:
    raw = text or ""
    for candidate in iter_json_objects(raw):
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        if isinstance(parsed, dict) and required_key in parsed:
            return parsed
    return None


def iter_json_objects(text: str | None) -> list[str]:
    raw = text or ""
    results: list[str] = []
    start: int | None = None
    depth = 0
    in_string = False
    escape_next = False

    for idx, ch in enumerate(raw):
        if in_string:
            if escape_next:
                escape_next = False
            elif ch == "\\":
                escape_next = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
            continue

        if ch == "{":
            if depth == 0:
                start = idx
            depth += 1
            continue

        if ch == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start is not None:
                results.append(raw[start : idx + 1])
                start = None

    return results


def iter_json_arrays(text: str | None) -> list[str]:
    raw = text or ""
    results: list[str] = []
    start: int | None = None
    depth = 0
    in_string = False
    escape_next = False

    for idx, ch in enumerate(raw):
        if in_string:
            if escape_next:
                escape_next = False
            elif ch == "\\":
                escape_next = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
            continue

        if ch == "[":
            if depth == 0:
                start = idx
            depth += 1
            continue

        if ch == "]" and depth > 0:
            depth -= 1
            if depth == 0 and start is not None:
                results.append(raw[start : idx + 1])
                start = None

    return results


def extract_named_field_value(
    text: str | None,
    field_name: str,
) -> str | None:
    target = normalize_match_text(field_name)
    if not target:
        return None
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        for separator in (":", "："):
            if separator not in stripped:
                continue
            head, tail = stripped.split(separator, 1)
            if normalize_match_text(head) == target:
                value = tail.strip()
                if value:
                    return value
    return None


def extract_public_attachment_reference(
    raw: str | None,
) -> tuple[int | None, str | None]:
    text = str(raw or "").strip()
    if not text:
        return None, None

    parsed = urlparse(
        text
        if "://" in text
        else f"http://_ignored{text if text.startswith('/') else '/' + text}"
    )
    parts = [part for part in (parsed.path or "").split("/") if part]
    if len(parts) < 4:
        return None, None
    if parts[0:3] != ["api", "public", "attachments"]:
        return None, None

    attachment_id = safe_positive_int(parts[3])
    if attachment_id is None:
        return None, None

    access_kind = parts[4].lower() if len(parts) > 4 else ""
    if access_kind not in {"access", "image"}:
        return None, None

    token_values = parse_qs(parsed.query or "").get("token") or []
    token = str(token_values[0]).strip() if token_values else None
    return attachment_id, token or None


def safe_positive_int(raw: Any) -> int | None:
    if isinstance(raw, int):
        return raw if raw > 0 else None
    text = str(raw or "").strip()
    if not text or not text.isdigit():
        return None
    value = int(text)
    return value if value > 0 else None


def slugify_ascii_identifier(
    text: str | None,
    *,
    lowercase: bool = True,
    max_length: int | None = None,
) -> str:
    source = str(text or "").strip()
    if lowercase:
        source = source.lower()

    pieces: list[str] = []
    last_was_sep = False
    for ch in source:
        if (
            ("a" <= ch <= "z")
            or ("0" <= ch <= "9")
            or (not lowercase and ("A" <= ch <= "Z"))
        ):
            pieces.append(ch)
            last_was_sep = False
            continue
        if ch == "_" or ch == "-":
            if pieces and not last_was_sep:
                pieces.append("_")
                last_was_sep = True
            continue
        if pieces and not last_was_sep:
            pieces.append("_")
            last_was_sep = True

    result = "".join(pieces).strip("_")
    if max_length is not None and max_length > 0:
        return result[:max_length]
    return result


def split_on_any_delimiter(text: str | None, delimiters: str) -> list[str]:
    if not text:
        return []
    parts: list[str] = []
    current: list[str] = []
    delimiter_set = set(delimiters)
    for ch in str(text):
        if ch in delimiter_set:
            if current:
                parts.append("".join(current))
                current = []
            continue
        current.append(ch)
    if current:
        parts.append("".join(current))
    return parts


def split_mixed_alnum_tokens(text: str | None) -> list[str]:
    raw = str(text or "")
    tokens: list[str] = []
    current: list[str] = []
    current_kind: str | None = None

    def _flush() -> None:
        nonlocal current, current_kind
        if current:
            tokens.append("".join(current))
        current = []
        current_kind = None

    for ch in raw:
        if "0" <= ch <= "9":
            kind = "digit"
        elif ("a" <= ch <= "z") or ("A" <= ch <= "Z"):
            kind = "alpha"
        else:
            _flush()
            continue
        if current_kind is None or current_kind == kind:
            current.append(ch)
            current_kind = kind
            continue
        _flush()
        current.append(ch)
        current_kind = kind

    _flush()
    return tokens


def split_on_blank_lines(text: str | None) -> list[str]:
    raw = str(text or "")
    blocks: list[str] = []
    current: list[str] = []
    for line in raw.splitlines():
        if line.strip():
            current.append(line)
            continue
        if current:
            blocks.append("\n".join(current))
            current = []
    if current:
        blocks.append("\n".join(current))
    return blocks


def split_sentences_by_terminal_punctuation(text: str | None) -> list[str]:
    raw = str(text or "")
    if not raw:
        return []

    sentences: list[str] = []
    current: list[str] = []
    terminal = {"。", "！", "？", ".", "!", "?"}
    length = len(raw)

    for idx, ch in enumerate(raw):
        current.append(ch)
        if ch not in terminal:
            continue
        next_char = raw[idx + 1] if idx + 1 < length else ""
        if next_char and not next_char.isspace() and next_char not in terminal:
            continue
        sentence = "".join(current).strip()
        if sentence:
            sentences.append(sentence)
        current = []

    tail = "".join(current).strip()
    if tail:
        sentences.append(tail)
    return sentences


def parse_markdown_heading(line: str | None) -> tuple[int, str] | None:
    raw = str(line or "")
    idx = 0
    length = len(raw)
    while idx < length and raw[idx] == "#":
        idx += 1
    if idx == 0 or idx > 6:
        return None
    if idx >= length or not raw[idx].isspace():
        return None
    heading = raw[idx:].strip()
    if not heading:
        return None
    return idx, heading


def build_semver_sort_key(version: str | None) -> tuple[tuple[int, int | str], ...]:
    normalized = str(version or "").strip()
    if not normalized:
        return ()
    if normalized.startswith(("v", "V")):
        normalized = normalized[1:]

    key: list[tuple[int, int | str]] = []
    for part in split_on_any_delimiter(normalized, ".+-"):
        for token in split_mixed_alnum_tokens(part):
            if token.isdigit():
                key.append((0, int(token)))
            else:
                key.append((1, token.lower()))
    return tuple(key)


def extract_cjk_bigram_and_word_tokens(
    text: str | None,
    *,
    stopwords: set[str] | frozenset[str] | None = None,
) -> set[str]:
    raw = str(text or "")
    blocked = stopwords or set()
    tokens: set[str] = set()

    def _append(token: str) -> None:
        normalized = token.lower()
        if normalized and normalized not in blocked:
            tokens.add(normalized)

    idx = 0
    length = len(raw)
    while idx < length:
        ch = raw[idx]
        code = ord(ch)
        if 0x4E00 <= code <= 0x9FFF:
            start = idx
            while idx < length and 0x4E00 <= ord(raw[idx]) <= 0x9FFF:
                idx += 1
            segment = raw[start:idx]
            for seg_idx, seg_ch in enumerate(segment):
                if seg_ch not in blocked:
                    tokens.add(seg_ch)
                if seg_idx < len(segment) - 1:
                    bigram = segment[seg_idx : seg_idx + 2]
                    if bigram not in blocked:
                        tokens.add(bigram)
            continue

        if ("a" <= ch <= "z") or ("A" <= ch <= "Z"):
            start = idx
            idx += 1
            while idx < length and (
                ("a" <= raw[idx] <= "z") or ("A" <= raw[idx] <= "Z")
            ):
                idx += 1
            token = raw[start:idx]
            if len(token) >= 2:
                _append(token)
            continue

        idx += 1

    return tokens


def extract_memory_keywords(text: str | None, *, limit: int = 12) -> list[str]:
    normalized = collapse_whitespace(text).lower()
    if not normalized:
        return []

    seen: set[str] = set()
    keywords: list[str] = []
    length = len(normalized)
    idx = 0
    while idx < length and len(keywords) < limit:
        ch = normalized[idx]
        code = ord(ch)
        if 0x4E00 <= code <= 0x9FFF:
            start = idx
            while idx < length and 0x4E00 <= ord(normalized[idx]) <= 0x9FFF:
                idx += 1
            token = normalized[start:idx]
            if len(token) >= 2 and token not in seen:
                seen.add(token)
                keywords.append(token)
            continue

        if ("a" <= ch <= "z") or ("0" <= ch <= "9"):
            start = idx
            idx += 1
            while idx < length:
                nxt = normalized[idx]
                if ("a" <= nxt <= "z") or ("0" <= nxt <= "9") or nxt in {"_", "-"}:
                    idx += 1
                    continue
                break
            token = normalized[start:idx]
            if len(token) >= 2 and token not in seen:
                seen.add(token)
                keywords.append(token[:32])
            continue

        idx += 1

    return keywords


def parse_index_score_pair(line: str | None) -> tuple[int, float] | None:
    cleaned = str(line or "").strip()
    if not cleaned:
        return None
    while cleaned and cleaned[0] in {"[", "("}:
        cleaned = cleaned[1:].lstrip()
    index_chars: list[str] = []
    position = 0
    while position < len(cleaned) and cleaned[position].isdigit():
        index_chars.append(cleaned[position])
        position += 1
    if not index_chars:
        return None
    while position < len(cleaned) and cleaned[position] in {"]", ")", " ", "\t"}:
        position += 1
    if position >= len(cleaned) or cleaned[position] not in {":", "="}:
        return None
    position += 1
    while position < len(cleaned) and cleaned[position] in {" ", "\t"}:
        position += 1
    score_chars: list[str] = []
    dot_used = False
    while position < len(cleaned):
        ch = cleaned[position]
        if ch.isdigit():
            score_chars.append(ch)
        elif ch == "." and not dot_used:
            score_chars.append(ch)
            dot_used = True
        else:
            break
        position += 1
    if not score_chars:
        return None
    return int("".join(index_chars)), float("".join(score_chars))


def extract_data_url_payload(
    url: str | None,
    *,
    media_prefix: str,
) -> str | None:
    raw = str(url or "").strip()
    prefix = f"data:{media_prefix}/"
    if not raw.startswith(prefix):
        return None
    comma_idx = raw.find(",")
    if comma_idx < 0:
        return None
    metadata = raw[len("data:") : comma_idx].lower()
    if ";base64" not in metadata:
        return None
    return raw[comma_idx + 1 :]


def split_last_suffix(
    text: str | None,
    *,
    separator: str = "-",
    allowed_suffixes: Iterable[str],
) -> tuple[str, str | None]:
    raw = str(text or "").strip()
    if not raw:
        return "", None
    suffixes = {str(item).strip().lower() for item in allowed_suffixes if item}
    head, sep, tail = raw.rpartition(separator)
    if not sep or tail.lower() not in suffixes:
        return raw, None
    return head, tail.lower()


def extract_double_brace_placeholders(text: str | None) -> list[str]:
    raw = str(text or "")
    placeholders: list[str] = []
    seen: set[str] = set()
    idx = 0
    length = len(raw)

    while idx < length:
        start = raw.find("{{", idx)
        if start < 0:
            break
        end = raw.find("}}", start + 2)
        if end < 0:
            break
        name = raw[start + 2 : end].strip()
        if name and all(ch.isalnum() or ch == "_" for ch in name) and name not in seen:
            seen.add(name)
            placeholders.append(name)
        idx = end + 2

    return placeholders


def extract_braced_identifiers(
    text: str | None,
    *,
    opening: str = "{",
    closing: str = "}",
) -> list[str]:
    raw = str(text or "")
    identifiers: list[str] = []
    seen: set[str] = set()
    idx = 0
    length = len(raw)

    while idx < length:
        start = raw.find(opening, idx)
        if start < 0:
            break
        end = raw.find(closing, start + len(opening))
        if end < 0:
            break
        name = raw[start + len(opening) : end].strip()
        if name and all(ch.isalnum() or ch == "_" for ch in name) and name not in seen:
            seen.add(name)
            identifiers.append(name)
        idx = end + len(closing)

    return identifiers
