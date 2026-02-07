"""
应用配置模块

使用 pydantic-settings 管理应用配置，支持环境变量和 .env 文件
"""

from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置类"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ========================================
    # 应用基础配置
    # ========================================
    APP_NAME: str = "NovusAI SaaS"
    APP_VERSION: str = "0.1.0"
    APP_ENV: str = "development"  # development, staging, production
    DEBUG: bool = True
    
    # 时区配置（用于后端和数据库）
    TIMEZONE: str = "Asia/Shanghai"
    
    # API 配置
    API_V1_PREFIX: str = "/api/v1"
    
    # 跨域配置
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5666" ]
    
    # ========================================
    # 安全配置
    # ========================================
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"
    
    # ========================================
    # 数据库配置
    # ========================================
    DATABASE_HOST: str = "localhost"
    DATABASE_PORT: int = 5432
    DATABASE_USER: str = "postgres"
    DATABASE_PASSWORD: str = "postgres"
    DATABASE_NAME: str = "novusai_saas"
    
    # 连接池配置
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_POOL_TIMEOUT: int = 30
    
    @property
    def DATABASE_URL(self) -> str:
        """构建数据库连接 URL"""
        return (
            f"postgresql+asyncpg://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}"
            f"@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"
        )
    
    @property
    def DATABASE_URL_SYNC(self) -> str:
        """同步数据库连接 URL (用于 Alembic)"""
        return (
            f"postgresql://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}"
            f"@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"
        )
    
    # ========================================
    # Redis 配置
    # ========================================
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0
    
    @property
    def REDIS_URL(self) -> str:
        """构建 Redis 连接 URL"""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    # ========================================
    # Celery 配置
    # ========================================
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""
    CELERY_TASK_SERIALIZER: str = "json"
    CELERY_RESULT_SERIALIZER: str = "json"
    CELERY_ACCEPT_CONTENT: list[str] = ["json"]
    CELERY_TASK_TRACK_STARTED: bool = True
    CELERY_TASK_TIME_LIMIT: int = 3600
    CELERY_TASK_SOFT_TIME_LIMIT: int = 3300
    CELERY_WORKER_CONCURRENCY: int = 4
    CELERY_WORKER_PREFETCH_MULTIPLIER: int = 1

    @property
    def celery_broker_url(self) -> str:
        return self.CELERY_BROKER_URL or self.REDIS_URL

    @property
    def celery_result_backend(self) -> str:
        return self.CELERY_RESULT_BACKEND or self.REDIS_URL
    
    # ========================================
    # 日志配置
    # ========================================
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_DIR: str = "logs"
    
    # ========================================
    # 分页配置
    # ========================================
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100
    
    # ========================================
    # 租户域名配置
    # ========================================
    # 租户子域名后缀，如 .app.novusai.com
    # 租户访问地址为: {tenant_code}.app.novusai.com
    TENANT_DOMAIN_SUFFIX: str = ".app.novusai.com"
    
    # 是否允许租户绑定自定义域名
    ALLOW_CUSTOM_DOMAIN: bool = True
    
    # 租户域名验证前缀（用于 DNS TXT 记录验证）
    DOMAIN_VERIFICATION_PREFIX: str = "_novusai-verification"
    
    @property
    def tz(self) -> ZoneInfo:
        """获取时区对象"""
        return ZoneInfo(self.TIMEZONE)


@lru_cache
def get_settings() -> Settings:
    """
    获取应用配置单例
    
    使用 lru_cache 确保只创建一个 Settings 实例
    """
    return Settings()


# 导出配置实例
settings = get_settings()
