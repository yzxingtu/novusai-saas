"""Non-chat endpoint helpers for OpenAI-compatible adapter facades."""

from __future__ import annotations

from typing import Any

from openai.types import CreateEmbeddingResponse

from app.ai.exceptions import AIGatewayError, convert_openai_error
from app.ai.types import EmbeddingResponse, ImageGenerationResponse, ImageResponse
from app.core.logging import LogManager

logger = LogManager.get_logger("ai")


class OpenAIAdapterNonChatRuntimeMixin:
    """Shared embedding, image, and model-list helpers."""

    async def embedding(
        self,
        texts: list[str],
        model: str,
        **kwargs: Any,
    ) -> EmbeddingResponse:
        try:
            self._log_upstream_request(
                endpoint_path="embeddings",
                model=model,
                stream=False,
            )
            logger.info("Embedding request: model={} texts={}", model, len(texts))
            response: CreateEmbeddingResponse = await self.client.embeddings.create(
                input=texts,
                model=model,
                **kwargs,
            )
            input_tokens, _, total_tokens = self._extract_usage_tokens(response.usage)
            return EmbeddingResponse(
                embeddings=[item.embedding for item in response.data],
                input_tokens=input_tokens,
                total_tokens=total_tokens,
                model=model,
            )
        except AIGatewayError:
            raise
        except Exception as exc:  # noqa: BLE001
            self._log_upstream_error(
                exc,
                endpoint_path="embeddings",
                model=model,
            )
            logger.error("Embedding error: model={} error={}", model, str(exc))
            raise convert_openai_error(
                exc,
                provider_code="openai",
                model_code=model,
            ) from exc

    async def list_models(self) -> list[dict[str, Any]]:
        try:
            self._log_upstream_request(endpoint_path="models", model="", stream=False)
            response = await self.client.models.list()
            return [
                {
                    "id": model.id,
                    "owned_by": getattr(model, "owned_by", None),
                }
                for model in response.data
            ]
        except Exception as exc:  # noqa: BLE001
            self._log_upstream_error(exc, endpoint_path="models", model="")
            logger.error("List models error: {}", str(exc))
            raise convert_openai_error(
                exc,
                provider_code="openai",
                model_code="",
            ) from exc

    @staticmethod
    def _build_image_generation_request(
        *,
        prompt: str,
        model: str,
        size: str,
        quality: str,
        style: str,
        n: int,
        kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        request_params: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "quality": quality,
            "n": n,
            "response_format": "url",
        }
        if "dall-e-3" in model:
            request_params["style"] = style
        request_params.update(kwargs)
        return request_params

    @staticmethod
    def _convert_image_generation_response(
        *,
        response: Any,
        model: str,
    ) -> ImageGenerationResponse:
        images: list[ImageResponse] = []
        revised_prompt: str | None = None
        for item in response.data:
            url = item.url or ""
            b64 = item.b64_json or ""
            is_base64 = bool(b64 and not url)
            item_revised_prompt = getattr(item, "revised_prompt", None)
            if item_revised_prompt and not revised_prompt:
                revised_prompt = item_revised_prompt
            images.append(
                ImageResponse(
                    url=b64 if is_base64 else url,
                    is_base64=is_base64,
                    revised_prompt=item_revised_prompt,
                )
            )
        return ImageGenerationResponse(
            images=images,
            model=model,
            revised_prompt=revised_prompt,
        )

    async def generate_image(
        self,
        prompt: str,
        model: str,
        size: str = "1024x1024",
        quality: str = "standard",
        style: str = "vivid",
        n: int = 1,
        **kwargs: Any,
    ) -> ImageGenerationResponse:
        try:
            logger.info(
                "Image generation request: model={} size={} quality={} n={}",
                model,
                size,
                quality,
                n,
            )
            response = await self.client.images.generate(
                **self._build_image_generation_request(
                    prompt=prompt,
                    model=model,
                    size=size,
                    quality=quality,
                    style=style,
                    n=n,
                    kwargs=kwargs,
                )
            )
            return self._convert_image_generation_response(
                response=response,
                model=model,
            )
        except AIGatewayError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.error("Image generation error: model={} error={}", model, str(exc))
            raise convert_openai_error(
                exc,
                provider_code="openai",
                model_code=model,
            ) from exc

    def get_supported_features(self) -> dict[str, bool]:
        return {
            "chat": True,
            "streaming": True,
            "function_calling": True,
            "vision": True,
            "embedding": True,
            "image_generation": True,
        }


__all__ = ["OpenAIAdapterNonChatRuntimeMixin"]
