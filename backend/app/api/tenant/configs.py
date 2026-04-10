"""
企业配置管理 API / Tenant Configuration Management API

提供企业级配置管理接口（企业管理员专用）
Provides tenant-level configuration management endpoints (tenant admin only)
"""

from __future__ import annotations

from fastapi import Body, Request

from app.api.shared._captcha_helpers import inject_captcha_provider_options
from app.api.shared._storage_helpers import (
    get_known_plugin_storage_drivers as _get_known_plugin_storage_drivers,
)
from app.configs.registry import config_registry
from app.configs.service import ConfigService
from app.core.base_controller import TenantController
from app.core.deps import ActiveTenantAdmin, DbSession
from app.core.i18n import _
from app.core.response import build_inline_error_result, success
from app.enums.config import ConfigScope
from app.enums.error_code import ErrorCode
from app.enums.rbac import PermissionScope
from app.exceptions import BusinessException, NotFoundException
from app.rbac.decorators import (
    MenuConfig,
    action_read,
    action_update,
    permission_resource,
)
from app.schemas.system.config import (
    ConfigGroupListResponse,
    ConfigGroupResponse,
    ConfigItemResponse,
    ConfigUpdateRequest,
    DisplayRuleSchema,
)
from app.services.tenant.tenant_role_option_service import TenantRoleOptionService

# 密钥类字段名关键词，匹配到的值做脱敏处理 / Sensitive field name keywords, matched values are masked
_SENSITIVE_KEYWORDS = {"secret", "key", "password", "token"}


def _mask_sensitive_options(options: dict) -> dict:
    """
    对存储凭证中的密钥类字段做脱敏处理 / Mask sensitive fields in storage credentials.

    规则：字段名包含 secret/key/password/token 关键词的，值脱敏为前 2 位 + **** + 后 2 位。
    Rule: Fields containing secret/key/password/token keywords are masked as first 2 chars + **** + last 2 chars.
    非密钥字段（bucket、region、endpoint、prefix 等）原样返回。
    Non-sensitive fields (bucket, region, endpoint, prefix, etc.) are returned as-is.
    """
    if not options:
        return {}
    masked: dict = {}
    for k, v in options.items():
        if not isinstance(v, str) or not v:
            masked[k] = v
            continue
        k_lower = k.lower()
        is_sensitive = any(word in k_lower for word in _SENSITIVE_KEYWORDS)
        if is_sensitive and len(v) > 4:
            masked[k] = f"{v[:2]}{'*' * min(len(v) - 4, 8)}{v[-2:]}"
        elif is_sensitive:
            masked[k] = "****"
        else:
            masked[k] = v
    return masked


async def _load_group_with_runtime_options(
    config_service: ConfigService,
    role_query_service: TenantRoleOptionService,
    tenant_id: int,
    group_code: str,
) -> dict | None:
    """Load tenant config group and inject runtime-only options for response."""
    groups_with_configs = await config_service.get_groups_with_configs(
        scope=ConfigScope.ALL_TENANTS,
        tenant_id=tenant_id,
    )

    target_group = next(
        (group for group in groups_with_configs if group["code"] == group_code),
        None,
    )
    if target_group is None:
        return None

    await role_query_service.inject_role_options_for_user_default_role(
        tenant_id=tenant_id,
        configs=target_group["configs"],
    )
    inject_captcha_provider_options(
        target_group["configs"],
        required_endpoints={"tenant", "user"},
        unavailable_label_key="config.tenant.captcha_provider.unavailable_option",
    )
    return target_group


def _translate_config_item(config: dict) -> ConfigItemResponse:
    """将配置项字典转换为响应对象并翻译 i18n 键 / Convert config item dict to response object and translate i18n keys"""
    # 翻译选项标签 / Translate option labels
    translated_options = []
    for opt in config.get("options", []):
        if opt.get("label"):
            label = opt["label"]
        elif opt.get("label_key"):
            label = _(opt["label_key"])
        else:
            label = str(opt.get("value", ""))
        translated_options.append(
            {
                "value": opt["value"],
                "label": label,
            }
        )

    # 翻译验证规则消息 / Translate validation rule messages
    translated_rules = []
    for rule in config.get("validation_rules", []):
        translated_rules.append(
            {
                "type": rule["type"],
                "value": rule["value"],
                "message": _(rule["message_key"]) if rule.get("message_key") else "",
            }
        )

    # 转换显示规则 / Convert display rules
    display_rules = [
        DisplayRuleSchema(
            field=rule["field"],
            operator=rule.get("operator", "equals"),
            value=rule.get("value"),
            action=rule.get("action", "show"),
        )
        for rule in config.get("display_rules", [])
    ]

    # 递归转换子字段 / Recursively convert child fields
    children = [_translate_config_item(child) for child in config.get("children", [])]

    return ConfigItemResponse(
        key=config["key"],
        name=_(config["name_key"]),
        description=_(config["description_key"])
        if config.get("description_key")
        else None,
        value_type=config["value_type"],
        value=config["value"],
        default_value=config["default_value"],
        options=translated_options,
        validation_rules=translated_rules,
        is_required=config["is_required"],
        is_encrypted=config["is_encrypted"],
        sort_order=config["sort_order"],
        display_rules=display_rules,
        value_path=config.get("value_path", ""),
        children=children,
        tag_separator=config.get("tag_separator", ","),
        file_accept=config.get("file_accept", ""),
    )


@permission_resource(
    resource="tenant_config",
    name="menu.tenant.tenant_config",  # i18n key / 国际化键名
    scope=PermissionScope.TENANT,
    parent_resource="system_mgmt",
    menu=MenuConfig(
        icon="lucide:sliders-horizontal",
        path="/system-mgmt/configs",
        component="system/configs/List",
        parent="system_mgmt",  # 父菜单: 系统管理 / Parent menu: system management
        sort_order=10,
    ),
)
class TenantConfigController(TenantController):
    """
    企业配置管理控制器 / Tenant Configuration Management Controller

    提供企业级配置的查看和修改接口
    Provides tenant-level configuration viewing and editing endpoints
    """

    prefix = "/configs"
    tags = ["Tenant Configuration"]

    def _register_routes(self) -> None:
        """注册路由 / Register routes"""
        router = self.router

        @router.get("/groups", summary="获取配置分组列表")
        @action_read("action.tenant_config.groups")
        async def list_config_groups(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
        ):
            """
            获取企业配置分组列表 / Get tenant config group list

            返回所有企业级配置分组（不含具体配置项）
            Returns all tenant-level config groups (without config items)

            权限 / Permission: tenant_config:groups
            """
            groups = config_registry.get_groups_by_scope(ConfigScope.ALL_TENANTS)

            result = []
            for group in groups:
                if not group.is_active:
                    continue

                # 计算可见配置项数量 / Calculate visible config item count
                visible_count = sum(1 for c in group.configs if c.is_visible)

                result.append(
                    ConfigGroupListResponse(
                        code=group.code,
                        name=_(group.name_key),
                        description=_(group.description_key)
                        if group.description_key
                        else None,
                        icon=group.icon,
                        sort_order=group.sort_order,
                        config_count=visible_count,
                    )
                )

            return success(
                data=sorted(result, key=lambda x: x.sort_order),
                message=_("common.success"),
            )

        @router.get("/groups/{group_code}", summary="获取分组配置项")
        @action_read("action.tenant_config.detail")
        async def get_group_configs(
            request: Request,
            db: DbSession,
            group_code: str,
            current_admin: ActiveTenantAdmin,
        ):
            """
            获取指定分组的配置项列表（含当前值） / Get config items for specified group (with current values)

            权限 / Permission: tenant_config:detail
            """
            # 验证分组存在 / Verify group exists
            group = config_registry.get_group(group_code)
            if not group or group.scope != ConfigScope.ALL_TENANTS:
                raise NotFoundException(
                    message=_("config.group_not_found"),
                    code=ErrorCode.CONFIG_GROUP_NOT_FOUND,
                )

            # 获取配置值 / Get config values
            config_service = ConfigService(db)
            role_query_service = TenantRoleOptionService(db)
            target_group = await _load_group_with_runtime_options(
                config_service=config_service,
                role_query_service=role_query_service,
                tenant_id=current_admin.tenant_id,
                group_code=group_code,
            )

            if not target_group:
                raise NotFoundException(
                    message=_("config.group_not_found"),
                    code=ErrorCode.CONFIG_GROUP_NOT_FOUND,
                )

            # 转换响应 / Convert response
            configs = [_translate_config_item(c) for c in target_group["configs"]]

            return success(
                data=ConfigGroupResponse(
                    code=target_group["code"],
                    name=_(target_group["name_key"]),
                    description=_(target_group["description_key"])
                    if target_group.get("description_key")
                    else None,
                    icon=target_group.get("icon"),
                    sort_order=target_group["sort_order"],
                    configs=configs,
                ),
                message=_("common.success"),
            )

        @router.put("/groups/{group_code}", summary="更新分组配置")
        @action_update("action.tenant_config.update")
        async def update_group_configs(
            request: Request,
            db: DbSession,
            group_code: str,
            data: ConfigUpdateRequest,
            current_admin: ActiveTenantAdmin,
        ):
            """
            批量更新分组下的配置项 / Batch update config items under a group

            权限 / Permission: tenant_config:update
            """
            # 验证分组存在 / Verify group exists
            group = config_registry.get_group(group_code)
            if not group or group.scope != ConfigScope.ALL_TENANTS:
                raise NotFoundException(
                    message=_("config.group_not_found"),
                    code=ErrorCode.CONFIG_GROUP_NOT_FOUND,
                )

            # 获取分组下的配置键列表 / Get config key list under the group
            valid_keys = {c.key for c in group.configs}

            # 验证传入的配置键 / Validate incoming config keys
            invalid_keys = set(data.configs.keys()) - valid_keys
            if invalid_keys:
                raise BusinessException(
                    message=_("config.invalid_keys", keys=", ".join(invalid_keys)),
                    code=ErrorCode.CONFIG_INVALID_KEYS,
                )

            # 更新配置 / Update configs
            config_service = ConfigService(db)
            for key, value in data.configs.items():
                await config_service.set_tenant_config(
                    tenant_id=current_admin.tenant_id,
                    key=key,
                    value=value,
                )

            await db.commit()

            # 返回更新后的配置 / Return updated configs
            role_query_service = TenantRoleOptionService(db)
            target_group = await _load_group_with_runtime_options(
                config_service=config_service,
                role_query_service=role_query_service,
                tenant_id=current_admin.tenant_id,
                group_code=group_code,
            )

            configs = (
                [_translate_config_item(c) for c in target_group["configs"]]
                if target_group
                else []
            )

            return success(
                data=ConfigGroupResponse(
                    code=group_code,
                    name=_(group.name_key),
                    description=_(group.description_key)
                    if group.description_key
                    else None,
                    icon=group.icon,
                    sort_order=group.sort_order,
                    configs=configs,
                ),
                message=_("config.updated"),
            )

        @router.get("/storage/status", summary="获取企业存储状态")
        @action_read("action.tenant_config.groups")
        async def get_tenant_storage_status(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
        ):
            """
            获取企业当前存储状态（有效模式、驱动信息、自配置权限等） / Get tenant storage status (effective mode, driver info, self-config permission)

            权限 / Permission: tenant_config:groups
            """
            from app.configs.service import ConfigService
            from app.services.common.storage_config_resolver import (
                StorageConfigResolver,
            )

            tenant_id = current_admin.tenant_id
            config_service = ConfigService(db)
            resolver = StorageConfigResolver(db)

            effective_mode = await resolver.get_storage_mode(tenant_id)

            # 逐企业自主配置开关（不依赖全局开关） / Per-tenant self-config toggle (independent of global toggle)
            tenant_self_config_enabled = await config_service.get_tenant_config(
                tenant_id, "tenant_storage_self_config_enabled", default=False
            )

            # 当前企业配置值 / Current tenant config values
            tenant_mode = await config_service.get_tenant_config(
                tenant_id, "tenant_storage_mode", default="platform"
            )
            tenant_driver = await config_service.get_tenant_config(
                tenant_id, "tenant_storage_driver", default=None
            )
            tenant_root_path = await config_service.get_tenant_config(
                tenant_id, "tenant_storage_root_path", default=""
            )
            tenant_base_url = await config_service.get_tenant_config(
                tenant_id, "tenant_storage_base_url", default=""
            )
            tenant_options = await config_service.get_tenant_config(
                tenant_id, "tenant_storage_options", default={}
            )

            # 当前生效的驱动 / Currently effective driver
            if effective_mode == "platform":
                effective_driver = await config_service.get_platform_config(
                    "platform_storage_driver", default="local"
                )
            else:
                effective_driver = tenant_driver

            # 构建返回数据 / Build response data
            response_data: dict = {
                "effective_mode": str(effective_mode),
                "effective_driver": str(effective_driver)
                if effective_driver
                else "local",
                "tenant_storage_mode": str(tenant_mode),
                "can_self_config": bool(tenant_self_config_enabled),
            }

            if effective_mode == "admin_override":
                # 管理员帮配模式：展示脱敏后的配置信息（企业只读） / Admin override mode: show masked config info (tenant read-only)
                response_data["tenant_storage_driver"] = (
                    str(tenant_driver) if tenant_driver else None
                )
                response_data["tenant_storage_root_path"] = str(tenant_root_path)
                response_data["tenant_storage_base_url"] = str(tenant_base_url)
                response_data["tenant_storage_options"] = _mask_sensitive_options(
                    tenant_options or {}
                )
            elif effective_mode == "custom":
                # 自定义模式：返回企业自己填写的配置（密钥同样脱敏） / Custom mode: return tenant's own config (credentials also masked)
                response_data["tenant_storage_driver"] = (
                    str(tenant_driver) if tenant_driver else None
                )
                response_data["tenant_storage_root_path"] = str(tenant_root_path)
                response_data["tenant_storage_base_url"] = str(tenant_base_url)
                response_data["tenant_storage_options"] = _mask_sensitive_options(
                    tenant_options or {}
                )
            else:
                # 平台模式：不返回凭证细节 / Platform mode: do not return credential details
                response_data["tenant_storage_driver"] = None
                response_data["tenant_storage_root_path"] = ""
                response_data["tenant_storage_base_url"] = ""
                response_data["tenant_storage_options"] = {}

            return success(data=response_data)

        @router.put("/storage", summary="保存企业存储配置")
        @action_update("action.tenant_config.update")
        async def save_tenant_storage_config(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            data: dict = Body(...),
        ):
            """
            企业保存自主存储配置（Mode 3） / Tenant saves self-managed storage config (Mode 3)

            权限 / Permission: tenant_config:update
            """
            from app.configs.service import ConfigService

            tenant_id = current_admin.tenant_id
            config_service = ConfigService(db)

            # 检查逐企业自主配置开关（不依赖全局开关） / Check per-tenant self-config switch (independent of global switch)
            tenant_enabled = await config_service.get_tenant_config(
                tenant_id, "tenant_storage_self_config_enabled", default=False
            )
            if not tenant_enabled:
                raise BusinessException(
                    message=_("config.storage.self_config_not_enabled"),
                    code=ErrorCode.FORBIDDEN,
                )

            # 必填校验：驱动和 Bucket / Required validation: driver and Bucket
            driver = data.get("tenant_storage_driver")
            if not driver:
                raise BusinessException(
                    message=_("error.common.invalid_parameter"),
                    code=ErrorCode.INVALID_PARAMETER,
                )
            root_path = data.get("tenant_storage_root_path", "")
            if not root_path or not str(root_path).strip():
                raise BusinessException(
                    message=_("error.common.invalid_parameter"),
                    code=ErrorCode.INVALID_PARAMETER,
                )

            # 驱动不允许选 local / Driver cannot be local
            if driver == "local":
                raise BusinessException(
                    message=_("config.storage.local_not_allowed_for_tenant"),
                    code=ErrorCode.INVALID_PARAMETER,
                )

            # Check allowed drivers / 校验平台允许的驱动白名单
            if driver:
                allowed = await config_service.get_platform_config(
                    "platform_storage_allowed_custom_drivers",
                    default=["aliyun-oss", "qiniu-kodo", "tencent-cos", "s3"],
                )
                if isinstance(allowed, list) and driver not in allowed:
                    raise BusinessException(
                        message=_("config.storage.driver_not_allowed"),
                        code=ErrorCode.INVALID_PARAMETER,
                    )

            config_map = {
                "tenant_storage_mode": "tenant_storage_mode",
                "tenant_storage_driver": "tenant_storage_driver",
                "tenant_storage_root_path": "tenant_storage_root_path",
                "tenant_storage_base_url": "tenant_storage_base_url",
                "tenant_storage_options": "tenant_storage_options",
            }

            for field, config_key in config_map.items():
                if field in data:
                    await config_service.set_tenant_config(
                        tenant_id=tenant_id,
                        key=config_key,
                        value=data[field],
                    )

            await db.commit()
            return success(message=_("config.updated"))

        @router.post("/storage/test-connection", summary="测试企业存储连接")
        @action_update("action.tenant_config.update")
        async def test_tenant_storage_connection(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
            driver: str = Body(..., embed=True),
            root_path: str = Body("", embed=True),
            base_url: str = Body("", embed=True),
            config: dict = Body({}, embed=True),
        ):
            """
            测试企业自主存储连接（Mode 3） / Test tenant self-managed storage connection (Mode 3)

            权限 / Permission: tenant_config:update
            """
            import io
            import uuid

            from app.configs.service import ConfigService
            from app.storage import storage_manager
            from app.storage.base import StorageConfig

            # 检查逐企业自主配置开关（不依赖全局开关） / Check per-tenant self-config switch (independent of global switch)
            config_service = ConfigService(db)
            tenant_enabled = await config_service.get_tenant_config(
                current_admin.tenant_id,
                "tenant_storage_self_config_enabled",
                default=False,
            )
            if not tenant_enabled:
                raise BusinessException(
                    message=_("config.storage.self_config_not_enabled"),
                    code=ErrorCode.FORBIDDEN,
                )

            if driver == "local":
                raise BusinessException(
                    message=_("config.storage.local_not_allowed_for_tenant"),
                    code=ErrorCode.INVALID_PARAMETER,
                )

            # Check allowed drivers / 校验平台允许的驱动白名单
            allowed = await config_service.get_platform_config(
                "platform_storage_allowed_custom_drivers",
                default=["aliyun-oss", "qiniu-kodo", "tencent-cos", "s3"],
            )
            if isinstance(allowed, list) and driver not in allowed:
                raise BusinessException(
                    message=_("config.storage.driver_not_allowed"),
                    code=ErrorCode.INVALID_PARAMETER,
                )

            try:
                sc = StorageConfig(
                    driver=driver,
                    root_path=root_path or config.get("bucket", "test"),
                    base_url=base_url or None,
                    options=config,
                )
                drv = storage_manager.get_driver(sc)
                test_key = f".novusai-test/{uuid.uuid4().hex[:8]}.txt"
                test_content = io.BytesIO(b"NovusAI tenant storage test")
                await drv.put(test_key, test_content, mime_type="text/plain")
                exists = await drv.exists(test_key)
                if not exists:
                    return success(
                        data=build_inline_error_result(
                            _("config.storage.test_file_not_found"),
                        )
                    )
                await drv.delete(test_key)
                return success(data={"success": True})
            except BusinessException:
                raise
            except Exception as e:
                return success(
                    data=build_inline_error_result(
                        e,
                        fallback_message=_("common.server_error"),
                    )
                )

        @router.get("/storage/drivers", summary="获取企业允许的存储驱动列表")
        @action_read("action.tenant_config.groups")
        async def list_tenant_storage_drivers(
            request: Request,
            db: DbSession,
            current_admin: ActiveTenantAdmin,
        ):
            """
            获取企业允许选择的存储驱动列表（受平台白名单限制，标记插件启用状态） / Get allowed storage driver list for tenant (restricted by platform whitelist, marks plugin enabled status)

            权限 / Permission: tenant_config:groups
            """
            from app.configs.service import ConfigService
            from app.storage import storage_manager

            config_service = ConfigService(db)
            allowed = await config_service.get_platform_config(
                "platform_storage_allowed_custom_drivers",
                default=["aliyun-oss", "qiniu-kodo", "tencent-cos", "s3"],
            )
            if not isinstance(allowed, list):
                allowed = ["aliyun-oss", "qiniu-kodo", "tencent-cos", "s3"]

            known_plugin_drivers = await _get_known_plugin_storage_drivers(db)
            all_drivers = storage_manager.get_all_driver_info_list(known_plugin_drivers)
            # Filter to allowed + exclude local / 过滤白名单并排除 local
            filtered = [
                d for d in all_drivers if d["name"] in allowed and d["name"] != "local"
            ]
            return success(data=filtered)


# 导出路由 / Export router
router = TenantConfigController.get_router()


__all__ = [
    "router",
    "TenantConfigController",
]
