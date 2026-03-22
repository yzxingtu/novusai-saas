# 测试与验证规则

## 后端单元测试

- 新增或重构 Service 后，优先补 `tests/services/test_{name}.py`
- 测试不得依赖真实 DB、Redis、网络、第三方 API
- 优先复用 `tests/services/conftest.py` 的共享 fixtures 和 mock 工厂
- Service 实例化用 `__new__` 跳过 `__init__`，手动注入 `db` / `tenant_id` / `repo`
- 每个 Service 测试文件至少覆盖正常流程、边界条件、异常分支
- 一般要求不少于 6 个 case，核心服务建议 10 个以上

## Mock 规范

- 数据库查询结果统一用 `make_scalar_result()`、`make_scalars_result()`、`make_row_result()`
- 外部依赖用 `patch()` / `patch.object()`
- 所有 async Service 测试使用 `pytest.mark.asyncio`

## 浏览器验证

- 日常页面验证优先使用 `chrome-devtools`
- 需要文件上传或复杂多标签页时再使用 `playwright`
- 同一条测试流程不要混用两套浏览器 MCP
- 页面状态变化后重新 snapshot，不要复用失效的 `uid` / `ref`
- 先查 console / network，再判断前端逻辑是否失败

## AI 配额 / 限速专项验证

- 涉及 `backend/app/ai/quota.py`、`backend/app/ai/rate_limiter.py`、`backend/app/ai/usage_recorder.py`、`admin/ai/quotas` 时，**禁止**只做编译或类型检查后就结束。
- 最低后端验证 / Minimum backend verification：
  - 目标测试文件至少覆盖硬配额、软配额、全局配额回退、限速继承、失败回滚
  - 诊断 Service 必须验证返回的 `exhaustion_action`、`exhaustion_http_status`、`exhaustion_error_code`
- 最低真实联调 / Minimum live validation：
  - 管理端登录：`admin / admin123456`
  - 企业端登录：`adminsss / admin123456`
  - 先创建临时规则，再通过真实入口触发一次运行时拦截，确认：
    - 硬配额返回 `HTTP 429 / 4291`
    - 速率限制返回 `HTTP 429 / 4292`
    - 软配额不会拦截请求
  - 测试结束后必须删除临时规则，避免污染环境

## 回收站回归最低要求

- 凡是列表页开启了 `recycleBin: true`，至少验证一次模块回收站弹窗可打开，且 `.../recycle-bin/count`、`.../recycle-bin?page[number]=1&page[size]=20` 返回 `200`
- 管理端模块回收站必须出现“查看总回收站”按钮，并跳转到 `/admin/system/recycle-bin`
- 企业端模块回收站必须**没有**“查看总回收站”按钮；直接访问 `/tenant/system/recycle-bin` 必须是 `404`
- 总回收站页面至少验证 `/admin/recycle-bin/modules`、`/admin/recycle-bin/summary`、`/admin/recycle-bin?...` 三类请求返回 `200`
- 控制器存在 `/{id}` 或 `/{task_id}` 之类动态路由时，必须确认 `register_admin_recycle_bin_routes()` / `register_tenant_recycle_bin_routes()` 注册在动态路由之前，避免把 `recycle-bin` 误解析成路径参数
- 企业端模型若归属列是 `owner_tenant_id`，必须额外验证回收站查询不会再强制注入错误的 `tenant_id` 过滤
- 浏览器验证完成后，顺手检查 `list_console_messages(types=[\"error\"])`；若有报错，需要区分是本次改动引入，还是页面原有噪音

## 验收最低要求

- 新增表单：至少验证打开、填写、提交、错误提示
- 新增列表：至少验证筛选、分页、权限按钮显示
- 新增上传下载：至少验证上传成功、下载成功、权限或可见性正确
- 新增插件页：至少验证菜单注册、页面加载、权限与卸载后回收

## 参考

- `../skills/novusai-saas/references/testing-spec.md`
- `../skills/novusai-saas/references/browser-testing-spec.md`
