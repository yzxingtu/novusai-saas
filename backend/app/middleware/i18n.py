"""
国际化中间件

根据请求的 Accept-Language 头或查询参数设置当前请求的语言
"""

from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.i18n import DEFAULT_LOCALE, parse_accept_language, set_locale


class I18nMiddleware:
    """
    国际化中间件（纯ASGI实现）

    语言检测优先级：
    1. 查询参数 ?lang=zh_CN
    2. 请求头 X-Language
    3. 请求头 Accept-Language
    4. 默认语言

    使用纯 ASGI 实现而非 BaseHTTPMiddleware，
    以确保异常处理器能正常工作。
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        # 解析语言并设置到上下文
        lang = self._get_language_from_scope(scope)
        set_locale(lang)

        # 直接调用下一层，不修改响应
        await self.app(scope, receive, send)

    def _get_language_from_scope(self, scope: Scope) -> str:
        """从请求 scope 中提取语言"""
        # 1. 从查询参数获取
        query_string = scope.get("query_string", b"").decode("utf-8")
        if query_string:
            from urllib.parse import parse_qs
            params = parse_qs(query_string)
            if "lang" in params:
                return params["lang"][0]

        # 2. 从请求头获取
        headers = dict(scope.get("headers", []))

        # X-Language 头
        x_lang = headers.get(b"x-language", b"").decode("utf-8")
        if x_lang:
            return x_lang

        # Accept-Language 头
        accept_language = headers.get(b"accept-language", b"").decode("utf-8")
        if accept_language:
            return parse_accept_language(accept_language)

        return DEFAULT_LOCALE
