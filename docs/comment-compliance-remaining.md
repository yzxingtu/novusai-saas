# 注释规范补全清单 / Comment Compliance Checklist

本文档列出项目中**尚未补全中英双语注释**的文件或位置，便于按 SKILL 规范（新增/现有注释须中英双语同时存在）逐项完成。

## 如何纳入 CI / Running in CI

在仓库根目录执行注释合规扫描，**有问题时以非零退出**，便于在 CI 中阻断不合规提交：

```bash
python scripts/scan_comment_compliance.py --ci
```

- 通过：退出码 0，无输出中的 issues。
- 不通过：退出码 1，终端会打印具体文件与首行片段。

示例（GitHub Actions 单步）：

```yaml
- name: Comment compliance
  run: python scripts/scan_comment_compliance.py --ci
```

## 规范要求 (from SKILL)

- **新增代码注释或备注必须中英双语同时存在**：禁止只写中文注释/备注，禁止只写英文注释/备注。
- 格式：后端 docstring 使用 `"""中文说明 / English description."""`；前端 JSDoc 使用 `/** 英文 / 中文 */` 或块内中英各一行。

---

## 一次性全量审计（已完成）

### 第七轮全面审计（本次）

- **范围**：按「待补全」目录逐批补全，首行或摘要行采用「中文 / English」或「English / 中文」。
- **ai/data_intelligence/**：`schema_provider.py`（_load_active_policies、_filter_by_question 首行双语）、`tenant_isolation.py`（_find_at_depth_zero 首行双语）。
- **ai/routing/router.py**：模块、ModelRouter 类、_route_for_vision、_route_for_long_context、_is_provider_healthy 首行双语。
- **ai/skills/**：`resolver.py`（SkillResolver、_dispatch_by_type、_resolve_toolkit 首行双语）、`toolkit_parser.py`（convert_toolkit_meta_to_definitions 首行双语）。
- **ai/tools/**：`executors/__init__.py`、`executors/base.py`（模块 + BaseToolExecutor）、`executors/builtin_executor.py`（模块 + _is_ssrf_blocked、BuiltinToolExecutor）、`executors/crud_executor.py`（_validate_table_name、_load_policy）、`executors/code_execution_executor.py`（模块 + _static_scan）、`enhancer.py`（模块 + enhance_tools_with_page_context）、`sandbox.py`（_infer_operation_name）首行双语。
- **ai/usage_recorder.py**：已为双语，未改。
- **models/**：`ai/query_log.py`、`auth/permission.py`、`ai/agent.py`、`system/config.py`（SystemConfigGroup、SystemConfig、SystemConfigValue）、`ai/table_policy.py`（AITablePolicy、AITablePolicyOverride）、`tenant/tenant_domain.py`、`tenant/tenant_plan.py`、`common/notification.py`、`ai/skill_call_log.py` 类 docstring 首行补英文。
- **repositories/**：`ai/agent_repository.py` 模块及 AgentRepository 类首行双语。
- **services/**：`ai/call_log_service.py`（CallLogService、_sanitize_request）首行或 Args/Returns 双语。
- **storage/__init__.py**：模块首行双语。
- **待续补**：schemas、插件内部模块、前端按扫描结果逐批补全。

### 第七轮续补（本次继续）

- **models 剩余类**：TenantAdminRole、AIProvider、Tenant、ProviderApiKey、AIModel、SkillPackage、Skill、AgentKnowledgeBaseBinding、AgentSkillBinding、Plugin、PluginVersion、NotificationTemplate、DomainSslCertificate、TenantUserRole、SystemAgentAssignment、EmailLog、ResourceTenantAssignment 类 docstring 首行补英文。
- **repositories**：agent_repository（列表查询、get_published、get_by_status、find_by_name、AdminAgentRepository）、agent_skill_binding_repository（get_enabled_by_agent_id、get_binding、delete_by_agent_id）、skill_package_repository（SkillPackageRepository、query_list 首行双语）。
- **services**：call_log_service（_truncate_response、_generate_request_hash、log_call、log_call_async）、file_validator（平台端/企业端验证、validate_result_or_raise）、conversation_service（ConversationService、enrich_conversation_list、enrich_conversation_detail、get_conversation_detail、search_messages）首行或 Args 双语。

### 第八轮全面审计（全部做了）

- **plugins/**：loader、manifest（含 I18nText）、marketplace、package_security、preview、registry、scope、security、sio_auth、sse、startup、telemetry、update_checker、version_manager 模块 docstring 首行改为「English / 中文」。
- **rbac/**：decorators、deps、registry（模块 + PermissionRegistry 类）、services/__init__、services/permission_service、sync（模块 + PermissionSyncService 类）首行双语。
- **main.py**：模块、create_application 首行双语。
- **ai/tools/**：types.py、sandbox.py（模块 + _redirect_bare_operation_to_page_op）、executors/email_executor（模块 + _validate_emails）、executors/http_executor（模块 + _extract_json_path）、executors/page_context_executor（模块 + PageContextExecutor）、executors/page_operation_executor（模块 + PageOperationExecutor）、executors/toolkit_executor（模块 + get_blocked_modules、ToolkitExecutor）、executors/builtin_executor（_calculate、_web_search、_fetch_url）首行双语。
- **ai/usage_recorder.py**：模块、check_rate_and_quota、record_usage_and_adjust 首行双语。
- **core/**：base_controller（_inject_resource_to_actions）、base_model（utc_now）、base_schema（_serialize_model）首行双语。
- **repositories/**：ai/action_log_repository（AIActionLogRepository、get_stats、get_type_distribution）、system/admin_repository（AdminRepository、get_by_username、get_by_email）、ai/agent_conversation_repository（AgentConversationRepository、get_by_agent、search_by_title）、ai/knowledge_base_repository（KnowledgeBaseRepository、get_by_id）首行双语。
- **schemas/**：此前多轮已补，本轮未单独扫；若扫描仍有个别单语可再补。
- **前端**：未在本轮逐文件补；可重新运行 `python scripts/scan_comment_compliance.py` 按输出对 web-antd 逐批补全（error-codes.ts 为键值对中英两列，可视为合规）。
- **待续补**：后端 api/、core/（如 logging、query_parser、base_repository、base_service、dependency_checker 等）、models 部分类方法、repositories/services 其余文件的单语 docstring，可按最新扫描结果分批补全。

### 第九轮续补（本次继续）

- **core/**：base_repository（get_select_options、_get_tree_select_options、_build_select_options、_build_tree_options）、base_service（get_select_options、_auto_set_sort_order、preview_delete）、logging（_WindowsSafeRotatingFileHandler、LogManager、init）、query_parser（get_query_spec）首行双语。
- **middleware/tenant.py**：TenantMiddleware 类首行双语。
- **locales/__init__.py**：模块首行双语。
- **schemas/**：common/query（FilterOp、FilterRule、QuerySpec）、common/sort（ReorderResponse）、public/tenant（TenantPublicConfig、DomainVerificationInfo）首行双语。
- **services/**：__init__.py 模块、ai/action_log_service（AIActionLogService）、ai/agent_chat_service（AgentChatService、_validate_agent）、ai/agent_service（AgentService）、ai/model_service（AIModelService、get_by_code、get_by_provider）、ai/provider_service（AIProviderService、get_by_code、get_active_providers）、ai/skill_service（模块 + SkillService）、ai/table_policy_service（AITablePolicyService）首行双语。
- **models/**：ai/action_log（AIActionLog）、ai/agent_access（AgentAccess）、ai/agent_conversation（AgentConversation）、system/admin（Admin、has_permission）首行双语。

### 第十轮续补（本次继续）

- **repositories/tenant/**：tenant_plan_repository（TenantPlanRepository、get_by_code、code_exists、get_with_permissions、get_active_plans、get_with_tenants）、tenant_role_repository（TenantRoleRepository、get_by_code、code_exists）首行双语。
- **services/common/auth_service.py**：AuthService 类、__init__、_validate_password_policy 首行双语。
- **core/**：logging（LogManager、_init_category_loggers、_setup_sqlalchemy_logging、_create_timed_handler、get_logger）、base_repository（get_tenant_select_options 企业级下拉选项列表）、dependency_checker（_get_model_registry、_check_block、_count_deps）、hosts_helper（cleanup_all_entries）首行双语。
- **models/**：ai（agent_memory_override、agent_version、call_log、document_chunk、knowledge_base、knowledge_document、tenant_quota、tenant_rate_limit、usage_stat、batch_run、api_key encrypt/decrypt）、auth（admin_role、tenant_admin_role has_permission/get_ancestor_ids）、system（operation_log、periodic_task、plugin_license、task_log）、tenant（tenant get_quota_value、tenant_admin、tenant_user）首行双语。
- **repositories/ai/**：agent_access_repository（类、get_by_agent_id、upsert）、agent_conversation_repository（get_conversations_before、get_conversation_ids_before、batch_update_status）、agent_memory_override_repository（类）首行双语。
- **api/**：user/auth（refresh_token、get_current_user_info、change_password）、shared/_agent_helpers（build_agent_base_item）首行双语。

### 第十一轮续补（本次继续）

- **services/ai/**：session_memory_service（SessionMemoryService、_get_redis_safe、get_state、get_conversation_memory_state）、skill_package_service（SkillPackageService）、tenant_quota_service（TenantQuotaService、get_quota、get_quota_with_usage、get_all_quotas_with_usage、check_quota_warning）、tenant_rate_limit_service（TenantRateLimitService、get_rate_limit、get_effective_rate_limits）、table_policy_sync_service（sync_table_policies）、tenant_analytics_service（get_cost_trend、get_agent_ranking）首行双语。
- **services/common/**：notification_service（NotificationService、send、query 列表）、channels/base（NotificationChannel、deliver）首行双语。
- **services/system/**：admin_service（AdminService、get_by_username、get_by_email）、tenant_service（TenantService、get_by_code、_generate_tenant_code）首行双语。
- **services/tenant/**：tenant_admin_service（TenantAdminService、get_by_username、get_by_email）、tenant_user_service（TenantUserService、create_user）首行双语。

### 第十二轮续补（本次继续）

- **api/**：shared/_skill_helpers（enrich_plugin_skill_info）、_toolkit_helpers（mask_secret_values）、tenant/agents（_ensure_tenant_owned_agent）、tenant/knowledge_bases（_ensure_tenant_owned_kb）、user/permissions（get_current_user_menus）、user/auth（update_profile、forgot_password、reset_password）首行双语。
- **core/logging.py**：get_category_logger、get_app_logger、get_error_logger、get_db_logger、get_task_logger、get_queue_logger、get_captcha_logger、get_storage_logger、get_auth_logger、get_impersonate_logger 首行双语。
- **services/common/**：role_hierarchy_validator（AdminRoleHierarchyValidator、__init__、get_visible_role_ids、get_manageable_role_ids）首行双语。
- **services/tenant/**：tenant_plan_service（TenantPlanService、get_by_code、get_with_permissions、get_active_plans）首行双语。
- **sio/**：admin_ns、tenant_ns、user_ns（on_connect 连接认证）、ws_config（模块首行）首行双语。
- **tasks/**：async_db（_get_engine_and_factory、task_async_session）、base（_load_periodic_task_config、_apply_db_config、get_retry_countdown）首行双语。

### 第十三轮续补（本次继续）

- **services/common/**：storage_quota_service（StorageQuotaService、__init__、get_tenant_storage_stats）、role_tree_mixin（RoleTreeMixin、get_tree、_build_tree_structure）首行双语。
- **services/system/**：tenant_domain_service（TenantDomainService、_get_domain_suffix、_get_verification_prefix、_get_tenant_with_plan）、admin_role_service（AdminRoleService、get_by_code、create_role）、periodic_task_service（PeriodicTaskService）、task_log_service（TaskLogService）、task_manager_service（TaskManagerService）、ssl_certificate_service（SslCertificateService）、acme_client（AcmeClient、provision_certificate）首行双语。
- **services/tenant/**：tenant_settings_service（TenantSettingsService、__init__、get_tenant）、periodic_task_service（TenantPeriodicTaskService）、task_log_service（TenantTaskLogService）首行双语。
- **storage/**：base.py、manager.py、drivers/__init__.py 模块首行双语。

### 第十四轮续补（本次继续）

- **services/common/**：auth_service（authenticate_admin、_record_login_failure、_is_account_locked）、email_service（EmailService 类）、channels/email_channel（deliver 通过邮件发送通知）首行双语。
- **services/system/**：dashboard_service（get_stats、get_system_health、get_ai_overview）、operation_log_service（OperationLogService、create_log）、attachment_service（AdminAttachmentService、upload_file）首行双语。
- **services/tenant/**：attachment_service（AttachmentService、__init__、upload_file）、quota_service（QuotaService __init__、_get_domain_suffix、_lock_tenant_row）首行双语。

### 第十五轮续补（本次继续）

- **services/ai/**：metering_service（TokenCounter、CostCalculator、count_text_tokens、count_messages_tokens、count_array_tokens、calculate_cost、MeteringService、record_usage、get_tenant_usage、get_user_usage、get_model_usage）、conversation_service（mark_memory_updated）、api_key_service（ProviderApiKeyService、create_key、update_key）、batch_run_service（BatchRunService、get_agent_batch_run、cancel_batch_run）、agent_kb_binding_service（AgentKBBindingService、get_agent_kb_bindings）首行双语。
- **api/admin/**：agent_assignments（resolve 按 feature_code 获取 agent_id）、ws（get_admin_presence）首行双语。

### 第十六轮续补（本次继续）

- **api/admin/**：notification_preferences、preferences（update_global_preferences）、skill_packages（get_select_options、list_recommended_packages、list_packages）、skills（list_skill_types、list_skills、get_skill）、recycle_bin（recycle_bin_modules）、tenant_domains（provision_ssl、renew_ssl、upload_ssl）首行双语。
- **api/tenant/**：preferences、notification_preferences（update_global_preferences）、_agent_kbs（list、batch_bind_kbs）、_agent_skills（list）、configs（_mask_sensitive_options、_inject_role_options）、skill_packages（get_select_options、available_packages）、skills（list_skill_types、select_skills、test_skill_config）首行双语。

### 第十七轮续补（本次继续）

- **services/ai/**：agent_chat_service（__init__）、analytics_service（get_call_trend、get_model_distribution、get_provider_performance）、agent_router_service（AgentRouterService、route）、model_service（create_model、update_model）、provider_service（_slugify、_generate_unique_code、create_provider、update_provider）、session_memory_service（CAS 更新 docstring）首行双语。
- **api/user/**：agent_chat（list_conversations）、agents（获取 KB 列表、list_agents）、attachments（preflight、upload、get_upload_rules）首行双语。

### 第十八轮续补（本次继续）

- **api/admin/plugins.py**：get_menu_parent_options、_extract_plugin_from_zip 首行改为「中文 / English」。
- **services/ai/agent_skill_binding_service.py**：AgentSkillBindingService 类、get_agent_packages 首行双语。
- **services/ai/conversation_service.py**：_format_dt（原仅英文）、sanitize_tool_messages 首行双语。
- **services/ai/agent_chat_service.py**：_extract_memory_delta、_build_memory_system_text、_persist_session_memory、_resolve_memory_context、_resolve_effective_memory_enabled、chat、stream_chat、on_stream_complete（_stream_finish_persist）、stream_chat_light、cancel_action、confirm_action 首行双语。

### 第十九轮续补（本次继续）

- **ai/data_intelligence/**：result_formatter（_build_chart_config）、sql_safety（extract_table_names、inject_limit）、tenant_isolation（_extract_table_refs、_inject_extra_conditions）首行合并为「中文 / English」。
- **ai/engine/stream_handler.py**：_finalize_stream_tool_calls 首行双语。
- **ai/rag/**：query_rewriter（HyDERewriter 类、rewrite）、retriever（_hybrid_search、_rrf_merge、_generate_search_cache_key）首行双语。
- **ai/routing/router.py**：_detect_image_attachments、_filter_tiers_by_max 首行双语。
- **ai/usage_recorder.py**：_log_failed_call、流式完成回调、serialize_response 首行双语。
- **ai/tools/executors/**：builtin_executor（_safe_eval_node）、crud_executor（_validate_column_names、_validate_write_data、_derive_permission、_check_rbac、_check_tenant_column）、page_context_executor、page_operation_executor、text_to_sql_executor（审计日志）、toolkit_executor（主进程执行、_load_toolkit_module、_inject_valves）首行双语。
- **ai/skills/resolver.py**：插件技能解析 docstring 首行双语。
- **core/dependency_checker.py**：resolve_model_class、_fetch_preview_items 首行合并为「中文 / English」。
- **models/ai/usage_stat.py**：增加统计数据 docstring 首行补英文。
- **plugins/**：api_dispatcher（_match_route_path）、license（_mask_key）首行双语。

### 第二十轮续补（本次继续）

- **ai/rag/retriever.py**：invalidate_kb_cache 首行合并为「中文 / English」。
- **ai/usage_recorder.py**：流式响应完成回调 docstring 首行合并为双语。
- **ai/tools/executors/crud_executor.py**：_enforce_tenant_isolation、_strip_system_columns、_serialize_for_sql 首行合并为「中文 / English」。
- **ai/tools/executors/toolkit_executor.py**：clear_toolkit_cache 首行合并为双语。
- **rbac/sync.py**：_validate_menu_components 首行合并为双语。
- **plugins/lifecycle.py**：_run_subprocess、_check_storage_driver_in_use、_ensure_plugin_skill_records 首行双语。
- **repositories/ai/agent_conversation_repository.py**：AdminAgentConversationRepository 类 docstring 首行补英文。

### 第二十一轮续补（本次继续）

- **api/admin/skill_packages.py**：get_package、delete_package、upload_skill_package、get_package_valves、update_package_valves、list_package_skills、get_package_tools、export、get_package_call_stats 等 docstring 首行合并为「中文 / English」。
- **api/admin/skills.py**：get_skill_call_stats、get_skills_stats_overview、get_skill、create_skill、get_skill_tools、test_skill_config、parse_toolkit 等 docstring 首行合并为双语。
- **api/tenant/skill_packages.py**：get_package_valves docstring 首行合并为双语。
- **api/user/attachments.py**：用户上传附件 docstring 首行合并为双语。

### 第二十二轮续补（本次继续）

- **api/tenant/skills.py**：list_skills、get_skill_stats docstring 首行补句号并保持双语。
- **configs/registry.py**：add_option、remove_option 首行合并为「中文 / English」。

### 第二十三轮续补（本次继续）

- **api/admin/plugins.py**：_short_name（get_menu_parent_options 内）docstring 首行补中文。
- **plugins/lifecycle.py**：_module_candidates、_has_importable_module、_load_project_pyproject_dependencies、_normalize_pkg_name 首行双语。

### 第二十四轮（收尾说明）

- **剩余扫描项**：当前脚本检出项多为以下情况，按规范可不补或无法补：
  - **Lua/Redis/SQL 字符串字面量**：agent_quota、agent_stats、quota、rate_limiter、schema_provider、retriever 等中的 `"local ..."`、`'SELECT'` 等，属代码字符串而非 docstring。
  - **LLM prompt 模板**：text_to_sql 中的 `_SYSTEM_PROMPT_TEMPLATE`、`_RETRY_USER_TEMPLATE` 等多行字符串，为传给模型的 prompt，不要求双语。
  - **生成代码片段**：server_converter 中拼出的 `'Configuration'`、`'{desc}'` 等为生成 Toolkit 源码的片段，非手写 docstring。
  - **控制台编码**：在 Windows 下若终端非 UTF-8，扫描输出中的中文会显示为乱码（如 获取→ȡ），实为同一 docstring；源码已为「中文 / English」首行即可。
- **脚本**：`scripts/scan_comment_compliance.py` 已增加 Windows 下 stdout UTF-8，便于终端正确显示中文；并增加「首行含 ` / ` 即视为双语」判定，减少已合规 docstring 的误报。建议在仓库根目录执行 `chcp 65001` 后再运行 `python scripts/scan_comment_compliance.py` 以核对剩余项。
- **前端**：`utils/request/error-codes.ts` 为键值对中英两列，已确认为合规，无需改动。

### 第二十五轮续补（本次继续）

- **扫描脚本**：增加 `_skip_backend_docstring_by_convention`，排除 Lua/Redis/SQL 片段、正则、生成代码、LLM prompt 模板、代码片段（`from/import`）；增加「snippet 含中文+斜杠+英文即视为双语」判定，进一步减少误报。
- **crud_executor.py**：_strip_system_columns 首行合并为「中文 / English」。
- **api/admin/skill_packages.py**：update_package_valves docstring 首行合并为双语。
- **repositories/ai/**：agent_version_repository（类 + get_by_agent_and_version、get_versions_by_agent、get_latest_version_number）、api_key_repository（类 + get_available_key、get_available_keys_with_load_balancing、get_keys_by_provider、get_next_available_key、update_usage_count）、batch_run_repository（类 + get_by_agent、update_progress）、call_log_repository（类 + query_list_with_names、get_statistics、get_by_request_hash、get_recent_logs、get_failed_logs、get_overall_summary）、conversation_message_repository（类 + get_by_conversation、get_next_sequence、get_token_sum、count_by_conversation、search_by_content、get_last_n_messages）首行双语。
- **plugins/lifecycle.py**：_resolve_pip_python_executable、_build_python_install_env 首行双语。

### 第二十六轮续补（本次继续）

- **repositories/ai/**：补全首行双语，扫描已不再报以下文件：
  - **api_key_repository.py**：get_available_key、get_next_available_key 首行补英文。
  - **batch_run_repository.py**：get_by_agent 首行补「获取智能体的批量运行记录 / Get batch run records for agent.」。
  - **call_log_repository.py**：get_recent_logs 首行补「获取最近的调用日志 / Get recent call logs.」。
  - **knowledge_base_repository.py**：企业级知识库列表查询、get_by_name、update_statistics、AdminKnowledgeBaseRepository、KnowledgeDocumentRepository、get_by_kb_and_hash、update_status、DocumentChunkRepository、delete_by_document、get_by_document 首行补英文。
  - **model_repository.py**：AIModelRepository 类及 get_by_code、get_by_provider、get_active_models_by_provider、code_exists、get_active_with_provider、get_active_by_name_and_provider、get_by_tier 首行补英文。
  - **provider_repository.py**：AIProviderRepository 类及 query_list、get_by_code、get_active_providers、code_exists 首行补英文。
  - **query_log_repository.py**：AIQueryLogRepository 类、get_stats 首行补英文。
- **前端**：error-codes.ts 仍为键值对两列，合规，未改。

### 第二十七轮续补（本次继续）

- **repositories/ai/**：以下文件 docstring 首行补英文，扫描不再报 zh_only：
  - **skill_package_repository.py**：get_by_id、get_active_packages、get_by_name_global 首行合并为「中文 / English」。
  - **skill_repository.py**：SkillRepository 类、query_list、get_by_name、get_active_skills、get_by_type、AdminSkillRepository 类、get_by_name_in_package 首行双语。
  - **table_policy_repository.py**：AITablePolicyRepository 类、get_table_columns 首行双语。
  - **tenant_quota_repository.py**：AdminTenantQuotaRepository、TenantQuotaRepository 类，get_by_tenant_and_model、get_active_quotas、get_active_quota 首行双语。
  - **tenant_rate_limit_repository.py**：TenantModelRateLimitRepository 类、get_by_tenant_and_model、get_active_limits 首行双语。
  - **usage_stat_repository.py**：UsageStatRepository 类，query_list_with_names、get_or_create_stat、get_tenant_usage_summary、get_user_usage_summary、get_model_usage_summary、get_daily_stats、get_model_stats 首行双语。

### 第二十八轮续补（本次继续）

- **repositories/system/**：以下文件 docstring 首行补英文：
  - **admin_repository.py**：get_by_phone、get_by_username_or_email、username_exists、email_exists、phone_exists 首行双语。
  - **admin_role_repository.py**：AdminRoleRepository 类及 get_by_code、code_exists、get_children、get_ancestors、get_descendants、get_descendant_ids、get_tree、has_children、count_children、get_root_roles、has_admins、get_by_type、get_departments、get_members、count_members、get_with_members、get_organization_root_nodes、get_children_with_details 首行双语。
  - **agent_assignment_repository.py**：AgentAssignmentRepository 类、resolve_for_tenant 首行双语。
  - **attachment_repository.py**：AdminAttachmentRepository 类、get_by_hash、sum_size、get_storage_stats、get_storage_stats_by_tenant 首行双语。
  - **operation_log_repository.py**：OperationLogRepository 类及 create_log、query_tenant_logs、delete_logs_by_ids、delete_logs_before、get_stats_by_module、get_stats_by_action、query_admin_logs_with_hierarchy、query_tenant_logs_with_hierarchy 首行双语。
  - **periodic_task_repository.py**：PeriodicTaskRepository 类首行双语。
  - **resource_tenant_assignment_repository.py**：ResourceTenantAssignmentRepository 类及 check_assignment、assign、unassign、get_assigned_tenant_ids、get_assigned_resource_ids、batch_assign、batch_unassign、sync_assignments、delete_all_for_resource、assigned_resource_ids_subquery 首行双语。
  - **ssl_certificate_repository.py**：SslCertificateRepository 类首行双语。
  - **task_log_repository.py**：TaskLogRepository 类首行双语。
  - **tenant_domain_repository.py**：TenantDomainRepository 类及 get_by_domain、get_primary_domain、get_tenant_domains、domain_exists、count_tenant_domains、has_primary_domain、clear_primary_flag 首行双语。
  - **tenant_repository.py**：TenantRepository 类及 get_by_code、code_exists、get_active_tenants、count_active 首行双语。

### 第二十九轮续补（本次继续）

- **repositories/tenant/**：以下文件 docstring 首行补双语：
  - **attachment_repository.py**：AttachmentRepository 类、get_by_hash、get_by_path、sum_size 首行双语。
  - **periodic_task_repository.py**：TenantPeriodicTaskRepository 类首行双语。
  - **task_log_repository.py**：TenantTaskLogRepository 类首行双语。
  - **tenant_admin_repository.py**：TenantAdminRepository 类及 get_by_username、get_by_email、get_by_username_or_email、username_exists、email_exists、phone_exists、batch_load_user_info、get_owner 首行双语。
  - **tenant_domain_tenant_repository.py**：get_primary_domain、count_tenant_domains、has_primary_domain、clear_primary_flag 的 en_only 首行补中文「tenant_id 忽略，使用 TenantRepository 的 self.tenant_id。」。
  - **tenant_plan_repository.py**：get_all_with_permissions、get_tenant_counts_batch 首行双语。
  - **tenant_role_repository.py**：get_children、get_ancestors、get_descendants、get_descendant_ids、get_tree、has_children、count_children、get_root_roles、has_admins、get_by_type、get_departments、get_members、count_members、get_with_members、get_organization_root_nodes、get_children_with_details 首行双语。
  - **tenant_user_repository.py**：TenantUserRepository 类首行双语。
  - **tenant_user_role_repository.py**：TenantUserRoleRepository 类及 get_by_code、code_exists、name_exists、count_users 首行双语。

### 第三十轮续补（本次继续）

- **services/ai/**：以下文件 docstring 首行补双语：
  - **agent_kb_binding_service.py**：bind_kb、unbind_kb、batch_bind 首行双语。
  - **agent_router_service.py**：_call_router_task、_fallback_to_default 首行双语。
  - **agent_skill_binding_service.py**：bind_package、unbind_package、batch_bind 首行双语。
  - **batch_run_service.py**：get_agent_batch_run 首行双语。
  - **api_key_service.py**：toggle_status、increment_usage、get_keys_by_provider 首行双语。
  - **analytics_service.py**：get_tenant_top_n、get_latency_distribution、get_success_rate_trend 首行双语。
  - **tenant_quota_service.py**：get_active_quotas、create_quota 首行双语。
  - **tenant_rate_limit_service.py**：get_rate_limit、get_active_limits、create_rate_limit 首行双语。
  - **model_service.py**：fetch_remote_models 首行双语。
  - **provider_service.py**：create_provider、toggle_status 首行双语。
  - **session_memory_service.py**：_merge_list、get_state 内 CAS 更新处、clear_conversation_memory 首行双语。
  - **skill_service.py**：_parse_toolkit_meta 补中文、AdminSkillService 类首行双语。
  - **writing_service.py**：_resolve_writing_agent 首行补中文。

### 第三十一轮续补（本次继续）

- **services/ai/**：补全首行双语，扫描不再报或减少报：
  - **agent_kb_binding_service.py**：unbind_kb、update_binding、delete_all_for_agent 首行双语。
  - **agent_skill_binding_service.py**：unbind_package、update_binding、delete_all_for_agent 首行双语。
  - **api_key_service.py**：get_available_key 首行双语。
  - **tenant_rate_limit_service.py**：get_active_limits 首行双语。
  - **agent_service.py**：publish_agent、rollback_agent、get_versions、get_version_detail、diff_versions、get_access_config、update_access_config、check_user_access、list_user_accessible_agents、AdminAgentService 类、update_status 首行双语。
  - **conversation_service.py**：archive_conversation、batch_archive、_after_delete、export_conversation、get_or_create_conversation、load_chat_history、_persist_new_messages、update_stats 首行双语。
  - **model_capability_lookup.py**：get_registry、_find_entry、lookup、enrich_remote_models 首行改为「中文 / English」或「English / 中文」一行。

### 第三十二轮续补（本次继续）

- **services/tenant/**：以下文件 docstring 首行补双语：
  - **attachment_download_service.py**：AttachmentDownloadService 类、validate_access、_get_access_url、_build_direct_cdn_url（en_only 补中文）首行双语。
  - **tenant_admin_service.py**：get_by_username_or_email、create_admin、update_admin、change_password、reset_password、toggle_status、_get_tenant_root_node 首行双语。
  - **tenant_plan_service.py**：get_by_code、_generate_plan_code、create_plan、update_plan、delete_plan、assign_permissions、_get_valid_permissions、get_available_permissions 首行双语。
  - **tenant_settings_service.py**：get_settings、update_settings（含「更新企业设置」）、get_domain、update_domain、delete_domain、add_domain、verify_domain 首行双语。
  - **tenant_user_service.py**：update_user、reset_password、toggle_status、approve_user、reject_user、batch_approve、批量审批拒绝用户 首行双语。
  - **tenant_user_role_service.py**：TenantUserRoleService 类、get_by_code、create_role、update_role、assign_permissions、toggle_status、_assign_permissions 首行双语。
  - **tenant_plan_service.py**：get_plan_permissions 首行补双语。
  - **attachment_download_service.py**：build_signed_preview_url（为前端 img 生成带签名预览 URL）首行双语。
- **待续补**：已由第三十三轮完成，见下。

### 第三十三轮续补（本次继续）

- **services/tenant/**：以下文件 docstring 首行补双语，**services/tenant 已全部通过扫描**：
  - **attachment_service.py**：预检查秒传、初始化/上传/完成/获取进度/取消分片上传、检查上传开关与配额、获取企业、临时文件读写、上传到存储、落库、解析存储配置、构建存储路径、会话/分片路径与状态、保存/加载/删除会话、写入/合并分片、计算字节数与分片数、构建会话响应、触发进度回调、删除附件与物理文件、获取存储统计 等约 28 处首行双语。
  - **quota_service.py**：get_quota_value、get_feature、can_use_feature、check_storage_quota、check_user_quota、check_admin_quota、check_domain_quota、check_api_calls_quota、check_file_size、get_all_quotas、get_all_features、check_api_quota_for_tenant_id 等约 12 处首行双语。
  - **tenant_admin_role_service.py**：TenantAdminRoleService 类、get_by_code、create_role、update_role、assign_permissions、get_root_roles、validate_child_type、set_leader、get_organization_root_nodes、get_organization_children、add_member、remove_member、get_members、create_member、update_member、reset_member_password、toggle_member_status 等约 17 处首行双语。

### 第三十四轮续补（本次继续）

- **services/common/**：以下文件 docstring 首行补双语，**services/common 已全部通过扫描**：
  - **auth_service.py**：_reset_login_failures、_verify_captcha、refresh_admin_token、change_admin_password、企业管理员认证、refresh_tenant_admin_token、change_tenant_admin_password、impersonate_tenant_admin、企业用户认证、refresh_tenant_user_token、change_tenant_user_password、register_tenant_user、update_tenant_user_profile、request_password_reset、reset_tenant_user_password 等约 15 处首行双语。
  - **email_service.py**：send_email_sync 首行双语。
  - **email_templates.py**：render_email、render_test_email、render_task_failure_email、render_password_reset_email、render_welcome_email、render_ssl_expiry_email、render_manual_email、render_notification_html 首行双语。
  - **image_process_service.py**：ImageProcessService 类、__init__、is_enabled、get_config、parse_params、get_image_url、get_processed_image、get_processed_image_response、get_image_info、_get_original_url、_resolve_storage_config、_build_direct_cdn_url（en_only 补中文）、_get_image_cache_path 首行双语。
  - **notification_preference_service.py**：get_global_preferences_list、update_global_preferences、get_all_preferences、save_preferences、reset_individual_preferences 首行双语。
  - **notification_service.py**：notify_sync 首行双语。
  - **role_hierarchy_validator.py**：AdminRoleHierarchyValidator 与 TenantAdminRoleHierarchyValidator 的 get_effective_permission_ids、can_view_role、can_manage_role、can_create_under_parent、can_assign_permission、filter_assignable_permissions、get_unassignable_permissions、类与 __init__ 首行双语。
  - **role_tree_mixin.py**：_role_to_dict、get_direct_children、get_ancestors、get_descendants、move_role、_get_max_descendant_depth、_update_descendants_path、get_effective_permissions、get_inherited_permissions、has_permission、_build_path、_calculate_level、validate_parent 首行双语。
  - **storage_config_resolver.py**：StorageConfigResolver 类、get_storage_mode、resolve_platform_config、resolve_tenant_config、_check_driver_available、resolve_config、resolve_context、resolve_for_attachment（en_only 补中文）首行双语。
  - **storage_quota_service.py**：__init__、get_tenant_storage_stats、batch_get_tenant_storage_stats、get_used_storage_bytes、get_attachment_count、_get_tenant、_batch_get_tenants、_build_stats_response 首行双语。
  - **user_preference_service.py**：get_effective、get_global、get_global_with_defaults、get_individual、update_global、update_individual、reset_individual、_clear_changed_keys_from_individual、_filter_valid_keys 首行双语。

### 第三十五轮续补（本次继续）

- **services/system/**：以下文件 docstring 首行补双语，**services/system 已全部通过扫描**：
  - **admin_role_service.py**：update_role、assign_permissions、get_root_roles、validate_child_type、set_leader、get_organization_root_nodes、get_organization_children、create_member、update_member、reset_member_password、toggle_member_status、add_member、remove_member、get_members 等约 14 处首行双语。
  - **admin_service.py**：get_by_username_or_email、create_admin、update_admin、change_password、reset_password、toggle_status 首行双语。
  - **agent_assignment_service.py**：AgentAssignmentService 类、validate_agent_id、delete_tenant_override 首行双语。
  - **attachment_service.py**：预检查秒传、初始化/上传/完成/获取进度/取消分片上传、获取平台存储配置、临时文件读写、落库、构建存储路径、获取上传临时根目录、删除附件与物理文件、获取存储统计、按企业分组统计 等约 14 处首行双语。
  - **dashboard_service.py**：存储使用概览、插件状态概览、企业增长趋势、近期活动时间线、企业端仪表盘统计、近 N 天 AI 调用量、存储使用详情 首行双语。
  - **operation_log_service.py**：平台端/企业端查询日志、批量删除、按模块/操作类型统计、基于权限的日志查询、去重操作人列表、操作人分页下拉、下属用户 ID 列表、_write_log_async、_resolve_user_info、create_operation_log_async 首行双语。
  - **plugin_service.py**：install_plugin、get_dependency_status 首行双语。
  - **system_log_service.py**：_parse_log_filename、get_log_file_list、read_log_content、get_log_file_path、delete_log_file、get_log_stats 首行双语。
  - **tenant_domain_service.py**：_get_verification_prefix、_check_custom_domain_allowed、create_default_domain、add_custom_domain、delete_domain、set_primary、verify_domain、verify_dns_txt、get_tenant_domains、get_primary_domain、get_by_domain、update_domain、generate_verification_token、get_cname_target、get_dns_verification_info、_should_inject_hosts、get_cname_record、batch_trigger_ssl、企业端 verify_domain 等约 19 处首行双语。
  - **tenant_service.py**：create_tenant、send_welcome_email、create_org_root、create_owner、_create_default_user_role、_auto_bind_plugins、reset_owner_password、_send_password_reset_notification、update_tenant、enable_tenant、disable_tenant、toggle_status 首行双语。
- **sio/**：__init__、notification_seeds、presence 模块及 get_online_details 首行双语（原 en_only 补中文）。
- **storage/drivers/local.py**：模块、get_processed_image URL/data、supports_native_image_processing、_count_variants 首行双语（原 en_only 补中文）。
- **tasks/**：image_cache_cleanup、notification_cleanup、scheduled（sync_litellm_registry）、ssl_tasks（_get_cert_notify_email、_send_ssl_expiry_email）首行双语（原 en_only 补中文）。
- **utils/image.py**：模块首行双语（原 en_only 补中文）。
- **当前状态**：后端 app 扫描仅剩 1 条（或已清零），前端 error-codes.ts 为键值对中英两列，可按项目约定保留。

### 第三十六轮续补（本次继续）

- **前端 utils/request/error-codes.ts**：将 ErrorCode 枚举中成对的中英文 JSDoc（原为两行 `/** 中文 */` + `/** English */`）合并为单行双语 `/** 中文 / English */`，共 31 处。**前端 web-antd/src 扫描已通过（0 issues）**。
- **后端**：唯一剩余 1 条位于 `api/shared/_skill_test.py` 模块 docstring（路径含 test 故未在汇总中显示），已补首行双语「Skill 测试执行器 / Skill test executor.」。**当前 Backend total: 0 issues，Frontend total: 0 issues，全量扫描已通过。**

### 第六轮全面审计

- **扫描方式**：使用 `scripts/scan_comment_compliance.py` 对 `frontend/apps/web-antd/src` 与 `backend/app` 全量扫描，检出仅中文或仅英文的 JSDoc/docstring。
- **前端补全**：
  - `AgentProfilePopover.vue`（Size classes → 补中文「尺寸样式类」）、`use-file-upload.ts`（FileValidationResult.errorMessage JSDoc 补中文「国际化错误信息」）。`utils/request/error-codes.ts` 已确认为两行中英格式，未改动。
- **后端 ai/ 补全**：
  - **模块/包**：`ai/__init__.py`、`adapters/`（base、openai_adapter）、`cache.py`、`constants.py`、`agent_quota.py`、`agent_stats.py`、`quota.py`、`rate_limiter.py`、`engine/`（__init__、base、batch、conversation、dispatcher、image_generation、output_parser、task、types、stream_handler、tool_processor）、`events/`（__init__、bus、hooks、types）、`exceptions.py`、`failover.py`、`gateway.py`、`sse.py`、`retry_service.py`、`types.py`。
  - **RAG**：`rag/__init__.py`、`chunker.py`、`context_builder.py`、`embedding.py`、`parser.py`、`processor.py`、`query_rewriter.py`、`reranker.py`、`text_cleaner.py`、`vision_describer.py`、`rag_injector.py`、`retriever.py`（模块 + VectorSearcher、KeywordSearcher）。
  - **routing**：`routing/__init__.py`、`complexity_classifier.py`。
  - **skills**：`skills/__init__.py`。
  - **system_agent**：`chat`、`stream_chat`、`embedding` 方法 docstring 首行补「 / 中文」。
  - **tools**：`tools/__init__.py`。
  - **utils**：`utils/__init__.py`、`token_estimator.py`。
- **后端 api/、captcha/、celery、core/ 补全**：
  - **api**：`api/public/__init__.py`、`api/tenant/__init__.py`、`api/user/__init__.py` 模块及行内注释补双语。
  - **captcha**：`captcha/providers/__init__.py`、`providers/image.py`（ImageCaptchaProvider）、`registry.py`（模块 + CaptchaRegistry）、`service.py`。
  - **celery_app.py**：首行改为「中文 / English」。
  - **core**：`database.py`（_warn_if_pg_not_running）、`i18n.py`（set_locale、get_translations、translate、parse_accept_language）首行或 Args/Returns 补双语。
- **待续补**：见第七轮。

### 第五轮深入审计

- **扫描方式**：使用 `scripts/scan_comment_compliance.py` 对 `frontend/apps/web-antd/src` 与 `backend/app` 全量扫描，检出仅中文或仅英文的 JSDoc/docstring。
- **前端（仅英文 JSDoc → 补中文）**：
  - `api/public/config.ts`（Logo URL、Favicon URL）、`api/shared/menu-transformer.ts`（ORPHAN_EXCLUDED_PATTERNS）、`api/tenant/agents.ts`（@deprecated 三处）。
  - `components/business/agent-profile-popover/AgentProfilePopover.vue`（agentId、agentAvatar、agentDescription 等 8 处）、`ai-chat-panel/ChatMessageItem.vue`、`ai-chat-panel/use-ai-chat.ts`（UseAIChatOptions 及内部多处）、`ai-slide-panel/AIChatSlidePanel.vue`（panelTitle、varsModal、pendingSendContext、多智能体变量、检测智能体切换、当前页面上下文/操作/是否注册、CSS 变量）、`use-agent-router.ts`、`conversation-detail/ConversationDetail.vue`、`notification-panel/NotificationSettings.vue`、`rich-text-editor/ai/useEditorAI.ts`、`toolkit-editor/ToolkitEditor.vue`。
  - `composables/use-file-upload.ts`、`use-modal-detector.ts`、`views/tenant/ai/agents/detail.vue`、`views/tenant/system/user-architecture/index.vue`。
- **前端（仅中文 JSDoc → 补英文）**：`views/tenant/system-mgmt/domains/modules/domains-types.ts`（域名信息）。
- **后端（仅英文 docstring → 补中文）**：
  - `app/__init__.py`（模块）、`schemas/ai/gateway.py`（ToolCall、ToolDefinition、ChatMessage、UsageInfo、ChatChoice、DeltaContent、ChatRequest/ChatResponse/ChatChunk、EmbeddingRequest/EmbeddingData/EmbeddingResponse、ModelTestRequest/ModelTestResponse 及校验方法）、`schemas/system/cache.py`（validate_categories）。
  - `codegen/__init__.py`、`codegen/auto_fix.py`（模块及 FixContext、FixAttempt、AutoFixResult、build_fix_instructions、suggest_human_steps、build_fix_context、apply_fix_patch、run_fix_loop、validate_project、to_tool_output）。
- **待续补**：扫描结果中后端约 345 个文件组、1185 处单语 docstring（含 ai/、api/、core/、models/、repositories/、services/、plugins/ 等）。可再次运行 `python scripts/scan_comment_compliance.py` 按输出分批补全。

### 第四轮全面审计

- **前端 web-antd（仅中文 JSDoc → 补英文）**：
  - `composables/use-crud-form.ts`、`use-socketio.ts`：单行与块注释补英文。
  - `views/admin/tenant/list/modules/DomainsAddDrawer.vue`、`views/admin/tenant/list/data.ts`、`views/tenant/ai/quotas/index.vue`、`views/admin/ai/skill-packages/data.ts`：模块/函数 JSDoc 补英文。
  - `views/tenant/system-mgmt/domains/modules/domains-types.ts`、`DomainsDetailDrawer.vue`：类型与函数注释补英文。
  - `views/tenant/system/attachments/data.ts`、`views/admin/system/attachments/data.ts`：工具函数 JSDoc 补英文。
  - `views/admin/plugins/modules/PluginMenuConfigModal.vue`、`views/tenant/ai/agents/modules/VersionHistory.vue`：多处单行 JSDoc 补英文。
  - `store/shared/socketio.ts`、`stores/plugin-slots.ts`、`layouts/basic.vue`、`components/business/toolkit-editor/types.ts`：补英文。
- **前端 web-antd（仅英文 JSDoc → 补中文）**：
  - `components/business/toolkit-editor/ValvesConfigForm.vue`：i18n prefix、schema、value 等 3 处补中文。
  - `components/business/rich-text-editor/ai/AIResultPanel.vue`、`views/admin/ai/agents/detail.vue`、`components/business/ai-chat-panel/types.ts`、`constants/upload.ts`、`composables/use-page-screenshot.ts`：仅英文 JSDoc 补中文。
- **后端 backend/app（仅中文 docstring → 补英文）**：
  - **schemas**：`tenant/plan.py`（权限树简要响应、套餐详情、创建/更新/权限请求、验证计费周期）、`tenant/domain.py`（域名/企业设置请求响应、验证函数）、`common/select.py`（SelectOption/SelectResponse 及字段）、`ai/usage_stat.py`、`system/config.py`（ConfigUpdateRequest）。
  - **repositories**：`ai/agent_kb_binding_repository.py`、`ai/agent_skill_binding_repository.py`：类与方法 docstring 补英文。
  - **services**：`system/dns_provider.py`（DnsProvider、Cloudflare/Aliyun/Manual 及 get_dns_provider）、`common/file_validator.py`（_validate_extension）。
  - **core**：`hosts_helper.py`（is_dev_local、add_host_entry、remove_host_entry、list_managed_entries、_cli_main 等）补英文。
- **后端 backend/app（仅英文 docstring → 补中文）**：
  - `services/system/cache_management_service.py`：_format_size、_CategoryStats、CacheManagementService 类及 _scan_*、_build_summary_item、get_cache_summary、_clear_*、clear_cache 等补中文。

### 第三轮全面审计

- **前端 web-antd**：
  - `views/admin/ai/providers/data.ts`：模块注释、缓存适配器类型列表、加载适配器类型 补英文。
  - `stores/plugin-extensions.ts`：EditorExtensionItem、EditorPanelItem、EditorCommandItem、ExtensionConflict 及所有属性 JSDoc 仅中文 → 补英文。
- **后端 backend/app**：
  - **schemas**：`ai/agent_version.py`（4 处）、`system/role.py`（15 处）、`system/config.py`（10 处）、`system/periodic_task.py`（PeriodicTaskCreateRequest）仅中文 docstring 补英文。
  - **repositories**：`system/email_log_repository.py`、`ai/skill_repository.py`（get_by_id）补英文。
  - **services**：`tenant/tenant_user_service.py`（_get_tenant_name、_send_approval_notification）、`system/tenant_domain_service.py`（_should_inject_hosts、verify_domain）、`common/email_service.py`（EmailService 类及 send 方法）补英文。
  - **plugins/base.py**：on_enable、on_disable、on_uninstall、on_upgrade 仅英文 → 补中文（改为「中文 / English」）。

### 第二轮全面审计

- **前端 web-antd**：
  - `store/shared/user-preference.ts`：`globalPreviewActive` 单行 JSDoc 补英文。
  - `views/admin/plugins/data.ts`：模块注释及 getStatusColor、getStatusText、getScopeText、getTierColor、getTierText、derivePluginType、getTypeColor、getTypeIcon、getTypeText、PLUGIN_TYPES、useColumns、useGridFormSchema 等仅中文 JSDoc 补英文。
- **后端 backend/app**：
  - **schemas**：`ai/agent_skill_binding.py`（3 处）、`tenant/user.py`（10 处）、`common/query.py`（5 处）、`system/periodic_task.py`（4 处）、`tenant/user_role.py`（5 处）仅中文 docstring 补英文。
  - **services**：`system/operation_log_service.py`（模块日志器）、`tenant/tenant_settings_service.py`（_count_domains、_unset_primary_domain、get_cname_target、list_domains）、`tenant/attachment_download_service.py`（全部仅中文 docstring）补英文。
  - **services/common/channels/base.py**：`channel_name` 仅中文 docstring 补英文。

- **backend/app**：此前已全量扫描并修复**仅中文/仅英文** docstring，包括：
  - **schemas/**：ai（conversation_message, provider, tenant_rate_limit）, system/cache, tenant/role；及此前 table_policy_override, knowledge_base, agent, agent_chat, common/permission, system/operation_log
  - **repositories/**：ai/table_policy_override_repository, ai/skill_package_repository
  - **services/**：tenant/quota_service, system/acme_client, system/periodic_task_service, system/ssl_certificate_service, ai/agent_router_service；及此前 system_log_service, agent_assignment_service, tenant_admin_role_service
  - **core/**：logging, hosts_helper, i18n
- **backend/plugins**：netdisk、weather-widget 遗漏处已补全（upload_service, tenant_upload, netdisk_tools, share_service get_download_url, test_open_meteo, test_skill）。
- **backend/migrations**：20260123_0005、20260123_0006、20260303_merge_session_memory_heads 中 upgrade/downgrade docstring 已改为双语。
- **backend/tests**：test_admin_auth、test_admin_admins、test_admin_roles 中所有类/方法 docstring 已改为双语。
- **frontend**：本轮补全：
  - **NovusDoc 插件**：DocumentList.vue、api/novusdoc.ts 模块注释改为双语。
  - **web-antd**：ChatMessageItem、AIChatSlidePanel（collectVisualState/truncateFormFields/guardPageDataSize/enrichPageContext）、user/ai-chat、StorageSwitchImpactModal、useEditorAI；views 下 usage、main.ts、VersionHistory、AccessConfigDrawer、DomainsSslDrawer、table-policies form、agent-assignments、api-keys、models、table-policies、call-logs、providers、dashboard、AccessConfig、DomainsSslDrawer 内单行 JSDoc、table-policies form watch 等仅中文/仅英文块均已改为双语。

## 已在本轮补全的范围（历史）

- `backend/app/core/`：query_parser, i18n, **logging, hosts_helper**
- `backend/app/schemas/`：common/auth, **common/permission**, system/email_log, system/admin, system/tenant, tenant/admin, tenant/ssl, ai/*（含 **knowledge_base, agent, agent_chat, table_policy_override**）, **system/operation_log**
- `backend/app/services/`：ai/*, **system/system_log_service, system/agent_assignment_service**, system/plugin_service, admin_role_service, **tenant/tenant_admin_role_service**, tenant_user_role_service, common/*
- `backend/plugins/netdisk`：全量仅中文 docstring 已改为双语
- `backend/plugins/weather-widget`：全量仅中文 docstring 已改为双语

---

## 待补全 / 建议抽查

以下为**未在本轮全量扫描**或可能仍有单语注释的区域，可按相同规则抽查。

### 后端 app（本轮续补）

- **ai/**（第六轮 + 第七轮已补）：rag/、routing/（含 router.py）、skills/（resolver、toolkit_parser）、system_agent、tools/（__init__、executors、enhancer、sandbox）、utils/、data_intelligence/（schema_provider、tenant_isolation 等）。usage_recorder 已为双语。
- **api/、captcha/、celery_app、core/**（第六轮已补）：见第六轮。
- **models/**（第七轮已补部分）：query_log、permission、agent、system/config（三处类）、table_policy（两处类）、tenant_domain、tenant_plan、notification、skill_call_log。**待续补**：auth/tenant_admin_role、ai/provider、tenant/tenant、ai/api_key、system/plugin、plugin_version 等其余类（见扫描或 grep 仅中文首行）。
- **repositories/、services/**（第七轮已补部分）：agent_repository、call_log_service。其余按扫描分批补全。
- **storage/**（第七轮已补）：__init__.py。**plugins/**（第八轮已补首行双语）、**sio/**、**tasks/** 已为双语；**schemas/** 多轮已补，按扫描查缺；**utils/**（app 根下）按扫描补全。**rbac/**、**main.py**、**core/**（base_controller、base_model、base_schema）、**repositories**（action_log、admin、agent_conversation、knowledge_base 等）、**ai/tools/**（executors、sandbox、types、usage_recorder）第八轮已补部分；其余 repositories/services、api/、core/ 其余文件按扫描分批补全。

### 前端 web-antd

- 已抽查：`components/business/`、`composables/`、`utils/plugin-shared.ts`、`router/access.ts`、`core/adapter/component/` 等 JSDoc 均为「块内中英各一行」或「英文 / 中文」形式，符合规范。其余 `src/` 可按需抽查。
- **多行 JSDoc 补全（本次）**：扫描脚本已扩展为同时检查多行 `/** ... */` 块首行双语。此前仅检查单行 JSDoc，多行块存在遗漏。扩展后共发现并修复 41 处（25 个文件）：含 `components/index.ts`、`views/_shared/*`、多个 `views/**/*.vue` 的 zh_only 首行，以及 `use-ai-chat.ts`、`use-file-upload.ts`、`use-page-screenshot.ts`、`constants/upload.ts`、`menu-transformer.ts`、`AgentProfilePopover.vue`、`dom-semantic-scanner.ts`、`use-ai-operations.ts` 等 en_only 首行。当前 `python scripts/scan_comment_compliance.py --ci` 全量通过（Frontend 0 / Backend 0）。
- **深入检查（后续）**：1) 后端补修 2 处：`ai/rag/audio_describer.py`、`ai/rag/video_describer.py` 中「首行英文 + 第二行中文」的 docstring 改为首行双语（`中文 / English`），以满足脚本对首行含 ` / ` 的判定。2) 扫描脚本已支持后端单引号 docstring（`'''...'''`），与 `"""..."""` 一并检查。3) 扫描范围：前端仅 `frontend/apps/web-antd/src`（未含 `frontend/packages`、`frontend/playground`）；后端仅 `backend/app`（未含 `backend/tests`、`backend/migrations`、`backend/scripts`、`backend/plugins/*` 等）。若需对上述目录做注释规范，需扩展脚本路径或单独约定。
- **扩展审计（--extended）**：执行 `python scripts/scan_comment_compliance.py --extended` 可额外扫描 `backend/plugins`、`backend/tests`、`frontend/packages`。首次运行结果：plugins 约 440 处、tests 约 200+ 处单语 docstring。已优先补全部分插件根模块与关键文件双语：`plugins/netdisk/backend/__init__.py`、`plugins/novusdoc/backend/__init__.py` 及 `api/__init__.py`、`services/__init__.py`、`plugins/amazon-s3/backend/main.py` 与 `driver.py`、`plugins/storage-migration/backend/main.py`、`plugins/netdisk/backend/services/upload_service.py`、`plugins/weather-widget/backend/api/handlers.py` 等。其余插件/测试内单语注释可按需分批补全或后续纳入 CI 范围。

### 插件前端

- **backend/plugins/** 下各插件 frontend（如 novusdoc 的 .vue/.ts）：如有单语注释可补全为双语。

---

## 建议操作

1. 在 `backend/app` 下搜索仅中文 docstring：含 `[一-龥]` 且不含 ` / ` 的 `"""..."""` 块。
2. 在 `frontend/apps/web-antd/src` 下检查 JSDoc：无中文则补中文，无英文则补英文。
3. 每改一处即保持格式：**中文说明 / English description.**

全量审计完成后，可归档或删除本文档。
