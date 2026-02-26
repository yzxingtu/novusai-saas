"""
平台配置管理 API

提供平台级配置管理接口（平台管理员专用）
"""

from typing import Any

from fastapi import Request, Body

from app.configs.service import ConfigService
from app.configs.registry import config_registry
from app.core.base_controller import GlobalController
from app.core.deps import DbSession, ActiveAdmin
from app.core.i18n import _
from app.core.response import success
from app.enums.config import ConfigScope
from app.enums.error_code import ErrorCode
from app.enums.rbac import PermissionScope
from app.exceptions import NotFoundException, BusinessException
from app.rbac.decorators import (
    permission_resource,
    MenuConfig,
    action_read,
    action_update,
)
from app.schemas.system.config import (
    ConfigGroupResponse,
    ConfigGroupListResponse,
    ConfigItemResponse,
    ConfigUpdateRequest,
    DisplayRuleSchema,
)


def _translate_config_item(config: dict) -> ConfigItemResponse:
    """将配置项字典转换为响应对象并翻译 i18n 键"""
    # 翻译选项标签
    translated_options = []
    for opt in config.get("options", []):
        translated_options.append({
            "value": opt["value"],
            "label": _(opt["label_key"]) if opt.get("label_key") else str(opt.get("value", "")),
        })
    
    # 翻译验证规则消息
    translated_rules = []
    for rule in config.get("validation_rules", []):
        translated_rules.append({
            "type": rule["type"],
            "value": rule["value"],
            "message": _(rule["message_key"]) if rule.get("message_key") else "",
        })
    
    # 转换显示规则
    display_rules = [
        DisplayRuleSchema(
            field=rule["field"],
            operator=rule.get("operator", "equals"),
            value=rule.get("value"),
            action=rule.get("action", "show"),
        )
        for rule in config.get("display_rules", [])
    ]
    
    # 递归转换子字段
    children = [
        _translate_config_item(child)
        for child in config.get("children", [])
    ]
    
    return ConfigItemResponse(
        key=config["key"],
        name=_(config["name_key"]),
        description=_(config["description_key"]) if config.get("description_key") else None,
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
    resource="platform_config",
    name="menu.admin.platform_config",  # i18n key
    scope=PermissionScope.ADMIN_ONLY,
    menu=MenuConfig(
        icon="lucide:settings",
        path="/system/configs",
        component="system/configs/List",
        parent="system_mgmt",  # 父菜单: 系统管理
        sort_order=50,
    ),
)
class AdminConfigController(GlobalController):
    """
    平台配置管理控制器
    
    提供平台级配置的查看和修改接口
    """
    
    prefix = "/configs"
    tags = ["System Configuration"]
    
    def _register_routes(self) -> None:
        """注册路由"""
        router = self.router
        
        @router.get("/groups", summary="获取配置分组列表")
        @action_read("action.platform_config.groups")
        async def list_config_groups(
            request: Request,
            db: DbSession,
            current_admin: ActiveAdmin,
        ):
            """
            获取平台配置分组列表
            
            返回所有平台级配置分组（不含具体配置项）
            
            权限: platform_config:groups
            """
            groups = config_registry.get_groups_by_scope(ConfigScope.ADMIN_ONLY)
            
            result = []
            for group in groups:
                if not group.is_active:
                    continue
                
                # 计算可见配置项数量
                visible_count = sum(
                    1 for c in group.configs if c.is_visible
                )
                
                result.append(ConfigGroupListResponse(
                    code=group.code,
                    name=_(group.name_key),
                    description=_(group.description_key) if group.description_key else None,
                    icon=group.icon,
                    sort_order=group.sort_order,
                    config_count=visible_count,
                ))
            
            return success(
                data=sorted(result, key=lambda x: x.sort_order),
                message=_("common.success"),
            )
        
        @router.get("/groups/{group_code}", summary="获取分组配置项")
        @action_read("action.platform_config.detail")
        async def get_group_configs(
            request: Request,
            db: DbSession,
            group_code: str,
            current_admin: ActiveAdmin,
        ):
            """
            获取指定分组的配置项列表（含当前值）
            
            权限: platform_config:detail
            """
            # 验证分组存在
            group = config_registry.get_group(group_code)
            if not group or group.scope != ConfigScope.ADMIN_ONLY:
                raise NotFoundException(
                    message=_("config.group_not_found"),
                    code=ErrorCode.CONFIG_GROUP_NOT_FOUND,
                )
            
            # 获取配置值
            config_service = ConfigService(db)
            groups_with_configs = await config_service.get_groups_with_configs(
                scope=ConfigScope.ADMIN_ONLY,
            )
            
            # 找到目标分组
            target_group = None
            for g in groups_with_configs:
                if g["code"] == group_code:
                    target_group = g
                    break
            
            if not target_group:
                raise NotFoundException(
                    message=_("config.group_not_found"),
                    code=ErrorCode.CONFIG_GROUP_NOT_FOUND,
                )
            
            # 转换响应
            configs = [
                _translate_config_item(c)
                for c in target_group["configs"]
            ]
            
            return success(
                data=ConfigGroupResponse(
                    code=target_group["code"],
                    name=_(target_group["name_key"]),
                    description=_(target_group["description_key"]) if target_group.get("description_key") else None,
                    icon=target_group.get("icon"),
                    sort_order=target_group["sort_order"],
                    configs=configs,
                ),
                message=_("common.success"),
            )
        
        @router.put("/groups/{group_code}", summary="更新分组配置")
        @action_update("action.platform_config.update")
        async def update_group_configs(
            request: Request,
            db: DbSession,
            group_code: str,
            current_admin: ActiveAdmin,
            body: dict[str, Any] = Body(...),
        ):
            """
            批量更新分组下的配置项
            
            支持两种格式：
            1. 扁平格式: {"site_name": "xxx", "site_logo": "xxx"}
            2. 包裹格式: {"configs": {"site_name": "xxx", ...}}
            
            权限: platform_config:update
            """
            # 验证分组存在
            group = config_registry.get_group(group_code)
            if not group or group.scope != ConfigScope.ADMIN_ONLY:
                raise NotFoundException(
                    message=_("config.group_not_found"),
                    code=ErrorCode.CONFIG_GROUP_NOT_FOUND,
                )
            
            # 支持两种格式
            if "configs" in body and isinstance(body["configs"], dict):
                configs = body["configs"]
            else:
                configs = body
            
            # 获取分组下的配置键列表
            valid_keys = {c.key for c in group.configs}
            
            # 验证传入的配置键
            invalid_keys = set(configs.keys()) - valid_keys
            if invalid_keys:
                raise BusinessException(
                    message=_("config.invalid_keys", keys=", ".join(invalid_keys)),
                    code=ErrorCode.CONFIG_INVALID_KEYS,
                )
            
            # 更新配置
            config_service = ConfigService(db)
            for key, value in configs.items():
                await config_service.set_platform_config(key, value)
            
            await db.commit()
            
            # 返回更新后的配置
            groups_with_configs = await config_service.get_groups_with_configs(
                scope=ConfigScope.ADMIN_ONLY,
            )
            
            target_group = None
            for g in groups_with_configs:
                if g["code"] == group_code:
                    target_group = g
                    break
            
            configs = [
                _translate_config_item(c)
                for c in target_group["configs"]
            ] if target_group else []
            
            return success(
                data=ConfigGroupResponse(
                    code=group_code,
                    name=_(group.name_key),
                    description=_(group.description_key) if group.description_key else None,
                    icon=group.icon,
                    sort_order=group.sort_order,
                    configs=configs,
                ),
                message=_("config.updated"),
            )
        
        @router.post("/generate-fernet-key", summary="生成 Fernet 加密密钥")
        @action_update("action.platform_config.update")
        async def generate_fernet_key(
            request: Request,
            current_admin: ActiveAdmin,
        ):
            """
            生成一个随机的 Fernet 密钥（用于 SSL 私钥加密等场景）
            
            权限: platform_config:update
            """
            from cryptography.fernet import Fernet
            key = Fernet.generate_key().decode()
            return success(data={"key": key})

        @router.post("/storage/test-connection", summary="测试存储连接")
        @action_update("action.platform_config.update")
        async def test_storage_connection(
            request: Request,
            current_admin: ActiveAdmin,
            driver: str = Body(..., embed=True),
            root_path: str = Body("", embed=True),
            base_url: str = Body("", embed=True),
            config: dict[str, Any] = Body({}, embed=True),
        ):
            """
            测试存储驱动连接是否可用
            
            执行完整测试流程：实例化 → 上传测试文件 → 检查存在 → 删除
            
            权限: platform_config:update
            """
            import io
            import uuid

            from app.storage import storage_manager
            from app.storage.base import StorageConfig

            try:
                sc = StorageConfig(
                    driver=driver,
                    root_path=root_path or config.get("bucket", "test"),
                    base_url=base_url or None,
                    options=config,
                )
                drv = storage_manager.get_driver(sc)

                test_key = f".novusai-test/{uuid.uuid4().hex[:8]}.txt"
                test_content = io.BytesIO(b"NovusAI storage connection test")

                await drv.put(
                    test_key, test_content,
                    mime_type="text/plain",
                )
                exists = await drv.exists(test_key)
                if not exists:
                    return success(data={
                        "success": False,
                        "errors": [_("config.storage.test_file_not_found")],
                    })
                await drv.delete(test_key)
                return success(data={"success": True})
            except Exception as e:
                return success(data={"success": False, "errors": [str(e)]})

        @router.get("/storage/drivers", summary="获取可用存储驱动列表")
        @action_read("action.platform_config.read")
        async def list_storage_drivers(
            request: Request,
            current_admin: ActiveAdmin,
        ):
            """
            获取所有可用的存储驱动列表（含内置和插件驱动）
            
            权限: platform_config:read
            """
            from app.storage import storage_manager

            return success(data=storage_manager.get_driver_info_list())

        @router.get("/storage/drivers/{driver_name}/schema", summary="获取存储驱动配置 Schema")
        @action_read("action.platform_config.read")
        async def get_storage_driver_schema(
            driver_name: str,
            request: Request,
            current_admin: ActiveAdmin,
        ):
            """
            获取指定存储驱动的配置 Schema
            
            权限: platform_config:read
            """
            from app.storage import storage_manager

            driver_cls = storage_manager.get_driver_class(driver_name)
            if not driver_cls:
                return success(data={"schema": {}, "defaults": {}})
            schema = getattr(driver_cls, "config_schema", None) or {}
            return success(data={"schema": schema, "defaults": {}})


# 导出路由
router = AdminConfigController.get_router()


__all__ = [
    "router",
    "AdminConfigController",
]
