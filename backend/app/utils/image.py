"""
图片处理工具

提供本地图片处理能力（Pillow 封装）
仅用于 LocalStorageDriver 和无原生图片处理能力的存储驱动
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from typing import BinaryIO, Literal

import anyio
from PIL import Image

# 支持的输出格式
SUPPORTED_FORMATS = {"jpg", "jpeg", "png", "webp", "gif"}

# 格式到 MIME 类型映射
FORMAT_MIME_MAP = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "gif": "image/gif",
}

# 格式到 Pillow 格式名映射
FORMAT_PILLOW_MAP = {
    "jpg": "JPEG",
    "jpeg": "JPEG",
    "png": "PNG",
    "webp": "WEBP",
    "gif": "GIF",
}

# 处理模式
ProcessMode = Literal["fit", "fill", "crop", "pad"]


@dataclass
class ImageProcessParams:
    """
    图片处理参数

    Attributes:
        width: 目标宽度（像素），None 表示不限制
        height: 目标高度（像素），None 表示不限制
        quality: 输出质量（1-100）
        format: 输出格式（jpg/png/webp/gif），None 表示保持原格式
        mode: 处理模式（fit/fill/crop/pad）
    """
    width: int | None = None
    height: int | None = None
    quality: int = 85
    format: str | None = None
    mode: ProcessMode = "fit"

    def __post_init__(self):
        """参数校验和规范化"""
        # 限制尺寸范围
        if self.width is not None:
            self.width = max(1, min(self.width, 4096))
        if self.height is not None:
            self.height = max(1, min(self.height, 4096))
        # 限制质量范围
        self.quality = max(1, min(self.quality, 100))
        # 规范化格式
        if self.format:
            self.format = self.format.lower()
            if self.format not in SUPPORTED_FORMATS:
                self.format = None

    def to_cache_key(self) -> str:
        """
        生成缓存键后缀

        Returns:
            基于参数的哈希字符串
        """
        parts = [
            f"w{self.width}" if self.width else "",
            f"h{self.height}" if self.height else "",
            f"q{self.quality}",
            f"f{self.format}" if self.format else "",
            f"m{self.mode}",
        ]
        key_str = "_".join(p for p in parts if p)
        return hashlib.md5(key_str.encode()).hexdigest()[:12]

    @classmethod
    def from_preset(cls, preset: str) -> ImageProcessParams:
        """
        从预设名称创建参数

        Args:
            preset: 预设名称

        Returns:
            对应的参数实例

        Raises:
            ValueError: 预设不存在
        """
        if preset not in PRESETS:
            raise ValueError(f"Unknown preset: {preset}")
        return cls(**PRESETS[preset])

    @classmethod
    def from_query(
        cls,
        w: int | None = None,
        h: int | None = None,
        q: int = 85,
        f: str | None = None,
        m: str = "fit",
        p: str | None = None,
    ) -> ImageProcessParams:
        """
        从 URL 查询参数创建

        Args:
            w: 宽度
            h: 高度
            q: 质量
            f: 格式
            m: 模式
            p: 预设名称（优先级高于其他参数）

        Returns:
            参数实例
        """
        if p:
            return cls.from_preset(p)
        return cls(width=w, height=h, quality=q, format=f, mode=m)  # type: ignore

    def is_empty(self) -> bool:
        """判断是否为空参数（不需要处理）"""
        return self.width is None and self.height is None and self.format is None


# 预设配置
PRESETS: dict[str, dict] = {
    "thumb": {
        "width": 150,
        "height": 150,
        "mode": "fill",
        "quality": 80,
    },
    "avatar": {
        "width": 100,
        "height": 100,
        "mode": "fill",
        "quality": 85,
    },
    "preview": {
        "width": 800,
        "height": 600,
        "mode": "fit",
        "quality": 85,
    },
    "banner": {
        "width": 1200,
        "height": 400,
        "mode": "fill",
        "quality": 90,
    },
    "small": {
        "width": 320,
        "height": 320,
        "mode": "fit",
        "quality": 80,
    },
    "medium": {
        "width": 640,
        "height": 640,
        "mode": "fit",
        "quality": 85,
    },
    "large": {
        "width": 1280,
        "height": 1280,
        "mode": "fit",
        "quality": 90,
    },
}


class ImageProcessor:
    """
    本地图片处理器

    基于 Pillow 实现图片缩放、裁剪、格式转换等功能
    """

    @staticmethod
    async def process(
        source: BinaryIO | bytes,
        params: ImageProcessParams,
    ) -> tuple[bytes, str]:
        """
        处理图片

        Args:
            source: 源图片（文件对象或字节）
            params: 处理参数

        Returns:
            (处理后的字节数据, MIME 类型)
        """
        def _process() -> tuple[bytes, str]:
            # 读取源图片
            if isinstance(source, bytes):
                img = Image.open(io.BytesIO(source))
            else:
                img = Image.open(source)

            # 获取原始信息
            original_format = img.format or "JPEG"
            original_mode = img.mode

            # 确定输出格式
            output_format = params.format or original_format.lower()
            if output_format == "jpg":
                output_format = "jpeg"
            pillow_format = FORMAT_PILLOW_MAP.get(output_format, "JPEG")
            mime_type = FORMAT_MIME_MAP.get(output_format, "image/jpeg")

            # 处理透明通道
            if pillow_format == "JPEG" and original_mode in ("RGBA", "LA", "P"):
                # JPEG 不支持透明，转换为 RGB
                if original_mode == "P":
                    img = img.convert("RGBA")
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "RGBA":
                    background.paste(img, mask=img.split()[3])
                else:
                    background.paste(img)
                img = background
            elif pillow_format in ("JPEG",) and original_mode not in ("RGB", "L"):
                img = img.convert("RGB")

            # 执行尺寸处理
            if params.width or params.height:
                img = ImageProcessor._resize(
                    img,
                    params.width,
                    params.height,
                    params.mode,
                )

            # 输出到字节流
            output = io.BytesIO()
            save_kwargs = {}

            if pillow_format == "JPEG":
                save_kwargs["quality"] = params.quality
                save_kwargs["optimize"] = True
            elif pillow_format == "WEBP":
                save_kwargs["quality"] = params.quality
                save_kwargs["method"] = 4  # 压缩方法
            elif pillow_format == "PNG":
                save_kwargs["optimize"] = True

            img.save(output, format=pillow_format, **save_kwargs)
            return output.getvalue(), mime_type

        return await anyio.to_thread.run_sync(_process)

    @staticmethod
    def _resize(
        img: Image.Image,
        width: int | None,
        height: int | None,
        mode: ProcessMode,
    ) -> Image.Image:
        """
        调整图片尺寸

        Args:
            img: 原始图片
            width: 目标宽度
            height: 目标高度
            mode: 处理模式

        Returns:
            处理后的图片
        """
        original_width, original_height = img.size

        # 计算目标尺寸
        target_width = width or original_width
        target_height = height or original_height

        if mode == "fit":
            # 等比缩放，不超出指定尺寸
            img.thumbnail((target_width, target_height), Image.Resampling.LANCZOS)
            return img

        elif mode == "fill":
            # 等比缩放并裁剪，填满指定尺寸
            # 计算缩放比例
            ratio_w = target_width / original_width
            ratio_h = target_height / original_height
            ratio = max(ratio_w, ratio_h)

            # 先缩放
            new_width = int(original_width * ratio)
            new_height = int(original_height * ratio)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # 再居中裁剪
            left = (new_width - target_width) // 2
            top = (new_height - target_height) // 2
            right = left + target_width
            bottom = top + target_height
            return img.crop((left, top, right, bottom))

        elif mode == "crop":
            # 从中心裁剪
            left = (original_width - target_width) // 2
            top = (original_height - target_height) // 2
            # 确保不越界
            left = max(0, left)
            top = max(0, top)
            right = min(original_width, left + target_width)
            bottom = min(original_height, top + target_height)
            return img.crop((left, top, right, bottom))

        elif mode == "pad":
            # 等比缩放，不足部分填充白色
            img.thumbnail((target_width, target_height), Image.Resampling.LANCZOS)
            new_width, new_height = img.size

            # 创建目标尺寸的白色背景
            if img.mode in ("RGBA", "LA"):
                background = Image.new("RGBA", (target_width, target_height), (255, 255, 255, 255))
            else:
                background = Image.new("RGB", (target_width, target_height), (255, 255, 255))

            # 居中粘贴
            paste_x = (target_width - new_width) // 2
            paste_y = (target_height - new_height) // 2
            background.paste(img, (paste_x, paste_y))
            return background

        # 默认返回原图
        return img

    @staticmethod
    def is_image(mime_type: str | None) -> bool:
        """
        判断 MIME 类型是否为支持的图片格式

        Args:
            mime_type: MIME 类型

        Returns:
            是否为图片
        """
        if not mime_type:
            return False
        return mime_type.lower() in (
            "image/jpeg",
            "image/jpg",
            "image/png",
            "image/webp",
            "image/gif",
        )


__all__ = [
    "ImageProcessParams",
    "ImageProcessor",
    "PRESETS",
    "SUPPORTED_FORMATS",
    "FORMAT_MIME_MAP",
]
