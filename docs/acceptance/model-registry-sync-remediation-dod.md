# 模型能力多源同步整改 DoD 验收记录

> 对应整改方案：`@模型能力同步整改方案_728f7a76.plan.md`

## 验收标准（DoD）完成情况

| 标准 | 状态 | 说明 |
|------|------|------|
| 任务描述（代码与 DB）均明确为多源同步 | ✅ | `scheduled.py` 与迁移 `20260318_0002_litellm_desc` 已更新 |
| 不会新增空能力 entry | ✅ | `_merge_llmring_into_registry` 在 `len(normalized)==1 and mode=="chat"` 时跳过 |
| 自动化测试覆盖关键分支并通过 | ✅ | `tests/tasks/test_registry_sync.py` 共 23 个用例 |
| 文档关键行为有测试或验收记录对应 | ✅ | 去重、布尔解析、降级、统计字段、日志口径均有测试断言 |

## 整改实施明细

### 阶段一：一致性修正

- [x] `scheduled.py` 任务 description 更新为「Sync LiteLLM + LLMRing multi-source model registry to Redis」
- [x] 迁移 `20260318_0002_update_litellm_registry_task_description.py`：UPDATE periodic_tasks 描述
- [x] 前端 i18n（admin/tenant system.json）文案统一为「LiteLLM + LLMRing 多源模型注册表同步」
- [x] cron `0 4 * * *` 保持不变

### 阶段二：逻辑稳健性

- [x] `_merge_llmring_into_registry`：归一化仅含默认 mode 的条目不新增 key，记录 debug 日志

### 阶段三：测试补齐

- [x] `_parse_bool_safe`：5 用例（false/true/原生 bool/不可解析）
- [x] `_normalize_llmring_entry`：3 用例（空 raw、价格换算、布尔安全）
- [x] `_find_registry_key_for_model_id`：4 用例（reg_key 存在、suffix 命中、精确匹配、未找到）
- [x] `_merge_llmring_into_registry`：3 用例（合并填空、新增 key、空归一化跳过）
- [x] `_build_registry_from_litellm` / `_is_valid_litellm_entry`：2 用例（sample_spec 排除、空 dict 排除）
- [x] `_merge_entry_fill_empty`：2 用例（填空、不覆盖）
- [x] 任务流程：4 用例（首 URL 失败次 URL 成功、LLMRing 单 provider 失败仍成功、全失败抛错、返回字段正确）
- [x] 日志口径：`test_llmring_provider_fail_task_still_succeeds` 断言 warning 含 provider 与 error；`test_return_fields_present` 断言 info 含 source/model_count/litellm_keys/llmring_added

### 阶段四：验收检查

- [x] 去重：`test_reg_key_exists_merges_fill_empty`、`test_new_key_added_when_not_found`
- [x] 布尔：`test_bool_false_not_string_true`、`test_bool_parsed_safely`
- [x] 容错：`test_llmring_provider_fail_task_still_succeeds`、`test_all_litellm_fail_raises`
- [x] 统计字段：`test_return_fields_present` 断言 source/model_count/litellm_keys/llmring_added_keys
- [x] 日志口径：上述用例中 mock logger 并断言 warning/info 调用参数，CI 可防护日志字段被改坏

## 测试执行结果

```bash
cd backend && python -m pytest tests/tasks/test_registry_sync.py -v
# 23 passed
```

## 修改文件清单

- `backend/app/tasks/scheduled.py`：description、空条目跳过逻辑
- `backend/migrations/versions/20260318_0002_update_litellm_registry_task_description.py`：新增
- `backend/tests/tasks/__init__.py`：新增
- `backend/tests/tasks/test_registry_sync.py`：新增
- `frontend/apps/web-antd/src/locales/langs/zh-CN/admin/system.json`：sync_litellm_registry 文案
- `frontend/apps/web-antd/src/locales/langs/en-US/admin/system.json`：同上
- `frontend/apps/web-antd/src/locales/langs/zh-CN/tenant/system.json`：同上
- `frontend/apps/web-antd/src/locales/langs/en-US/tenant/system.json`：同上
