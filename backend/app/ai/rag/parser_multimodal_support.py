"""Multimodal parser companions for image, audio, and video files."""

from __future__ import annotations

import mimetypes
from typing import TYPE_CHECKING, BinaryIO

from app.core.logging import LogManager

from .parser_contracts import DocumentParser, ParsedPage

if TYPE_CHECKING:
    from app.ai.rag.audio_describer import AudioDescriber
    from app.ai.rag.video_describer import VideoDescriber
    from app.ai.rag.vision_describer import VisionDescriber
    from app.models.ai.knowledge_base import KnowledgeBase

logger = LogManager.get_logger("ai.rag.parser")

IMAGE_TYPES: frozenset[str] = frozenset({"image", "jpg", "jpeg", "png", "webp", "gif"})
AUDIO_TYPES: frozenset[str] = frozenset({"audio", "mp3", "wav", "m4a", "flac", "aac"})
VIDEO_TYPES: frozenset[str] = frozenset({"video", "mp4", "webm", "mov", "avi", "mkv"})


class ImageParser(DocumentParser):
    """
    Image File Parser (jpg/jpeg/png/webp/gif) / 图片文件解析器（jpg/jpeg/png/webp/gif）

    Calls VisionDescriber to generate text descriptions for images, returns a single ParsedPage.
    If vision_describer is None or description is empty, returns ParsedPage with content=""
    (processor layer is responsible for filtering empty ParsedPage).
    调用 VisionDescriber 生成图片的文字描述，返回单个 ParsedPage。
    若 vision_describer 为 None 或描述为空，返回 content="" 的 ParsedPage
    （processor 层负责过滤空 ParsedPage）。
    """

    def __init__(
        self,
        vision_describer: VisionDescriber | None = None,
        knowledge_base: KnowledgeBase | None = None,
    ) -> None:
        self._vision_describer = vision_describer
        self._knowledge_base = knowledge_base

    async def parse(
        self, file_content: BinaryIO, file_name: str = ""
    ) -> list[ParsedPage]:
        image_bytes = file_content.read()

        if not self._vision_describer or not self._knowledge_base or not image_bytes:
            return [ParsedPage(content="", metadata={"source": file_name})]

        mime_type, _ = mimetypes.guess_type(file_name or "image.jpg")
        if not mime_type or not mime_type.startswith("image/"):
            mime_type = "image/jpeg"

        description = await self._vision_describer.describe_image(
            image_bytes=image_bytes,
            mime_type=mime_type,
            knowledge_base=self._knowledge_base,
        )

        logger.info(
            "Image parsed via Vision: {}, description_len={}",
            file_name,
            len(description),
        )
        return [
            ParsedPage(
                content=description,
                metadata={
                    "source": file_name,
                    "mime_type": mime_type,
                },
            )
        ]


class AudioParser(DocumentParser):
    """
    Audio File Parser / 音频文件解析器

    Uses AudioDescriber to transcribe audio to text for embedding.
    If describer is None or returns "", returns empty ParsedPage (filtered by processor).
    使用 AudioDescriber 将音频转写为文本供 embedding。无 describer 或返回 "" 时返回空 ParsedPage（由 processor 过滤）。
    """

    def __init__(
        self,
        audio_describer: AudioDescriber | None = None,
        knowledge_base: KnowledgeBase | None = None,
    ) -> None:
        self._audio_describer = audio_describer
        self._knowledge_base = knowledge_base

    async def parse(
        self, file_content: BinaryIO, file_name: str = ""
    ) -> list[ParsedPage]:
        audio_bytes = file_content.read()
        if not self._audio_describer or not audio_bytes:
            return [ParsedPage(content="", metadata={"source": file_name})]
        mime_type, _ = mimetypes.guess_type(file_name or "audio.mp3")
        if not mime_type or not mime_type.startswith("audio/"):
            mime_type = "audio/mpeg"
        description = await self._audio_describer.describe_audio(
            audio_bytes=audio_bytes,
            mime_type=mime_type,
            knowledge_base=self._knowledge_base,
        )
        logger.info("Audio parsed: {}, description_len={}", file_name, len(description))
        return [
            ParsedPage(
                content=description,
                metadata={"source": file_name, "mime_type": mime_type},
            )
        ]


class VideoParser(DocumentParser):
    """
    Video File Parser / 视频文件解析器

    Uses VideoDescriber to get text description for embedding.
    If describer is None or returns "", returns empty ParsedPage (filtered by processor).
    使用 VideoDescriber 得到文本描述供 embedding。无 describer 或返回 "" 时返回空 ParsedPage（由 processor 过滤）。
    """

    def __init__(
        self,
        video_describer: VideoDescriber | None = None,
        knowledge_base: KnowledgeBase | None = None,
    ) -> None:
        self._video_describer = video_describer
        self._knowledge_base = knowledge_base

    async def parse(
        self, file_content: BinaryIO, file_name: str = ""
    ) -> list[ParsedPage]:
        video_bytes = file_content.read()
        if not self._video_describer or not video_bytes:
            return [ParsedPage(content="", metadata={"source": file_name})]
        mime_type, _ = mimetypes.guess_type(file_name or "video.mp4")
        if not mime_type or not mime_type.startswith("video/"):
            mime_type = "video/mp4"
        description = await self._video_describer.describe_video(
            video_bytes=video_bytes,
            mime_type=mime_type,
            knowledge_base=self._knowledge_base,
        )
        logger.info("Video parsed: {}, description_len={}", file_name, len(description))
        return [
            ParsedPage(
                content=description,
                metadata={"source": file_name, "mime_type": mime_type},
            )
        ]


__all__ = [
    "AUDIO_TYPES",
    "AudioParser",
    "IMAGE_TYPES",
    "ImageParser",
    "VIDEO_TYPES",
    "VideoParser",
]
