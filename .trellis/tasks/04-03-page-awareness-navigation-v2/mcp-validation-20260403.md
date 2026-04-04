# MCP Validation 2026-04-03

## Environment

- Frontend: `http://127.0.0.1:5666`
- Backend: `http://127.0.0.1:8000`
- Admin login: `admin / admin123456`
- Tenant admin user: `adminsss`
- Tenant code: `t1zc91teq`

## Admin Verification

### Verified

- Admin login succeeded and redirected to `/admin/ai/agents`.
- Admin dashboard page context now includes `navigation_context` in chat route/stream requests.
- Admin AI route request captured:
  - `POST /admin/ai/agent-chat/route`
  - `page_context.page_key=admin.dashboard`
  - `page_context.page_data.navigation_context.endpoint=admin`

### Failed

- From `/admin/dashboard`, sending `我想添加一个智能体` did **not** trigger cross-page navigation.
- Router selected agent `15 / 智能助手`, not a page-operation-focused chain.
- Stream request payload did **not** include `available_operations` in `page_context.page_data`.
- Follow-up explicit command `请直接在当前页面帮我找到新建智能体入口并打开，不要先问我类型` still only triggered repeated `get_page_context` calls.

### Evidence

- Route request `reqid=2749` selected:
  - `agent_id=15`
  - `agent_name=智能助手`
  - `routed_by=router`
- Stream request `reqid=2754` body contains:
  - `page_context.page_key=admin.dashboard`
  - `page_context.page_data.navigation_context`
  - missing `page_context.page_data.available_operations`
- Tool loop on second turn showed 3 completed `get_page_context` calls and no `navigate_menu`/`invoke_page_operation`.

## Tenant Verification

### Verified

- Tenant login on bare localhost is blocked by tenant-domain isolation as expected.
- Tenant auth API succeeds when `tenant_code=t1zc91teq` is supplied.
- Injecting valid tenant tokens allowed entering `/tenant/dashboard`.
- Tenant CommandBar search for `智能体` returned exactly one result.
- Clicking the result navigated to `/tenant/ai/agents`.
- Result stayed within tenant endpoint and did not jump to any `/admin/*` route.

## Current Conclusion

- Endpoint-scoped shared menu navigation works in real UI for tenant CommandBar search.
- Admin/tenant endpoint isolation behavior is correct.
- Initial admin runtime issue was confirmed: dashboard route used `context_only`, so `available_operations` was absent.
- After changing admin/tenant dashboard + analytics routes to `operate`, admin live requests now include:
  - `available_operations`
  - `list_available_menus`
  - `navigate_menu`
- Admin live runtime now successfully executes:
  - `get_page_context`
  - `pageop_list_available_menus`
  - `pageop_navigate_menu`
- Admin MCP flow now reaches `/admin/ai/agents` from `/admin/dashboard` in live chat.
- Remaining gap:
  - The continuation from navigated page into `create_record` / form opening is still not fully proven end-to-end in one turn.
  - Post-fix guidance has been strengthened in:
    - `page_operation_executor.py`
    - `page_tool_expander.py`
    - `page_context_executor.py`
  - Latest live run confirms:
    - dashboard request includes `available_operations`
    - planner no longer drops page tools to zero
    - live tool chain executes `pageop_list_available_menus` and `pageop_navigate_menu`
    - AI reaches `/admin/ai/agents` and responds that it can continue to open the create form
  - Latest additional MCP runs show a second blocker in the live environment:
    - some runs fail on `pageop_list_available_menus` or post-navigation follow-up operations with
      `page operation timeout (60s)` / `WebSocket connection may be disconnected`
    - the dashboard page sometimes shows `实时连接已断开`
    - this means the remaining instability is no longer route/planner exposure, but the live page-operation channel / room-join readiness in MCP runs
