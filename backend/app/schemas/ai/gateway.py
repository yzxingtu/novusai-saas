"""
AI 网关请求/响应 Schema

定义 AI 网关调用的请求和响应数据结构
"""

from typing import Optional, List, Literal, Any
from pydantic import BaseModel, Field, field_validator
from decimal import Decimal


class ToolCall(BaseModel):
    """工具调用定义"""
    
    id: str = Field(..., description="工具调用 ID")
    type: str = Field(default="function", description="类型")
    function: dict = Field(..., description="函数信息")


class ToolDefinition(BaseModel):
    """工具定义"""
    
    type: str = Field(default="function", description="类型")
    function: dict = Field(..., description="函数定义")


class ChatMessage(BaseModel):
    """聊天消息"""
    
    role: Literal["system", "user", "assistant", "tool"] = Field(
        ..., 
        description="消息角色"
    )
    content: Optional[str] = Field(None, description="消息内容")
    tool_calls: Optional[List[ToolCall]] = Field(default=None, description="工具调用列表")
    tool_call_id: Optional[str] = Field(default=None, description="工具调用 ID")
    
    model_config = {"extra": "allow"}


class UsageInfo(BaseModel):
    """Token 使用信息"""
    
    input_tokens: int = Field(..., description="输入 tokens")
    output_tokens: int = Field(..., description="输出 tokens")
    total_tokens: int = Field(..., description="总 tokens")
    cost: Optional[Decimal] = Field(None, description="费用(美元)")


class ChatChoice(BaseModel):
    """聊天选择"""
    
    index: int = Field(..., description="索引")
    message: ChatMessage = Field(..., description="消息")
    finish_reason: Optional[str] = Field(default=None, description="完成原因")


class DeltaContent(BaseModel):
    """增量内容(SSE 流式响应)"""
    
    role: Optional[str] = Field(default=None, description="角色")
    content: Optional[str] = Field(default=None, description="内容")
    tool_calls: Optional[List[ToolCall]] = Field(default=None, description="工具调用")


class ChatRequest(BaseModel):
    """聊天请求"""
    
    model_code: str = Field(..., description="模型代码", examples=["gpt-4", "claude-3-opus"])
    messages: List[ChatMessage] = Field(..., description="消息列表", min_length=1)
    stream: bool = Field(default=False, description="是否使用流式响应")
    temperature: float = Field(default=0.7, ge=0, le=2, description="温度参数")
    max_tokens: Optional[int] = Field(default=None, ge=1, description="最大生成 tokens")
    top_p: float = Field(default=1.0, ge=0, le=1, description="核采样参数")
    tools: Optional[List[ToolDefinition]] = Field(default=None, description="工具列表")
    user: Optional[str] = Field(default=None, description="用户标识")
    
    @field_validator("messages")
    @classmethod
    def validate_messages(cls, v: List[ChatMessage]) -> List[ChatMessage]:
        """验证消息列表"""
        if not v:
            raise ValueError("messages 不能为空")
        return v
    
    model_config = {"extra": "allow"}


class ChatResponse(BaseModel):
    """聊天响应"""
    
    id: str = Field(..., description="响应 ID")
    model: str = Field(..., description="模型名称")
    choices: List[ChatChoice] = Field(..., description="选择列表")
    usage: UsageInfo = Field(..., description="使用信息")
    created: int = Field(..., description="创建时间戳")
    
    model_config = {"extra": "allow"}


class ChatChunk(BaseModel):
    """聊天数据块(SSE 流式响应)"""
    
    id: str = Field(..., description="响应 ID")
    model: str = Field(..., description="模型名称")
    choices: List[dict] = Field(..., description="选择列表")
    created: int = Field(..., description="创建时间戳")
    
    model_config = {"extra": "allow"}


class EmbeddingRequest(BaseModel):
    """向量化请求"""
    
    model_code: str = Field(..., description="模型代码", examples=["text-embedding-ada-002"])
    texts: List[str] = Field(..., description="文本列表", min_length=1, max_length=2048)
    user: Optional[str] = Field(default=None, description="用户标识")
    
    @field_validator("texts")
    @classmethod
    def validate_texts(cls, v: List[str]) -> List[str]:
        """验证文本列表"""
        if not v:
            raise ValueError("texts 不能为空")
        if len(v) > 2048:
            raise ValueError("texts 最多支持 2048 个文本")
        return v


class EmbeddingData(BaseModel):
    """嵌入向量数据"""
    
    index: int = Field(..., description="索引")
    embedding: List[float] = Field(..., description="向量")
    object: str = Field(default="embedding", description="对象类型")


class EmbeddingResponse(BaseModel):
    """向量化响应"""
    
    id: str = Field(..., description="响应 ID")
    model: str = Field(..., description="模型名称")
    data: List[EmbeddingData] = Field(..., description="嵌入向量数据")
    usage: UsageInfo = Field(..., description="使用信息")
    
    model_config = {"extra": "allow"}


class ModelTestRequest(BaseModel):
    """模型测试请求"""
    
    provider_id: int = Field(..., description="供应商 ID")
    model_code: str = Field(..., description="模型代码", examples=["gpt-4", "claude-3-opus"])
    test_prompt: str = Field(default="你好", description="测试提示词")
    stream: bool = Field(default=False, description="是否使用流式响应")
    temperature: float = Field(default=0.7, ge=0, le=2, description="温度参数")
    max_tokens: Optional[int] = Field(default=500, ge=1, description="最大生成 tokens")
    
    model_config = {"extra": "allow"}


class ModelTestResponse(BaseModel):
    """模型测试响应"""
    
    connected: bool = Field(..., description="是否连通")
    latency_ms: int = Field(..., description="响应时间(毫秒)")
    input_tokens: int = Field(default=0, description="输入 tokens")
    output_tokens: int = Field(default=0, description="输出 tokens")
    total_tokens: int = Field(default=0, description="总 tokens")
    response_text: str = Field(default="", description="响应文本")
    error: Optional[str] = Field(default=None, description="错误信息")
    model: str = Field(..., description="模型名称")
    provider: str = Field(..., description="供应商代码")
    
    model_config = {"extra": "allow"}


__all__ = [
    "ToolCall",
    "ToolDefinition",
    "ChatMessage",
    "UsageInfo",
    "ChatChoice",
    "DeltaContent",
    "ChatRequest",
    "ChatResponse",
    "ChatChunk",
    "EmbeddingRequest",
    "EmbeddingData",
    "EmbeddingResponse",
    "ModelTestRequest",
    "ModelTestResponse",
]
