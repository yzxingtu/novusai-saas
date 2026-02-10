"""
Token 估算工具

对 CJK 字符采用更准确的估算系数，避免 len//4 对中日韩文本严重低估。
"""


def _is_cjk(char: str) -> bool:
    """判断字符是否为 CJK 统一表意文字"""
    cp = ord(char)
    # CJK Unified Ideographs: U+4E00 - U+9FFF
    # CJK Extension A: U+3400 - U+4DBF
    # CJK Extension B+: U+20000 - U+2A6DF
    # CJK Compatibility: U+F900 - U+FAFF
    # Fullwidth forms: U+FF00 - U+FFEF
    # CJK Symbols: U+3000 - U+303F
    # Hiragana: U+3040 - U+309F
    # Katakana: U+30A0 - U+30FF
    # Hangul Syllables: U+AC00 - U+D7AF
    return (
        0x4E00 <= cp <= 0x9FFF
        or 0x3400 <= cp <= 0x4DBF
        or 0x20000 <= cp <= 0x2A6DF
        or 0xF900 <= cp <= 0xFAFF
        or 0xFF00 <= cp <= 0xFFEF
        or 0x3000 <= cp <= 0x303F
        or 0x3040 <= cp <= 0x309F
        or 0x30A0 <= cp <= 0x30FF
        or 0xAC00 <= cp <= 0xD7AF
    )


def estimate_tokens(text: str) -> int:
    """
    估算文本的 token 数量

    规则:
    - ASCII 字符: 每 4 字符 ≈ 1 token
    - CJK 字符: 每 1.5 字符 ≈ 1 token（即 1 个 CJK 字约 0.67 token）
    - 其他 Unicode: 每 2 字符 ≈ 1 token

    Args:
        text: 待估算文本

    Returns:
        估算 token 数（至少为 0）
    """
    if not text:
        return 0

    ascii_count = 0
    cjk_count = 0
    other_count = 0

    for ch in text:
        if ch.isascii():
            ascii_count += 1
        elif _is_cjk(ch):
            cjk_count += 1
        else:
            other_count += 1

    tokens = ascii_count / 4 + cjk_count / 1.5 + other_count / 2
    return max(int(tokens), 1) if text else 0


__all__ = ["estimate_tokens"]
