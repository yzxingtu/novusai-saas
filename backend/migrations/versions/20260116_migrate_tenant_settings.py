"""migrate_tenant_settings_to_config

Revision ID: migrate_tenant_settings
Revises: 3f669a3f2342
Create Date: 2026-01-16 16:45:00.000000+00:00

将 tenants.settings JSON 字段数据迁移到新配置表
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session
import json


# revision identifiers, used by Alembic.
revision: str = 'migrate_tenant_settings'
down_revision: Union[str, None] = '3f669a3f2342'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 旧字段到新配置键的映射
SETTINGS_MAPPING = {
    # branding 分组
    "logo_url": "tenant_logo",
    "favicon_url": "tenant_favicon",
    "theme_color": "tenant_primary_color",
    # security 分组
    "captcha_enabled": "tenant_captcha_enabled",
    "login_methods": "tenant_login_methods",
}


def upgrade() -> None:
    """Upgrade: 迁移租户设置数据到新配置表."""
    bind = op.get_bind()
    session = Session(bind=bind)
    
    try:
        # 获取所有租户及其设置
        tenants = session.execute(
            sa.text("SELECT id, settings FROM tenants WHERE settings IS NOT NULL")
        ).fetchall()
        
        if not tenants:
            print("没有需要迁移的租户设置数据")
            return
        
        # 获取配置 ID 映射
        config_ids = {}
        for new_key in SETTINGS_MAPPING.values():
            result = session.execute(
                sa.text("SELECT id FROM system_configs WHERE key = :key"),
                {"key": new_key}
            ).fetchone()
            if result:
                config_ids[new_key] = result[0]
        
        if not config_ids:
            print("警告: 未找到配置项记录，请先运行配置同步")
            return
        
        migrated_count = 0
        
        for tenant_id, settings_json in tenants:
            if not settings_json:
                continue
            
            # 解析 JSON（可能是字符串或已解析的 dict）
            if isinstance(settings_json, str):
                try:
                    settings = json.loads(settings_json)
                except json.JSONDecodeError:
                    print(f"租户 {tenant_id} 的 settings 解析失败，跳过")
                    continue
            else:
                settings = settings_json
            
            if not isinstance(settings, dict):
                continue
            
            for old_key, new_key in SETTINGS_MAPPING.items():
                if old_key not in settings:
                    continue
                
                config_id = config_ids.get(new_key)
                if not config_id:
                    print(f"配置项 {new_key} 未找到，跳过")
                    continue
                
                value = settings[old_key]
                
                # 检查是否已存在配置值
                existing = session.execute(
                    sa.text("""
                        SELECT id FROM system_config_values 
                        WHERE config_id = :config_id AND tenant_id = :tenant_id AND is_deleted = FALSE
                    """),
                    {"config_id": config_id, "tenant_id": tenant_id}
                ).fetchone()
                
                if existing:
                    # 更新现有值
                    session.execute(
                        sa.text("""
                            UPDATE system_config_values 
                            SET value = :value, updated_at = NOW()
                            WHERE id = :id
                        """),
                        {"id": existing[0], "value": json.dumps(value)}
                    )
                else:
                    # 插入新值
                    session.execute(
                        sa.text("""
                            INSERT INTO system_config_values (config_id, tenant_id, value, created_at, updated_at, is_deleted)
                            VALUES (:config_id, :tenant_id, :value, NOW(), NOW(), FALSE)
                        """),
                        {"config_id": config_id, "tenant_id": tenant_id, "value": json.dumps(value)}
                    )
                
                migrated_count += 1
        
        session.commit()
        print(f"成功迁移 {migrated_count} 条配置数据")
        
    except Exception as e:
        session.rollback()
        print(f"迁移失败: {e}")
        raise
    finally:
        session.close()


def downgrade() -> None:
    """Downgrade: 不支持回滚数据迁移."""
    # 数据迁移不支持自动回滚
    # 如需回滚，请手动处理
    print("警告: 数据迁移不支持自动回滚")
    pass
