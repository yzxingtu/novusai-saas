"""
Token Estimation Utility / Token 估算工具

Uses more accurate estimation coefficients for CJK characters to avoid severe underestimation by len//4.
对 CJK 字符采用更准确的估算系数，避免 len//4 对中日韩文本严重低估。
"""


def _is_cjk(char: str) -> bool:
    """Check if character is a CJK unified ideograph / 判断字符是否为 CJK 统一表意文字"""
    cp = ord(char)
    # CJK Unified Ideographs: U+4E00 - U+9FFF / CJK 统一表意文字
    # CJK Extension A: U+3400 - U+4DBF / CJK 扩展 A
    # CJK Extension B+: U+20000 - U+2A6DF / CJK 扩展 B 及以后
    # CJK Compatibility: U+F900 - U+FAFF / CJK 兼容表意
    # Fullwidth forms: U+FF00 - U+FFEF / 全角形式
    # CJK Symbols: U+3000 - U+303F / CJK 符号与标点
    # Hiragana: U+3040 - U+309F / 平假名
    # Katakana: U+30A0 - U+30FF / 片假名
    # Hangul Syllables: U+AC00 - U+D7AF / 韩文音节
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
    Estimate token count for text.
    估算文本的 token 数量。

    Rules / 规则:
    - ASCII characters: ~1 token per 4 chars / ASCII 字符: 每 4 字符 ≈ 1 token
    - CJK characters: ~1 token per 1.5 chars / CJK 字符: 每 1.5 字符 ≈ 1 token
    - Other Unicode: ~1 token per 2 chars / 其他 Unicode: 每 2 字符 ≈ 1 token

    Args:
        text: Text to estimate / 待估算文本

    Returns:
        Estimated token count (minimum 0) / 估算 token 数（至少为 0）
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
