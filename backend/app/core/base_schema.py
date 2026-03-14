"""
Schema 基类模块 / Schema Base Module

提供 Pydantic Schema 的基类，包括：
Provides base classes for Pydantic schemas, including:
- BaseSchema: 通用 Schema 基类 / Generic schema base class
- BaseCreateSchema: 创建 Schema 基类 / Creation schema base class
- BaseUpdateSchema: 更新 Schema 基类 / Update schema base class
- BaseResponseSchema: 响应 Schema 基类 / Response schema base class
- PageParams: 分页参数 / Pagination parameters
- PageResponse: 分页响应 / Paginated response
"""

from datetime import datetime
from typing import Any, Generic, TypeVar, get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

from app.core.config import settings

# 泛型类型变量 / Generic type variable
T = TypeVar("T")


class BaseSchema(BaseModel):
    """
    Schema 基类 / Schema Base Class

    提供统一的配置和序列化行为
    Provides unified configuration and serialization behavior.
    """

    model_config = ConfigDict(
        from_attributes=True,       # 支持从 ORM 模型转换 / Support conversion from ORM models
        populate_by_name=True,      # 支持字段别名 / Support field aliases
        use_enum_values=True,       # 枚举返回值而非对象 / Enums return values, not objects
        json_encoders={             # 自定义 JSON 编码 / Custom JSON encoders
            datetime: lambda v: v.isoformat() if v else None,
        },
        str_strip_whitespace=True,  # 自动去除字符串首尾空白 / Auto-strip whitespace from strings
    )

    @model_serializer(mode='wrap')
    def _serialize_model(self, handler: Any) -> dict:
        """
        全局序列化器：将所有 datetime 字段转为 ISO 8601 UTC 字符串。
        Global serializer: convert all datetime fields to ISO 8601 UTC strings.

        解决 Pydantic v2 中 model_dump() 不触发 json_encoders 的问题。
        Fixes Pydantic v2 model_dump() not triggering json_encoders.
        DB 存储 naive UTC → 输出 '2026-02-21T05:07:00+00:00'
        Browser new Date() auto-converts to local time.
        """
        from datetime import timezone as tz

        data = handler(self)
        if not isinstance(data, dict):
            return data
        for key, value in data.items():
            if isinstance(value, datetime):
                if value.tzinfo is None:
                    data[key] = value.replace(tzinfo=tz.utc).isoformat()
                else:
                    data[key] = value.isoformat()
        return data

    @model_validator(mode='before')
    @classmethod
    def parse_datetime_fields(cls, data: Any) -> Any:
        """
        全局 datetime 字段解析器 / Global datetime field parser

        在数据验证前,将所有字符串格式的 datetime 字段自动转换为带本地时区的 datetime 对象
        Before validation, auto-converts all string datetime fields to timezone-aware datetime objects.

        支持的格式 / Supported formats:
        - "YYYY-MM-DD HH:mm:ss" (前端发送的格式 / Frontend format)
        - "YYYY-MM-DDTHH:mm:ss" (ISO 8601)
        - "YYYY-MM-DD" (纯日期 / Date only)
        """
        # 只处理字典类型的数据 / Only process dict data (from API requests)
        if not isinstance(data, dict):
            return data

        # 获取模型字段定义 / Get model field definitions
        if not hasattr(cls, 'model_fields'):
            return data

        processed_data = {}

        for field_name, field_value in data.items():
            # 跳过 None 值 / Skip None values
            if field_value is None:
                processed_data[field_name] = field_value
                continue

            # 检查字段是否存在于模型中 / Check if field exists in model
            if field_name not in cls.model_fields:
                processed_data[field_name] = field_value
                continue

            # 获取字段类型 / Get field type
            field = cls.model_fields[field_name]
            field_type = field.annotation

            # 检查字段类型是否包含 datetime / Check if field type contains datetime
            is_datetime_field = False

            if field_type is datetime:
                is_datetime_field = True
            elif get_origin(field_type) is type(None) or str(get_origin(field_type)) == 'UnionType':
                # 处理 Optional[datetime] 或 datetime | None / Handle Optional[datetime] or datetime | None
                args = get_args(field_type)
                if datetime in args:
                    is_datetime_field = True

            # 如果不是 datetime 字段,直接使用原值 / Not a datetime field, use raw value
            if not is_datetime_field:
                processed_data[field_name] = field_value
                continue

            # 如果已经是 datetime 对象,添加时区信息 / If already datetime, add timezone info
            if isinstance(field_value, datetime):
                if field_value.tzinfo is None:
                    # naive datetime from DB → 标记为 UTC / Mark as UTC (DB stores UTC)
                    from datetime import timezone
                    processed_data[field_name] = field_value.replace(tzinfo=timezone.utc)
                else:
                    processed_data[field_name] = field_value
                continue

            # 如果是字符串,尝试解析为 datetime / If string, try to parse as datetime
            if isinstance(field_value, str):
                from datetime import datetime as dt

                # 支持的格式列表 / Supported format list
                formats = [
                    "%Y-%m-%d %H:%M:%S",   # 前端发送的格式 / Frontend format
                    "%Y-%m-%dT%H:%M:%S",   # ISO 8601
                    "%Y-%m-%d",            # 纯日期 / Date only
                ]

                for fmt in formats:
                    try:
                        parsed = dt.strptime(field_value, fmt)
                        # 解析为本地时区的 datetime / Parse as local-timezone datetime
                        processed_data[field_name] = parsed.replace(tzinfo=settings.tz)
                        break
                    except ValueError:
                        continue
                else:
                    # 所有格式都失败,保留原值 / All formats failed, keep raw value
                    processed_data[field_name] = field_value
            else:
                processed_data[field_name] = field_value

        return processed_data


class BaseCreateSchema(BaseSchema):
    """
    创建 Schema 基类 / Create Schema Base Class

    用于创建资源时的数据验证
    Used for data validation when creating resources.
    """
    pass


class BaseUpdateSchema(BaseSchema):
    """
    更新 Schema 基类 / Update Schema Base Class

    用于更新资源时的数据验证，所有字段默认可选
    Used for data validation when updating resources. All fields are optional by default.
    """
    pass


class BaseResponseSchema(BaseSchema):
    """
    响应 Schema 基类 / Response Schema Base Class

    包含通用的响应字段
    Contains common response fields.
    """

    id: int = Field(..., description="ID")
    created_at: datetime = Field(..., description="创建时间 / Created at")
    updated_at: datetime = Field(..., description="更新时间 / Updated at")


class TenantResponseSchema(BaseResponseSchema):
    """
    企业级响应 Schema 基类 / Tenant Response Schema Base Class

    包含 tenant_id 字段
    Includes tenant_id field.
    """

    tenant_id: int = Field(..., description="企业ID / Tenant ID")


class PageParams(BaseSchema):
    """分页参数 / Pagination Parameters"""

    page: int = Field(default=1, ge=1, description="页码 / Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量 / Page size")

    @property
    def skip(self) -> int:
        """计算跳过的记录数 / Calculate number of records to skip"""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """获取限制数量 / Get limit count"""
        return self.page_size


class PageResponse(BaseSchema, Generic[T]):
    """
    分页响应 / Paginated Response

    用于包装分页查询结果
    Used to wrap paginated query results.
    """

    items: list[T] = Field(default_factory=list, description="数据列表 / Data list")
    total: int = Field(..., description="总记录数 / Total records")
    page: int = Field(..., description="当前页码 / Current page")
    page_size: int = Field(..., description="每页数量 / Page size")
    pages: int = Field(..., description="总页数 / Total pages")

    @classmethod
    def create(
        cls,
        items: list[T],
        total: int,
        page: int,
        page_size: int,
    ) -> "PageResponse[T]":
        """
        创建分页响应 / Create paginated response

        Args:
            items: 当前页数据列表 / Current page data list
            total: 总记录数 / Total record count
            page: 当前页码 / Current page number
            page_size: 每页数量 / Page size

        Returns:
            分页响应对象 / Paginated response object
        """
        pages = (total + page_size - 1) // page_size if page_size > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )


class IDSchema(BaseSchema):
    """ID Schema，用于只需要 ID 的场景 / ID Schema for scenarios requiring only an ID"""

    id: int = Field(..., description="ID")


class IDsSchema(BaseSchema):
    """批量 ID Schema / Batch IDs Schema"""

    ids: list[int] = Field(..., min_length=1, description="ID列表 / List of IDs")


class MessageSchema(BaseSchema):
    """消息 Schema，用于简单的消息响应 / Message Schema for simple message responses"""

    message: str = Field(..., description="消息内容 / Message content")


# 导出 / Exports
__all__ = [
    "BaseSchema",
    "BaseCreateSchema",
    "BaseUpdateSchema",
    "BaseResponseSchema",
    "TenantResponseSchema",
    "PageParams",
    "PageResponse",
    "IDSchema",
    "IDsSchema",
    "MessageSchema",
]
