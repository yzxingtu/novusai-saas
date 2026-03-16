"""
知识库 API 共享辅助函数 / Shared helpers for knowledge base API

供 admin 与 tenant 端复用，避免重复逻辑。
For reuse by admin and tenant API modules to avoid duplication.
"""

from app.core.logging import get_logger

logger = get_logger(__name__)


def enrich_model_names(kb, result: dict) -> None:
    """
    Enrich result dict with model name fields (embedding, vision, audio, video).
    将知识库关联模型的名称填充到 result 字典。
    """
    for attr, key in [
        ("embedding_model", "embedding_model_name"),
        ("vision_model", "vision_model_name"),
        ("audio_model", "audio_model_name"),
        ("video_model", "video_model_name"),
    ]:
        result[key] = None
        try:
            model = getattr(kb, attr, None)
            if model:
                result[key] = model.name
        except Exception as exc:
            logger.debug("Knowledge base model name resolution failed: {}", exc)
