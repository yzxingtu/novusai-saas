"""add tenant-scoped unique constraints for tenant_admins and tenant_users

Adds UniqueConstraint on (tenant_id, username) and (tenant_id, email) for tenant_admins,
and (tenant_id, username), (tenant_id, email), (tenant_id, phone) for tenant_users.

Revision ID: 20260305_tenant_uq
Revises: c1a4f0e2b9d3
Create Date: 2026-03-05 16:00:00.000000+00:00

"""

from collections.abc import Callable, Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = "20260305_tenant_uq"
down_revision: str | Sequence[str] | None = "c1a4f0e2b9d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(table_name: str) -> bool:
    return inspect(op.get_bind()).has_table(table_name)


def _unique_constraint_names(table_name: str) -> set[str]:
    if not _has_table(table_name):
        return set()
    return {
        constraint["name"]
        for constraint in inspect(op.get_bind()).get_unique_constraints(table_name)
        if constraint.get("name")
    }


def _dedupe_tenant_admins_username() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM tenant_admins dup
            USING tenant_admins keep
            WHERE dup.id > keep.id
              AND dup.tenant_id = keep.tenant_id
              AND dup.username IS NOT NULL
              AND keep.username = dup.username
            """
        )
    )


def _dedupe_tenant_admins_email() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM tenant_admins dup
            USING tenant_admins keep
            WHERE dup.id > keep.id
              AND dup.tenant_id = keep.tenant_id
              AND dup.email IS NOT NULL
              AND keep.email = dup.email
            """
        )
    )


def _dedupe_tenant_users_username() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM tenant_users dup
            USING tenant_users keep
            WHERE dup.id > keep.id
              AND dup.tenant_id = keep.tenant_id
              AND dup.username IS NOT NULL
              AND keep.username = dup.username
            """
        )
    )


def _dedupe_tenant_users_email() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM tenant_users dup
            USING tenant_users keep
            WHERE dup.id > keep.id
              AND dup.tenant_id = keep.tenant_id
              AND dup.email IS NOT NULL
              AND keep.email = dup.email
            """
        )
    )


def _dedupe_tenant_users_phone() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM tenant_users dup
            USING tenant_users keep
            WHERE dup.id > keep.id
              AND dup.tenant_id = keep.tenant_id
              AND dup.phone IS NOT NULL
              AND keep.phone = dup.phone
            """
        )
    )


def _create_unique_constraint_if_missing(
    table_name: str,
    constraint_name: str,
    columns: list[str],
    *,
    dedupe: Callable[[], None] | None = None,
) -> None:
    if not _has_table(table_name):
        return
    if constraint_name in _unique_constraint_names(table_name):
        return
    if dedupe is not None:
        dedupe()
    op.create_unique_constraint(constraint_name, table_name, columns)


def upgrade() -> None:
    _create_unique_constraint_if_missing(
        "tenant_admins",
        "uq_tenant_admin_tenant_username",
        ["tenant_id", "username"],
        dedupe=_dedupe_tenant_admins_username,
    )
    _create_unique_constraint_if_missing(
        "tenant_admins",
        "uq_tenant_admin_tenant_email",
        ["tenant_id", "email"],
        dedupe=_dedupe_tenant_admins_email,
    )
    _create_unique_constraint_if_missing(
        "tenant_users",
        "uq_tenant_user_tenant_username",
        ["tenant_id", "username"],
        dedupe=_dedupe_tenant_users_username,
    )
    _create_unique_constraint_if_missing(
        "tenant_users",
        "uq_tenant_user_tenant_email",
        ["tenant_id", "email"],
        dedupe=_dedupe_tenant_users_email,
    )
    _create_unique_constraint_if_missing(
        "tenant_users",
        "uq_tenant_user_tenant_phone",
        ["tenant_id", "phone"],
        dedupe=_dedupe_tenant_users_phone,
    )


def downgrade() -> None:
    if "uq_tenant_user_tenant_phone" in _unique_constraint_names("tenant_users"):
        op.drop_constraint("uq_tenant_user_tenant_phone", "tenant_users", type_="unique")
    if "uq_tenant_user_tenant_email" in _unique_constraint_names("tenant_users"):
        op.drop_constraint("uq_tenant_user_tenant_email", "tenant_users", type_="unique")
    if "uq_tenant_user_tenant_username" in _unique_constraint_names("tenant_users"):
        op.drop_constraint("uq_tenant_user_tenant_username", "tenant_users", type_="unique")
    if "uq_tenant_admin_tenant_email" in _unique_constraint_names("tenant_admins"):
        op.drop_constraint("uq_tenant_admin_tenant_email", "tenant_admins", type_="unique")
    if "uq_tenant_admin_tenant_username" in _unique_constraint_names("tenant_admins"):
        op.drop_constraint("uq_tenant_admin_tenant_username", "tenant_admins", type_="unique")
