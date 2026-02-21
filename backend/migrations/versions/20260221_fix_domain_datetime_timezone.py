"""fix domain/ssl datetime columns: remove timezone

Remove timezone=True from DateTime columns in tenant_domains and
domain_ssl_certificates tables to match project convention
(TIMESTAMP WITHOUT TIME ZONE, naive UTC).

Revision ID: 20260221_fix_tz
Revises: 20260221_seed_ssl
Create Date: 2026-02-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '20260221_fix_tz'
down_revision: Union[str, None] = 'fbe521b42f77'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # tenant_domains: verified_at, ssl_expires_at
    op.alter_column(
        'tenant_domains', 'verified_at',
        type_=sa.DateTime(),
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=True,
    )
    op.alter_column(
        'tenant_domains', 'ssl_expires_at',
        type_=sa.DateTime(),
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=True,
    )

    # domain_ssl_certificates: issued_at, expires_at, last_renewal_attempt
    op.alter_column(
        'domain_ssl_certificates', 'issued_at',
        type_=sa.DateTime(),
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=True,
    )
    op.alter_column(
        'domain_ssl_certificates', 'expires_at',
        type_=sa.DateTime(),
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=True,
    )
    op.alter_column(
        'domain_ssl_certificates', 'last_renewal_attempt',
        type_=sa.DateTime(),
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        'domain_ssl_certificates', 'last_renewal_attempt',
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        existing_nullable=True,
    )
    op.alter_column(
        'domain_ssl_certificates', 'expires_at',
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        existing_nullable=True,
    )
    op.alter_column(
        'domain_ssl_certificates', 'issued_at',
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        existing_nullable=True,
    )
    op.alter_column(
        'tenant_domains', 'ssl_expires_at',
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        existing_nullable=True,
    )
    op.alter_column(
        'tenant_domains', 'verified_at',
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        existing_nullable=True,
    )
