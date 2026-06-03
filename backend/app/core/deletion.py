"""
删除依赖保护模块 / Deletion Dependency Protection Module

提供声明式删除依赖注册机制：
Provides declarative deletion dependency registration mechanism:
- DeletionStrategy: 删除策略枚举 / Deletion strategy enum (BLOCK/CASCADE_SOFT/CASCADE_DELETE/NULLIFY/IGNORE)
- DeletionDep: 单条依赖声明数据类 / Single dependency declaration dataclass

Model 通过声明 __delete_deps__ 属性，描述“哪些模型引用了我，删除时如何处理”。
Models declare __delete_deps__ to describe "which models reference me and how to handle on deletion".
BaseService._before_delete() 自动读取声明并执行依赖检查。
BaseService._before_delete() automatically reads declarations and performs dependency checks.

使用示例 / Usage:
    class AIProvider(BaseModel):
        __delete_deps__ = [
            DeletionDep("AIModel", "provider_id", DeletionStrategy.BLOCK,
                        label_field="name", i18n_key="ai_model"),
            DeletionDep("ProviderApiKey", "provider_id", DeletionStrategy.CASCADE_SOFT,
                        i18n_key="provider_api_key"),
        ]
"""

from dataclasses import dataclass

from app.enums.base import LabeledStrEnum


class DeletionStrategy(LabeledStrEnum):
    """删除依赖处理策略 / Deletion dependency handling strategy"""

    BLOCK = ("block", "enum.deletion_strategy.block")
    CASCADE_SOFT = ("cascade_soft", "enum.deletion_strategy.cascade_soft")
    CASCADE_DELETE = ("cascade_delete", "enum.deletion_strategy.cascade_delete")
    NULLIFY = ("nullify", "enum.deletion_strategy.nullify")
    IGNORE = ("ignore", "enum.deletion_strategy.ignore")


@dataclass(frozen=True)
class DeletionDep:
    """
    单条删除依赖声明 / Single deletion dependency declaration

    Attributes:
        model: 引用本模型的目标模型类名 / Target model class name referencing this model (e.g. "AIModel")
        fk_field: 目标模型中的 FK 字段名 / FK field name in target model (e.g. "provider_id")
        strategy: 删除策略 / Deletion strategy
        label_field: 目标模型中用于展示名称的字段 / Field for display name in target model (default "name")
        i18n_key: 目标模型的 i18n 翻译 key / i18n translation key for target model (e.g. "deletion.model.ai_model")
    """

    model: str
    fk_field: str
    strategy: DeletionStrategy
    label_field: str = "name"
    i18n_key: str = ""


__all__ = [
    "DeletionStrategy",
    "DeletionDep",
]
