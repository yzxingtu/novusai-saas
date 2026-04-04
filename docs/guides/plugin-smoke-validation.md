# 插件系统发布前冒烟验证（M209-T11 + M502 补强）

## 1. 范围

- `backend/plugins/novusdoc`
- `backend/plugins/novusdoc-pro`
- `backend/plugins/weather-widget`
- 严格沙箱改造点：Dispatcher 参数注入、PluginDbProxy、License Gate、前端路径规范
- **M502 补强**：静态资源边界、manifest 信任边界、license 多记录/签名统一、版本管理加锁、webhook 脱敏、扩展注册 fail-close

## 2. 自动化结果（已执行）

### 2.1 插件契约测试

```bash
python -m pytest tests/plugins/test_contract_lifecycle.py -q
```

结果：`29 passed`

### 2.2 插件核心回归（含 M502 新增）

```bash
python -m pytest tests/test_plugin_api_dispatcher_security.py tests/test_plugin_loader.py tests/test_plugin_lifecycle_lock.py tests/test_plugin_module_loader.py tests/test_plugin_asset_resolver.py tests/test_plugin_api_dispatcher_context_safety.py tests/test_plugin_license_query_stability.py tests/test_plugin_service_license_activation.py tests/test_plugin_license_verification_policy.py tests/test_plugin_version_manager_locking.py tests/test_plugin_webhook_dispatcher_security.py -q
```

结果：`42 passed`

### 2.3 三插件清单与 handler 加载检查

执行了以下检查：

- plugin manifest 可解析（novusdoc / novusdoc-pro / weather-widget）
- 全部 API route 的 handler 可加载
- `extensions.frontend.pages[*].path` 路径前缀合规（`/admin/plugins/` 或 `/tenant/plugins/`）
- `pages[*].menu` 只承担菜单 metadata，不再额外维护 `frontend.menus` / `standalone_pages`
- 若 handler 声明 `db` 参数，插件必须声明 `db:own_tables`

结果：`plugin-smoke-check-ok`

## 3. 改造点覆盖矩阵

| 检查项 | novusdoc | novusdoc-pro | weather-widget |
|---|---|---|---|
| Dispatcher 严格参数注入兼容 | PASS | PASS | PASS |
| `db` 注入能力门控 | PASS | PASS | PASS |
| raw session 逃逸防护 | PASS | PASS | PASS |
| License Gate 与 strict sandbox 兼容 | N/A | PASS | N/A |
| 前端路径前缀规范 | PASS | PASS | PASS |
| API handler 加载 | PASS | PASS | PASS |
| /plugin-assets 仅 dist 文件（M502） | PASS | PASS | PASS |
| manifest 信任边界（生产用 DB 快照） | PASS | PASS | PASS |
| license 多记录查询稳定性 | N/A | PASS | N/A |
| license 激活统一签名验证 | PASS | PASS | PASS |
| 扩展注册 fail-close | PASS | PASS | PASS |
| VersionManager 加锁+缓存清理 | PASS | PASS | PASS |
| Webhook 错误脱敏+密钥解密一致 | PASS | PASS | PASS |

## 4. 手工运行时冒烟清单（待发布窗口执行）

> 以下步骤用于上线窗口最终确认，需在部署环境执行。

### 4.1 novusdoc

1. 登录企业端，打开文档列表页（`/tenant/plugins/novusdoc/docs`）
2. 新建文档、编辑文档、删除文档
3. 调用 AI 相关接口（如 `docs/{doc_id}/ai/continue`）

预期：

- 列表与详情正常
- CRUD 无 5xx
- AI 流式/降级路径可用

### 4.2 novusdoc-pro

1. 访问评论/成员/版本/分享路径
2. 未激活 license 时校验门控返回（403 + license 提示）
3. 激活 license 后重复操作验证可通行

预期：

- 门控逻辑与提示正确
- 激活后接口可用
- 无跨表沙箱异常

### 4.3 weather-widget

1. 访问配置接口 `config`
2. 调用天气查询 `current`/`forecast`/`geocoding`

预期：

- `ctx.get_config()` 读取正常
- 天气 API 代理可返回数据或可解释错误

## 5. 验收结论

- 自动化与静态检查均通过，可进入发布窗口。
- 手工运行时冒烟建议在灰度发布阶段执行并留存截图/日志。
