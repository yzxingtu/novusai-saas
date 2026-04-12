"""
Plugin manifest metadata companion schemas. / 插件清单元数据辅助 Schema。

Split stable feature/dependency/pricing/resource declarations out of
`app.plugins.manifest` so the public manifest module can stay focused on
extension/runtime surface contracts and the top-level facade.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.plugins.dependencies import (
    PluginDependencyRequirement,
    combine_plugin_dependency_versions,
    validate_plugin_dependency_name,
    validate_plugin_dependency_version,
)
from app.plugins.manifest_helpers import I18nText


class FeatureSchema(BaseModel):
    """Feature flag declaration / Feature Flag 声明"""

    code: str
    name: I18nText = Field(default_factory=dict)
    default: bool = True
    description: I18nText = Field(default_factory=dict)


class CompatibilityConflictSchema(BaseModel):
    """Plugin conflict declaration / 插件冲突声明"""

    plugin: str
    reason: I18nText = Field(default_factory=dict)


class CompatibilitySchema(BaseModel):
    """Compatibility matrix / 兼容性矩阵"""

    model_config = ConfigDict(extra="forbid")

    platform_version: str = "*"
    conflicts: list[CompatibilityConflictSchema] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def reject_legacy_requires(cls, data: object) -> object:
        if isinstance(data, dict) and "requires" in data:
            raise ValueError(
                "compatibility.requires has been removed. "
                "Use dependencies.plugins with optional version constraints instead."
            )
        return data


class AIFeatureSchema(BaseModel):
    """AI feature declaration / AI 功能声明"""

    feature_code: str
    display_name: I18nText = Field(default_factory=dict)
    description: I18nText = Field(default_factory=dict)
    default_prompt: str = ""


class AIRequirementsSchema(BaseModel):
    """AI requirements declaration / AI 需求声明"""

    features: list[AIFeatureSchema] = Field(default_factory=list)
    required_model_types: list[str] = Field(default_factory=list)
    min_context_window: int | None = None


class DependenciesSchema(BaseModel):
    """Dependencies declaration / 依赖声明"""

    model_config = ConfigDict(extra="forbid")

    python: list[str] = Field(default_factory=list)
    plugins: list["PluginDependencySchema"] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def reject_legacy_system_dependencies(cls, data: object) -> object:
        if isinstance(data, dict) and "system" in data:
            raise ValueError(
                "dependencies.system is not supported in the unified runtime model. "
                "Move system prerequisites to documentation or typed preflight logic."
            )
        return data

    @field_validator("python")
    @classmethod
    def validate_python_dependencies(cls, v: list[str]) -> list[str]:
        cleaned: list[str] = []
        for req in v:
            req_str = (req or "").strip()
            if not req_str:
                raise ValueError("dependencies.python item cannot be empty")
            try:
                from packaging.requirements import Requirement

                parsed = Requirement(req_str)
            except Exception as exc:
                raise ValueError(
                    f"Invalid python dependency '{req_str}': {exc}"
                ) from exc
            if parsed.url:
                raise ValueError(
                    f"Direct URL python dependency is not allowed: '{req_str}'"
                )
            cleaned.append(req_str)
        return list(dict.fromkeys(cleaned))

    @field_validator("plugins", mode="before")
    @classmethod
    def normalize_plugin_dependencies(
        cls,
        v: object,
    ) -> list[dict[str, str]] | object:
        if not isinstance(v, list):
            return v

        normalized: list[dict[str, str]] = []
        for item in v:
            if isinstance(item, str):
                normalized.append(
                    {
                        "plugin": validate_plugin_dependency_name(item),
                        "version": "*",
                    }
                )
                continue
            normalized.append(item)
        return normalized

    @field_validator("plugins")
    @classmethod
    def deduplicate_plugin_dependencies(
        cls,
        v: list["PluginDependencySchema"],
    ) -> list["PluginDependencySchema"]:
        merged: dict[str, PluginDependencySchema] = {}
        for dep in v:
            existing = merged.get(dep.plugin)
            if existing is None:
                merged[dep.plugin] = dep
                continue
            merged[dep.plugin] = PluginDependencySchema(
                plugin=dep.plugin,
                version=combine_plugin_dependency_versions(
                    existing.version,
                    dep.version,
                ),
            )
        return list(merged.values())


class PluginDependencySchema(BaseModel):
    """Plugin dependency declaration / 插件依赖声明"""

    model_config = ConfigDict(extra="forbid")

    plugin: str
    version: str = "*"

    @field_validator("plugin")
    @classmethod
    def validate_plugin(cls, v: str) -> str:
        return validate_plugin_dependency_name(v)

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        return validate_plugin_dependency_version(v)

    def to_requirement(self) -> PluginDependencyRequirement:
        return PluginDependencyRequirement(plugin=self.plugin, version=self.version)


class DeveloperSchema(BaseModel):
    """Developer information / 开发者信息"""

    name: str = ""
    email: str = ""
    url: str = ""


class TrialSchema(BaseModel):
    """Trial period configuration / 试用期配置"""

    enabled: bool = False
    days: int = 14


class PricingSchema(BaseModel):
    """Pricing information / 定价信息"""

    type: str = "free"
    price: float | None = None
    currency: str = "CNY"
    trial: TrialSchema = Field(default_factory=TrialSchema)


class ResourcesSchema(BaseModel):
    """Resources declaration / 资源声明"""

    readme: I18nText = Field(default_factory=dict)
    changelog: str = ""
    screenshots: list[str] = Field(default_factory=list)
    documentation_url: str = ""
DependenciesSchema.model_rebuild()
