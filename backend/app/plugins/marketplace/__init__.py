"""
插件市场模块 (Platform Core Module)

⚠️  WARNING: 此目录是平台核心模块，不是可卸载的插件。请勿删除！
    删除后插件市场功能将完全不可用。

职责：
- registry_service.py  — 从远程/本地拉取插件注册中心数据，提供搜索/过滤/状态比对
- download_service.py   — 从 GitHub/Gitee Release 下载插件包，执行一键安装/更新
- registry.json         — 本地开发/测试用回退数据，生产环境从远程拉取
- docs/                 — 插件开发文档

依赖的 API 控制器：app.api.admin.marketplace
依赖的 Git 客户端：app.plugins.github_client
"""
