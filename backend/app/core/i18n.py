"""
国际化（i18n）模块

提供多语言支持，包括：
- 翻译文件加载与缓存
- 翻译函数 _()
- 语言上下文管理
"""

import json
import logging
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger("app.i18n")

# 当前请求的语言上下文
_current_locale: ContextVar[str] = ContextVar("current_locale", default="zh_CN")

# 支持的语言列表
SUPPORTED_LOCALES = ["zh_CN", "en"]
DEFAULT_LOCALE = "zh_CN"

# 翻译文件目录
LOCALES_DIR = Path(__file__).parent.parent / "locales"


def _deep_merge(base: dict, override: dict) -> dict:
    """深度合并字典"""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


# locale 名称映射：插件可能使用 zh-CN / en-US，需映射到后端的 zh_CN / en
_LOCALE_ALIASES: dict[str, list[str]] = {
    "zh_CN": ["zh-CN", "zh_CN", "zh"],
    "en": ["en-US", "en_US", "en"],
}


def _find_plugin_locale_file(plugin_locale_dir: Path, locale: str) -> Path | None:
    """在插件 locales 目录中查找匹配当前 locale 的翻译文件"""
    aliases = _LOCALE_ALIASES.get(locale, [locale])
    for alias in aliases:
        candidate = plugin_locale_dir / f"{alias}.json"
        if candidate.exists():
            return candidate
    return None


@lru_cache(maxsize=10)
def _load_translations(locale: str) -> dict[str, Any]:
    """
    加载指定语言的翻译文件
    
    加载目录下所有 *.json 文件，深度合并到统一的翻译字典。
    同时扫描 app/plugins/*/locales/ 目录，自动合并插件的翻译文件。
    
    Args:
        locale: 语言代码，如 'zh_CN', 'en'
    
    Returns:
        翻译字典
    """
    translations: dict[str, Any] = {}

    # 1. 加载核心翻译文件（app/locales/{locale}/*.json）
    locale_dir = LOCALES_DIR / locale
    if locale_dir.exists():
        for json_file in sorted(locale_dir.glob("*.json")):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    translations = _deep_merge(translations, data)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning("Failed to load translation file %s: %s", json_file, e)

    # 2. 扫描插件翻译文件
    # 两个位置：app/plugins/*/locales/ 和 plugins/*/locales/（已安装插件）
    _plugin_dirs = [
        LOCALES_DIR.parent / "plugins",           # app/plugins/
        LOCALES_DIR.parent.parent / "plugins",     # plugins/（已安装插件）
    ]
    for plugins_dir in _plugin_dirs:
        if not plugins_dir.is_dir():
            continue
        for plugin_dir in sorted(plugins_dir.iterdir()):
            if not plugin_dir.is_dir():
                continue
            plugin_locale_dir = plugin_dir / "locales"
            if not plugin_locale_dir.is_dir():
                continue
            locale_file = _find_plugin_locale_file(plugin_locale_dir, locale)
            if locale_file:
                try:
                    with open(locale_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        translations = _deep_merge(translations, data)
                except (json.JSONDecodeError, IOError) as e:
                    logger.warning(
                        "Failed to load plugin translation %s: %s",
                        locale_file, e,
                    )

    return translations


def reload_translations() -> None:
    """
    清除翻译缓存，强制重新加载所有翻译文件。
    
    在插件安装/卸载后调用，确保插件的翻译文件被加载。
    """
    _load_translations.cache_clear()


def get_locale() -> str:
    """获取当前请求的语言"""
    return _current_locale.get()


def set_locale(locale: str) -> None:
    """
    设置当前请求的语言
    
    Args:
        locale: 语言代码
    """
    if locale in SUPPORTED_LOCALES:
        _current_locale.set(locale)
    else:
        _current_locale.set(DEFAULT_LOCALE)


def get_translations(locale: str | None = None) -> dict[str, Any]:
    """
    获取指定语言的翻译字典
    
    Args:
        locale: 语言代码，默认使用当前上下文语言
    
    Returns:
        翻译字典
    """
    if locale is None:
        locale = get_locale()
    return _load_translations(locale)


def translate(key: str, locale: str | None = None, **kwargs: Any) -> str:
    """
    翻译指定的 key
    
    Args:
        key: 翻译键，支持点号分隔的嵌套键，如 'auth.login_success'
        locale: 语言代码，默认使用当前上下文语言
        **kwargs: 用于格式化的参数
    
    Returns:
        翻译后的字符串，如果找不到则返回 key
    
    Examples:
        >>> translate('common.success')
        '操作成功'
        >>> translate('validation.required', field='用户名')
        '用户名不能为空'
    """
    if locale is None:
        locale = get_locale()
    
    translations = get_translations(locale)
    
    # 按点号分割 key，逐层查找
    keys = key.split(".")
    value: Any = translations
    
    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            # 找不到翻译，尝试回退到默认语言
            if locale != DEFAULT_LOCALE:
                return translate(key, locale=DEFAULT_LOCALE, **kwargs)
            # 默认语言也找不到，返回 key
            return key
    
    if not isinstance(value, str):
        return key
    
    # 格式化参数替换
    if kwargs:
        try:
            value = value.format(**kwargs)
        except KeyError:
            pass
    
    return value


# 翻译函数别名
_ = translate


def parse_accept_language(accept_language: str | None) -> str:
    """
    解析 Accept-Language 头，返回最佳匹配的语言
    
    Args:
        accept_language: HTTP Accept-Language 头的值
    
    Returns:
        最佳匹配的语言代码
    
    Examples:
        >>> parse_accept_language('zh-CN,zh;q=0.9,en;q=0.8')
        'zh_CN'
        >>> parse_accept_language('en-US,en;q=0.9')
        'en'
    """
    if not accept_language:
        return DEFAULT_LOCALE
    
    # 解析语言偏好列表
    languages = []
    for part in accept_language.split(","):
        part = part.strip()
        if not part:
            continue
        
        # 解析语言和权重
        if ";q=" in part:
            lang, q = part.split(";q=")
            try:
                weight = float(q)
            except ValueError:
                weight = 1.0
        else:
            lang = part
            weight = 1.0
        
        # 标准化语言代码
        lang = lang.strip().replace("-", "_")
        languages.append((lang, weight))
    
    # 按权重排序
    languages.sort(key=lambda x: x[1], reverse=True)
    
    # 查找最佳匹配
    for lang, _ in languages:
        # 精确匹配
        if lang in SUPPORTED_LOCALES:
            return lang
        
        # 前缀匹配（如 zh 匹配 zh_CN）
        lang_prefix = lang.split("_")[0]
        for supported in SUPPORTED_LOCALES:
            if supported.startswith(lang_prefix):
                return supported
    
    return DEFAULT_LOCALE


def reload_translations() -> None:
    """
    重新加载翻译文件（清除缓存）
    
    用于开发环境中动态更新翻译
    """
    _load_translations.cache_clear()


# 导出
__all__ = [
    "SUPPORTED_LOCALES",
    "DEFAULT_LOCALE",
    "get_locale",
    "set_locale",
    "get_translations",
    "translate",
    "_",
    "parse_accept_language",
    "reload_translations",
]
