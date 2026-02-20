"""add domain_ssl_certificates table

Revision ID: 27044bf9d269
Revises: f97fd4fbf845
Create Date: 2026-02-20 18:33:05.298760+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '27044bf9d269'
down_revision: Union[str, None] = 'f97fd4fbf845'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    op.create_table('domain_ssl_certificates',
    sa.Column('domain_id', sa.Integer(), nullable=False, comment='域名 ID'),
    sa.Column('tenant_id', sa.Integer(), nullable=False, comment='租户 ID'),
    sa.Column('cert_type', sa.String(length=20), nullable=False, comment='证书类型: platform(ACME自动签发) / custom(用户上传)'),
    sa.Column('status', sa.String(length=20), nullable=False, comment='证书状态: pending/active/expired/revoked/failed'),
    sa.Column('certificate', sa.Text(), nullable=True, comment='PEM 格式证书内容'),
    sa.Column('private_key_encrypted', sa.Text(), nullable=True, comment='Fernet 加密的私钥'),
    sa.Column('certificate_chain', sa.Text(), nullable=True, comment='PEM 格式证书链（中间证书）'),
    sa.Column('issuer', sa.String(length=255), nullable=True, comment="签发机构（如 Let's Encrypt）"),
    sa.Column('serial_number', sa.String(length=100), nullable=True, comment='证书序列号'),
    sa.Column('issued_at', sa.DateTime(timezone=True), nullable=True, comment='签发时间'),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True, comment='到期时间'),
    sa.Column('auto_renew', sa.Boolean(), nullable=False, comment='是否自动续期（仅 platform 类型有效）'),
    sa.Column('last_renewal_attempt', sa.DateTime(timezone=True), nullable=True, comment='最近一次续期尝试时间'),
    sa.Column('renewal_error', sa.Text(), nullable=True, comment='最近一次续期失败原因'),
    sa.Column('acme_order_url', sa.String(length=500), nullable=True, comment='ACME 订单 URL（用于异步轮询签发状态）'),
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False, comment='创建时间'),
    sa.Column('updated_at', sa.DateTime(), nullable=False, comment='更新时间'),
    sa.Column('is_deleted', sa.Boolean(), nullable=False, comment='软删除标记'),
    sa.Column('deleted_at', sa.DateTime(), nullable=True, comment='删除时间'),
    sa.Column('delete_level', sa.String(length=20), nullable=True, comment='删除层级: tenant=租户回收站, admin=管理端回收站'),
    sa.ForeignKeyConstraint(['domain_id'], ['tenant_domains.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_domain_ssl_certificates_domain_id'), 'domain_ssl_certificates', ['domain_id'], unique=False)
    op.create_index(op.f('ix_domain_ssl_certificates_id'), 'domain_ssl_certificates', ['id'], unique=False)
    op.create_index(op.f('ix_domain_ssl_certificates_is_deleted'), 'domain_ssl_certificates', ['is_deleted'], unique=False)
    op.create_index(op.f('ix_domain_ssl_certificates_tenant_id'), 'domain_ssl_certificates', ['tenant_id'], unique=False)
    op.create_index('ix_domain_ssl_certs_domain_status', 'domain_ssl_certificates', ['domain_id', 'status'], unique=False)
    op.create_index('ix_domain_ssl_certs_expires', 'domain_ssl_certificates', ['expires_at'], unique=False)
    op.create_index('ix_domain_ssl_certs_tenant', 'domain_ssl_certificates', ['tenant_id'], unique=False)


def downgrade() -> None:
    """Downgrade database schema."""
    op.drop_index('ix_domain_ssl_certs_tenant', table_name='domain_ssl_certificates')
    op.drop_index('ix_domain_ssl_certs_expires', table_name='domain_ssl_certificates')
    op.drop_index('ix_domain_ssl_certs_domain_status', table_name='domain_ssl_certificates')
    op.drop_index(op.f('ix_domain_ssl_certificates_tenant_id'), table_name='domain_ssl_certificates')
    op.drop_index(op.f('ix_domain_ssl_certificates_is_deleted'), table_name='domain_ssl_certificates')
    op.drop_index(op.f('ix_domain_ssl_certificates_id'), table_name='domain_ssl_certificates')
    op.drop_index(op.f('ix_domain_ssl_certificates_domain_id'), table_name='domain_ssl_certificates')
    op.drop_table('domain_ssl_certificates')
