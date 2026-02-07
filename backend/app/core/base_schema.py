"""
Schema 基类模块

提供 Pydantic Schema 的基类，包括：
- BaseSchema: 通用 Schema 基类
- BaseCreateSchema: 创建 Schema 基类
- BaseUpdateSchema: 更新 Schema 基类
- BaseResponseSchema: 响应 Schema 基类
- PageParams: 分页参数
- PageResponse: 分页响应
"""

from datetime import datetime
from typing import Any, Generic, TypeVar
from typing import get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.core.config import settings

# 泛型类型变量
T = TypeVar("T")


class BaseSchema(BaseModel):
    """
    Schema 基类
    
    提供统一的配置和序列化行为
    """
    
    model_config = ConfigDict(
        from_attributes=True,       # 支持从 ORM 模型转换
        populate_by_name=True,      # 支持字段别名
        use_enum_values=True,       # 枚举返回值而非对象
        json_encoders={             # 自定义 JSON 编码
            datetime: lambda v: v.strftime("%Y-%m-%d %H:%M:%S") if v else None,
        },
        str_strip_whitespace=True,  # 自动去除字符串首尾空白
    )
    
    @model_validator(mode='before')
    @classmethod
    def parse_datetime_fields(cls, data: Any) -> Any:
        """
        全局 datetime 字段解析器
        
        在数据验证前,将所有字符串格式的 datetime 字段
        自动转换为带本地时区 (Asia/Shanghai) 的 datetime 对象
        
        支持的格式:
        - "YYYY-MM-DD HH:mm:ss" (前端发送的格式)
        - "YYYY-MM-DDTHH:mm:ss" (ISO 8601)
        - "YYYY-MM-DD" (纯日期)
        """
        # 只处理字典类型的数据(来自API请求)
        if not isinstance(data, dict):
            return data
        
        # 获取模型字段定义
        if not hasattr(cls, 'model_fields'):
            return data
        
        processed_data = {}
        
        for field_name, field_value in data.items():
            # 跳过 None 值
            if field_value is None:
                processed_data[field_name] = field_value
                continue
            
            # 检查字段是否存在于模型中
            if field_name not in cls.model_fields:
                processed_data[field_name] = field_value
                continue
            
            # 获取字段类型
            field = cls.model_fields[field_name]
            field_type = field.annotation
            
            # 检查字段类型是否包含 datetime
            is_datetime_field = False
            
            if field_type is datetime:
                is_datetime_field = True
            elif get_origin(field_type) is type(None) or str(get_origin(field_type)) == 'UnionType':
                # 处理 Optional[datetime] 或 datetime | None
                args = get_args(field_type)
                if datetime in args:
                    is_datetime_field = True
            
            # 如果不是 datetime 字段,直接使用原值
            if not is_datetime_field:
                processed_data[field_name] = field_value
                continue
            
            # 如果已经是 datetime 对象,添加时区信息
            if isinstance(field_value, datetime):
                if field_value.tzinfo is None:
                    # naive datetime -> 添加本地时区
                    processed_data[field_name] = field_value.replace(tzinfo=settings.tz)
                else:
                    processed_data[field_name] = field_value
                continue
            
            # 如果是字符串,尝试解析为 datetime
            if isinstance(field_value, str):
                from datetime import datetime as dt
                
                # 支持的格式列表
                formats = [
                    "%Y-%m-%d %H:%M:%S",   # 前端发送的格式
                    "%Y-%m-%dT%H:%M:%S",   # ISO 8601
                    "%Y-%m-%d",            # 纯日期
                ]
                
                for fmt in formats:
                    try:
                        parsed = dt.strptime(field_value, fmt)
                        # 解析为本地时区的 datetime
                        processed_data[field_name] = parsed.replace(tzinfo=settings.tz)
                        break
                    except ValueError:
                        continue
                else:
                    # 所有格式都失败,保留原值
                    processed_data[field_name] = field_value
            else:
                processed_data[field_name] = field_value
        
        return processed_data


class BaseCreateSchema(BaseSchema):
    """
    创建 Schema 基类
    
    用于创建资源时的数据验证
    """
    pass


class BaseUpdateSchema(BaseSchema):
    """
    更新 Schema 基类
    
    用于更新资源时的数据验证
    所有字段默认可选
    """
    pass


class BaseResponseSchema(BaseSchema):
    """
    响应 Schema 基类
    
    包含通用的响应字段
    """
    
    id: int = Field(..., description="ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")


class TenantResponseSchema(BaseResponseSchema):
    """
    租户级响应 Schema 基类
    
    包含 tenant_id 字段
    """
    
    tenant_id: int = Field(..., description="租户ID")


class PageParams(BaseSchema):
    """
    分页参数
    """
    
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")
    
    @property
    def skip(self) -> int:
        """计算跳过的记录数"""
        return (self.page - 1) * self.page_size
    
    @property
    def limit(self) -> int:
        """获取限制数量"""
        return self.page_size


class PageResponse(BaseSchema, Generic[T]):
    """
    分页响应
    
    用于包装分页查询结果
    """
    
    items: list[T] = Field(default_factory=list, description="数据列表")
    total: int = Field(..., description="总记录数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")
    pages: int = Field(..., description="总页数")
    
    @classmethod
    def create(
        cls,
        items: list[T],
        total: int,
        page: int,
        page_size: int,
    ) -> "PageResponse[T]":
        """
        创建分页响应
        
        Args:
            items: 当前页数据列表
            total: 总记录数
            page: 当前页码
            page_size: 每页数量
        
        Returns:
            分页响应对象
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
    """ID Schema，用于只需要 ID 的场景"""
    
    id: int = Field(..., description="ID")


class IDsSchema(BaseSchema):
    """批量 ID Schema"""
    
    ids: list[int] = Field(..., min_length=1, description="ID列表")


class MessageSchema(BaseSchema):
    """消息 Schema，用于简单的消息响应"""
    
    message: str = Field(..., description="消息内容")


# 导出
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
