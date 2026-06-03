"""
代码生成器常量 / Codegen constants
"""

from pathlib import Path

# 项目根目录（backend 的父级，即 monorepo 根）/ Project root (parent of backend)
CODEGEN_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# Endpoint scope 合法值 / Valid endpoint scope values
SCOPE_VALUES = frozenset({"admin", "tenant", "admin_only", "tenant_only"})

# data_mode 合法值 / Valid data_mode values
DATA_MODE_VALUES = frozenset({"cross_tenant", "independent", "tenant_isolated"})

# base_class 合法值 / Valid base_class values
BASE_CLASS_VALUES = frozenset({"BaseModel", "TenantModel"})

# sub_table mode 合法值 / Valid sub_table mode values
SUB_TABLE_MODE_VALUES = frozenset({"embedded", "standard", "erp"})
