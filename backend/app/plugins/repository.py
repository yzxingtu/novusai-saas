"""
插件仓库抽象接口（预留）

定义远程插件仓库的标准接口，供未来插件市场对接使用。
支持从远程仓库搜索、下载、发布插件。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PluginSearchResult:
    """插件搜索结果"""
    name: str
    display_name: str
    version: str
    description: str = ""
    author: str = ""
    plugin_type: str = "composite"
    icon: str = ""
    downloads_count: int = 0
    rating: float | None = None
    tags: list[str] = field(default_factory=list)
    category: str = ""
    homepage: str = ""
    source_url: str = ""
    license: str = ""


@dataclass
class PluginSearchQuery:
    """插件搜索查询"""
    keyword: str = ""
    plugin_type: str | None = None
    category: str | None = None
    tags: list[str] | None = None
    sort_by: str = "downloads_count"
    sort_order: str = "desc"
    page: int = 1
    page_size: int = 20


@dataclass
class PluginSearchResponse:
    """插件搜索响应"""
    items: list[PluginSearchResult]
    total: int
    page: int
    page_size: int


class PluginRepository(ABC):
    """
    远程插件仓库抽象接口

    实现此接口以对接不同的插件源（官方市场、私有仓库、GitHub 等）。

    使用示例::

        class OfficialMarketplace(PluginRepository):
            async def search(self, query):
                # Call marketplace API
                ...

            async def download(self, name, version):
                # Download .nap from marketplace
                ...
    """

    @abstractmethod
    async def search(self, query: PluginSearchQuery) -> PluginSearchResponse:
        """
        搜索插件

        Args:
            query: 搜索查询条件

        Returns:
            搜索结果
        """
        ...

    @abstractmethod
    async def get_detail(self, name: str) -> PluginSearchResult | None:
        """
        获取插件详情

        Args:
            name: 插件名称

        Returns:
            插件详情或 None
        """
        ...

    @abstractmethod
    async def download(self, name: str, version: str | None = None) -> bytes:
        """
        下载插件 .nap 包

        Args:
            name: 插件名称
            version: 版本号（None 表示最新版）

        Returns:
            .nap 文件字节内容

        Raises:
            NotFoundException: 插件不存在
        """
        ...

    @abstractmethod
    async def get_versions(self, name: str) -> list[str]:
        """
        获取插件所有可用版本

        Args:
            name: 插件名称

        Returns:
            版本号列表（按 semver 降序排列）
        """
        ...

    async def publish(
        self,
        nap_content: bytes,
        metadata: dict[str, Any] | None = None,
    ) -> PluginSearchResult:
        """
        发布插件到仓库（可选实现）

        Args:
            nap_content: .nap 文件内容
            metadata: 额外元数据

        Returns:
            发布结果

        Raises:
            NotImplementedError: 仓库不支持发布
        """
        raise NotImplementedError("This repository does not support publishing")

    async def check_update(
        self,
        name: str,
        current_version: str,
    ) -> str | None:
        """
        检查插件是否有更新

        Args:
            name: 插件名称
            current_version: 当前安装版本

        Returns:
            最新版本号（有更新时）或 None（已是最新）
        """
        versions = await self.get_versions(name)
        if versions and versions[0] != current_version:
            return versions[0]
        return None


__all__ = [
    "PluginRepository",
    "PluginSearchQuery",
    "PluginSearchResponse",
    "PluginSearchResult",
]
