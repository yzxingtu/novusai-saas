"""
平台管理员仓储 / Admin Repository

提供平台管理员的数据访问操作
Provides platform admin data access operations.
"""

from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app.core.base_repository import BaseRepository
from app.models.system.admin import Admin


class AdminRepository(BaseRepository[Admin]):
    """
    平台管理员仓储 / Admin repository.

    提供管理员特有的数据访问方法
    """

    model = Admin

    # 按 scope 限制可过滤字段
    _scope_fields = {
        "admin": {
            "id",
            "username",
            "email",
            "phone",
            "is_active",
            "ai_enabled",
            "is_super",
            "nickname",
            "role_id",
            "created_at",
            "updated_at",
        },
    }

    async def get_by_username(self, username: str) -> Admin | None:
        """
        根据用户名获取管理员 / Get admin by username.

        Args:
            username: 用户名

        Returns:
            管理员实例或 None
        """
        return await self.get_one_by(username=username)

    async def get_by_email(self, email: str) -> Admin | None:
        """
        根据邮箱获取管理员 / Get admin by email.

        Args:
            email: 邮箱

        Returns:
            管理员实例或 None
        """
        return await self.get_one_by(email=email)

    async def get_by_phone(self, phone: str) -> Admin | None:
        """
        根据手机号获取管理员 / Get admin by phone.

        Args:
            phone: 手机号

        Returns:
            管理员实例或 None
        """
        return await self.get_one_by(phone=phone)

    async def get_by_username_or_email(
        self,
        username_or_email: str,
    ) -> Admin | None:
        """
        根据用户名或邮箱获取管理员（用于登录）/ Get admin by username or email (for login).

        Args:
            username_or_email: 用户名或邮箱

        Returns:
            管理员实例或 None
        """
        query = select(self.model).where(
            self.model.is_deleted.is_(False),
            or_(
                self.model.username == username_or_email,
                self.model.email == username_or_email,
            ),
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def username_exists(
        self, username: str, exclude_id: int | None = None
    ) -> bool:
        """
        检查用户名是否已存在 / Check if username already exists.

        Args:
            username: 用户名
            exclude_id: 排除的 ID（用于更新时排除自身）

        Returns:
            是否存在
        """
        query = select(self.model.id).where(
            self.model.username == username,
            self.model.is_deleted.is_(False),
        )
        if exclude_id:
            query = query.where(self.model.id != exclude_id)

        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None

    async def email_exists(self, email: str, exclude_id: int | None = None) -> bool:
        """
        检查邮箱是否已存在 / Check if email already exists.

        Args:
            email: 邮箱
            exclude_id: 排除的 ID

        Returns:
            是否存在
        """
        query = select(self.model.id).where(
            self.model.email == email,
            self.model.is_deleted.is_(False),
        )
        if exclude_id:
            query = query.where(self.model.id != exclude_id)

        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None

    async def phone_exists(self, phone: str, exclude_id: int | None = None) -> bool:
        """
        检查手机号是否已存在 / Check if phone already exists.

        Args:
            phone: 手机号
            exclude_id: 排除的 ID

        Returns:
            是否存在
        """
        if not phone:
            return False

        query = select(self.model.id).where(
            self.model.phone == phone,
            self.model.is_deleted.is_(False),
        )
        if exclude_id:
            query = query.where(self.model.id != exclude_id)

        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None

    async def query_identity_select(
        self,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Admin], int]:
        """
        查询管理端身份选择器数据 / Query admin identity select data.

        Returns:
            (admins, total)
        """
        conditions = [self.model.is_deleted.is_(False)]

        if search:
            escaped_search = str(search).replace("%", r"\%").replace("_", r"\_")
            pattern = f"%{escaped_search}%"
            conditions.append(
                or_(
                    self.model.username.ilike(pattern, escape="\\"),
                    self.model.nickname.ilike(pattern, escape="\\"),
                    self.model.email.ilike(pattern, escape="\\"),
                )
            )

        count_query = select(func.count(self.model.id)).where(*conditions)
        total = (await self.db.execute(count_query)).scalar() or 0

        query = (
            select(self.model)
            .where(*conditions)
            .options(
                selectinload(self.model.role),
                selectinload(self.model.org_node),
            )
            .order_by(
                self.model.is_super.desc(),
                self.model.username.asc(),
                self.model.id.asc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all()), total


__all__ = ["AdminRepository"]
