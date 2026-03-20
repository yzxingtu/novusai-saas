from __future__ import annotations

from app.services.ai.model_capability_lookup import _extract_capabilities, _find_entry
from app.tasks.scheduled import _merge_dashscope_supplements_into_registry


def test_find_entry_avoids_cross_provider_mismatch_when_provider_known() -> None:
    registry = {
        "openrouter/qwen/qwen-vl-plus": {
            "supports_vision": True,
            "max_input_tokens": 8192,
        }
    }

    assert _find_entry(registry, "qwen-vl-plus", provider_code="dashscope") is None
    assert _find_entry(registry, "qwen-vl-plus") == registry["openrouter/qwen/qwen-vl-plus"]


def test_find_entry_latest_alias_reuses_same_provider_base_entry() -> None:
    registry = {
        "dashscope/qwen-max": {
            "supports_function_calling": True,
            "max_input_tokens": 30720,
        }
    }

    assert _find_entry(
        registry,
        "qwen-max-latest",
        provider_code="dashscope",
    ) == registry["dashscope/qwen-max"]


def test_extract_capabilities_derives_modalities_and_rate_limits() -> None:
    caps = _extract_capabilities(
        {
            "mode": "chat",
            "max_input_tokens": "1048576",
            "max_output_tokens": "65535",
            "input_cost_per_token": 3e-7,
            "output_cost_per_token": 2.5e-6,
            "rpm": "100000",
            "tpm": "8000000",
            "supported_modalities": ["text", "image", "audio", "video"],
            "supports_function_calling": "true",
            "supports_streaming": "false",
        }
    )

    assert caps["model_type"] == "chat"
    assert caps["context_window"] == 1_048_576
    assert caps["max_output_tokens"] == 65_535
    assert caps["input_price_per_1k"] == 0.0003
    assert caps["output_price_per_1k"] == 0.0025
    assert caps["rpm_limit"] == 100_000
    assert caps["tpm_limit"] == 8_000_000
    assert caps["supports_vision"] is True
    assert caps["supports_audio"] is True
    assert caps["supports_video"] is True
    assert caps["supports_function_calling"] is True
    assert caps["supports_streaming"] is False


def test_merge_dashscope_supplements_adds_latest_and_inherits_base_fields(
    monkeypatch,
) -> None:
    class _Response:
        def __init__(self, text: str) -> None:
            self.text = text

        def raise_for_status(self) -> None:
            return None

    model_html = """
    <table>
      <tr>
        <td>qwen-vl-plus Currently qwen-vl-plus-2025-08-15.</td>
        <td>Stable</td>
        <td>131,072</td>
        <td>129,024 Max per image: 16,384</td>
        <td>8,192</td>
        <td>$0.21</td>
        <td>$0.63</td>
        <td>quota</td>
      </tr>
      <tr>
        <td>qwen-vl-plus-latest Always the latest snapshot.</td>
        <td>Latest</td>
        <td>$0.21</td>
        <td>$0.63</td>
      </tr>
      <tr>
        <td>qwen-max-latest Always the latest snapshot.</td>
        <td>Latest</td>
        <td>$1.6</td>
        <td>$6.4</td>
      </tr>
    </table>
    """
    rate_html = """
    <table>
      <tr><td>qwen-vl-plus</td></tr>
      <tr><td>qwen-vl-plus-latest</td></tr>
      <tr><td>qwen-vl-plus-2025-08-15 (qwen-vl-plus-0815)</td><td>120</td><td>1,000,000</td></tr>
      <tr><td>qwen-max-latest</td><td>600</td><td>1,000,000</td></tr>
    </table>
    """

    def fake_get(url: str, timeout: int):
        if "rate-limit" in url:
            return _Response(rate_html)
        return _Response(model_html)

    monkeypatch.setattr("requests.get", fake_get)

    registry = {
        "dashscope/qwen-max": {
            "supports_function_calling": True,
            "max_input_tokens": 30720,
            "max_output_tokens": 8192,
            "input_cost_per_token": 1.6e-6,
            "output_cost_per_token": 6.4e-6,
        }
    }

    added = _merge_dashscope_supplements_into_registry(registry)

    assert added == 3
    assert registry["dashscope/qwen-vl-plus"]["max_input_tokens"] == 129_024
    assert registry["dashscope/qwen-vl-plus"]["max_output_tokens"] == 8_192
    assert registry["dashscope/qwen-vl-plus"]["rpm"] == 120
    assert registry["dashscope/qwen-vl-plus"]["tpm"] == 1_000_000
    assert registry["dashscope/qwen-vl-plus"]["supports_vision"] is True

    assert registry["dashscope/qwen-vl-plus-latest"]["max_output_tokens"] == 8_192
    assert registry["dashscope/qwen-vl-plus-latest"]["rpm"] == 120
    assert registry["dashscope/qwen-vl-plus-latest"]["tpm"] == 1_000_000

    assert registry["dashscope/qwen-max-latest"]["supports_function_calling"] is True
    assert registry["dashscope/qwen-max-latest"]["max_input_tokens"] == 30720
    assert registry["dashscope/qwen-max-latest"]["rpm"] == 600
    assert registry["dashscope/qwen-max-latest"]["tpm"] == 1_000_000
