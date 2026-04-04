# Page Awareness Navigation V2

## Purpose

补齐页面感知的跨菜单导航能力，让管理端与企业端页面 AI 不再局限于“当前页内操作”，而能在当前端点内安全地切页并继续执行目标页已有的 AI 操作。

## Goals

- 支持 `/admin` 与 `/tenant` 两端的菜单级导航。
- 支持 AI 判断“当前是否已在目标页”，避免无意义跳转。
- 严格基于当前用户可访问菜单集合执行导航，禁止隐式越权。
- 导航完成后把新页面的 `page_session_id` 与 `page_context` 回传给后端，支撑同一轮继续操作。

## Scope

- 前端共享菜单导航 helper
- `CommandBar` 与默认页面操作接入
- 跳页类页面操作统一返回新页摘要
- 后端 `PageOperationExecutor` 导航后上下文续接
- Router 跨页目标意图识别增强
- 前后端测试补齐

## Acceptance

- 管理端与企业端任意可操作页面都可通过 AI 发起菜单导航。
- 若用户已在目标页，不触发 `router.push`，而是直接继续目标页操作。
- 若目标菜单无权限、找不到或歧义，不跳转，返回明确失败或候选。
- 导航成功后，后续 `get_page_context` / `pageop_*` 使用新页面上下文与新会话。
