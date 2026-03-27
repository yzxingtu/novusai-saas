"""
LiteLLM + LLMRing multi-source registry sync tests / 多源模型能力注册表同步测试

Covers:
- Helper functions: _parse_bool_safe, _normalize_llmring_entry,
  _find_registry_key_for_model_id, _merge_llmring_into_registry
- Task flow: LiteLLM fallback, LLMRing degradation, full failure, return fields
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.tasks.scheduled import (
    LITELLM_REGISTRY_URLS,
    _build_registry_from_litellm,
    _find_registry_key_for_model_id,
    _is_valid_litellm_entry,
    _merge_entry_fill_empty,
    _merge_llmring_into_registry,
    _normalize_llmring_entry,
    _parse_bool_safe,
    sync_litellm_registry,
)

# ── _parse_bool_safe ───────────────────────────────────────────────────────


class TestParseBoolSafe:
    """Boolean safe parsing / 布尔安全解析"""

    def test_bool_false_not_string_true(self) -> None:
        """\"false\" must not become True. / \"false\" 不能转为 True"""
        assert _parse_bool_safe("false") is False
        assert _parse_bool_safe("FALSE") is False
        assert _parse_bool_safe("False") is False

    def test_bool_true(self) -> None:
        assert _parse_bool_safe("true") is True
        assert _parse_bool_safe("1") is True
        assert _parse_bool_safe("yes") is True

    def test_bool_false_values(self) -> None:
        assert _parse_bool_safe("false") is False
        assert _parse_bool_safe("0") is False
        assert _parse_bool_safe("no") is False

    def test_native_bool(self) -> None:
        assert _parse_bool_safe(True) is True
        assert _parse_bool_safe(False) is False

    def test_unparseable_returns_none(self) -> None:
        assert _parse_bool_safe("") is None
        assert _parse_bool_safe("maybe") is None
        assert _parse_bool_safe(123) is None


# ── _normalize_llmring_entry ──────────────────────────────────────────────────


class TestNormalizeLlmringEntry:
    """LLMRing entry normalization / LLMRing 条目归一化"""

    def test_empty_raw_returns_minimal(self) -> None:
        """Empty raw yields mode=chat only. / 空 raw 仅返回 mode=chat"""
        out = _normalize_llmring_entry({})
        assert out == {"mode": "chat"}

    def test_price_conversion(self) -> None:
        """dollars_per_million -> per token. / 百万美元转为 per-token"""
        raw = {
            "dollars_per_million_tokens_input": 1.0,
            "dollars_per_million_tokens_output": 2.0,
        }
        out = _normalize_llmring_entry(raw)
        assert out["input_cost_per_token"] == 1e-6
        assert out["output_cost_per_token"] == 2e-6

    def test_bool_parsed_safely(self) -> None:
        """String \"false\" must not become True. / \"false\" 必须解析为 False"""
        raw = {"supports_vision": "false", "supports_function_calling": "true"}
        out = _normalize_llmring_entry(raw)
        assert out["supports_vision"] is False
        assert out["supports_function_calling"] is True


# ── _find_registry_key_for_model_id ─────────────────────────────────────────


class TestFindRegistryKeyForModelId:
    """Dedup key lookup / 去重 key 查找"""

    def test_reg_key_exists_returns_it(self) -> None:
        registry = {"openai/gpt-4.1": {"max_input_tokens": 128}}
        assert (
            _find_registry_key_for_model_id(
                registry, "gpt-4.1", "openai/gpt-4.1"
            )
            == "openai/gpt-4.1"
        )

    def test_model_id_suffix_match(self) -> None:
        registry = {"openai/gpt-4.1": {}}
        assert (
            _find_registry_key_for_model_id(
                registry, "gpt-4.1", "other/key"
            )
            == "openai/gpt-4.1"
        )

    def test_exact_model_id_match(self) -> None:
        registry = {"gpt-4.1": {}}
        assert (
            _find_registry_key_for_model_id(
                registry, "gpt-4.1", "openai/gpt-4.1"
            )
            == "gpt-4.1"
        )

    def test_not_found_returns_none(self) -> None:
        registry = {"other/model": {}}
        assert (
            _find_registry_key_for_model_id(
                registry, "gpt-4.1", "openai/gpt-4.1"
            )
            is None
        )


# ── _merge_llmring_into_registry ─────────────────────────────────────────────


class TestMergeLlmringIntoRegistry:
    """LLMRing merge and dedup / LLMRing 合并与去重"""

    def test_reg_key_exists_merges_fill_empty(self) -> None:
        """Existing key: merge fill empty, no new key. / 已有 key: 合并填空"""
        registry = {"openai/gpt-4.1": {"max_input_tokens": 100}}
        payload = {
            "models": {
                "openai:gpt-4.1": {
                    "max_output_tokens": 200,
                    "max_input_tokens": 999,
                }
            }
        }
        added = _merge_llmring_into_registry(registry, payload)
        assert added == 0
        assert registry["openai/gpt-4.1"]["max_input_tokens"] == 100  # not overwritten
        assert registry["openai/gpt-4.1"]["max_output_tokens"] == 200

    def test_new_key_added_when_not_found(self) -> None:
        registry = {}
        payload = {
            "models": {
                "openai:gpt-4.1": {"max_input_tokens": 128}
            }
        }
        added = _merge_llmring_into_registry(registry, payload)
        assert added == 1
        assert "openai/gpt-4.1" in registry
        assert registry["openai/gpt-4.1"]["max_input_tokens"] == 128

    def test_empty_normalized_skipped(self) -> None:
        """Empty normalized entry must not add key. / 空归一化条目不新增 key"""
        registry = {}
        payload = {
            "models": {
                "openai:empty-model": {}
            }
        }
        added = _merge_llmring_into_registry(registry, payload)
        assert added == 0
        assert "openai/empty-model" not in registry


# ── _build_registry_from_litellm / _is_valid_litellm_entry ───────────────────


class TestBuildRegistryFromLitellm:
    """LiteLLM registry build / LiteLLM 主 registry 构建"""

    def test_sample_spec_excluded(self) -> None:
        raw = {"sample_spec": {"x": 1}, "openai/gpt-4": {"max_input_tokens": 1}}
        registry, count = _build_registry_from_litellm(raw)
        assert "sample_spec" not in registry
        assert "openai/gpt-4" in registry
        assert count == 1

    def test_empty_dict_excluded(self) -> None:
        raw = {"openai/empty": {}}
        registry, count = _build_registry_from_litellm(raw)
        assert "openai/empty" not in registry
        assert count == 0


# ── _merge_entry_fill_empty ───────────────────────────────────────────────────


class TestMergeEntryFillEmpty:
    """Fill empty only, no overwrite / 只填空不覆盖"""

    def test_fills_empty_slot(self) -> None:
        target = {"a": None}
        _merge_entry_fill_empty(target, {"a": 1})
        assert target["a"] == 1

    def test_does_not_overwrite_existing(self) -> None:
        target = {"a": 42}
        _merge_entry_fill_empty(target, {"a": 1})
        assert target["a"] == 42


# ── Task flow (mock requests + redis) ─────────────────────────────────────────


class TestSyncLitellmRegistryTask:
    """sync_litellm_registry task flow / 任务流程"""

    def _make_litellm_response(self, count: int = 15) -> dict:
        return {f"model-{i}": {"max_input_tokens": 128} for i in range(count)}

    @patch("app.tasks.scheduled._get_sync_redis")
    @patch("requests.get")
    def test_first_url_fails_second_succeeds(
        self, mock_get: MagicMock, mock_redis: MagicMock
    ) -> None:
        """LiteLLM first URL fails, second succeeds. / 首 URL 失败次 URL 成功"""
        litellm_resp = MagicMock()
        litellm_resp.raise_for_status = MagicMock()
        litellm_resp.json.return_value = self._make_litellm_response()

        llmring_resp = MagicMock()
        llmring_resp.raise_for_status = MagicMock()
        llmring_resp.json.return_value = {"models": {}}

        mock_get.side_effect = [
            Exception("network error"),
            litellm_resp,
            llmring_resp,
            llmring_resp,
            llmring_resp,
        ]

        redis_client = MagicMock()
        mock_redis.return_value = redis_client

        result = sync_litellm_registry.apply().get()

        assert result["model_count"] >= 15
        assert result["litellm_keys"] >= 15
        assert LITELLM_REGISTRY_URLS[1] in str(result["source"])
        redis_client.setex.assert_called_once()

    @patch("app.tasks.scheduled.logger")
    @patch("app.tasks.scheduled._get_sync_redis")
    @patch("requests.get")
    def test_llmring_provider_fail_task_still_succeeds(
        self, mock_get: MagicMock, mock_redis: MagicMock, mock_logger: MagicMock
    ) -> None:
        """LLMRing one provider fail, task still succeeds. / LLMRing 单 provider 失败仍成功"""
        litellm_resp = MagicMock()
        litellm_resp.raise_for_status = MagicMock()
        litellm_resp.json.return_value = self._make_litellm_response()

        def get_side_effect(url, **kwargs):
            if "litellm" in url or "BerriAI" in url:
                return litellm_resp
            if "openai" in url:
                raise Exception("openai fetch failed")
            if "anthropic" in url or "google" in url:
                r = MagicMock()
                r.raise_for_status = MagicMock()
                r.json.return_value = {"models": {}}
                return r
            raise ValueError(url)

        mock_get.side_effect = get_side_effect
        mock_redis.return_value = MagicMock()

        result = sync_litellm_registry.apply().get()

        assert result["model_count"] >= 15
        assert "source" in result
        assert "litellm_keys" in result
        assert "llmring_added_keys" in result

        mock_logger.warning.assert_any_call(
            "LLMRing provider fetch failed: provider={} error={}",
            "openai",
            "openai fetch failed",
        )

    @patch("app.tasks.scheduled._get_sync_redis")
    @patch("requests.get")
    def test_all_litellm_fail_raises(
        self, mock_get: MagicMock, mock_redis: MagicMock
    ) -> None:
        """All LiteLLM URLs fail → RuntimeError. / 全部 LiteLLM 失败抛异常"""
        mock_get.side_effect = Exception("all failed")
        mock_redis.return_value = MagicMock()

        with pytest.raises(RuntimeError, match="All LiteLLM registry URLs failed"):
            sync_litellm_registry.apply().get()

    @patch("app.tasks.scheduled.logger")
    @patch("app.tasks.scheduled._get_sync_redis")
    @patch("requests.get")
    def test_return_fields_present(
        self, mock_get: MagicMock, mock_redis: MagicMock, mock_logger: MagicMock
    ) -> None:
        """Return dict has model_count, litellm_keys, llmring_added_keys; info log has source/metrics."""
        litellm_resp = MagicMock()
        litellm_resp.raise_for_status = MagicMock()
        litellm_resp.json.return_value = self._make_litellm_response()

        def get_side_effect(url, **kwargs):
            if "litellm" in url or "BerriAI" in url or "model_prices" in url:
                return litellm_resp
            r = MagicMock()
            r.raise_for_status = MagicMock()
            r.json.return_value = {"models": {"openai:gpt-4": {"max_input_tokens": 128}}}
            return r

        mock_get.side_effect = get_side_effect
        mock_redis.return_value = MagicMock()

        result = sync_litellm_registry.apply().get()

        assert "source" in result
        assert "model_count" in result
        assert "litellm_keys" in result
        assert "llmring_added_keys" in result
        assert result["model_count"] > 0
        assert result["litellm_keys"] > 0

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == (
            "LiteLLM registry synced: source={} models={} litellm_keys={} llmring_added={}"
        )
        assert call_args[0][1] == result["source"]
        assert call_args[0][2] == result["model_count"]
        assert call_args[0][3] == result["litellm_keys"]
        assert call_args[0][4] == result["llmring_added_keys"]
