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
    # AI 数据智能（Text-to-SQL）配置
    # ========================================
    # 只读数据库连接 URL（用于 AI Text-to-SQL 查询）
    # 建议使用专用只读用户，参见 scripts/create_ai_readonly_user.sql
    AI_READONLY_DB_URL: str = ""

    @property
    def AI_READONLY_DB_URL_ASYNC(self) -> str:
        """异步只读数据库连接 URL"""
        url = self.AI_READONLY_DB_URL
        if not url:
            return ""
        # 将 postgresql:// 转为 postgresql+asyncpg://
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    # ========================================
    # AI 缓存配置
    # ========================================
    AI_CACHE_TTL: int = 3600  # AI 响应缓存 TTL（秒），仅 temperature=0 时生效

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
    
    # ========================================
    # SSL 证书管理
    # ========================================
    # 私钥加密密钥（Fernet key，用于加密存储 SSL 私钥）
    SSL_PRIVATE_KEY_ENCRYPTION_KEY: str = ""
    # ACME 目录 URL（生产环境）
    ACME_DIRECTORY_URL: str = "https://acme-v02.api.letsencrypt.org/directory"
    # ACME 目录 URL（测试环境）
    ACME_STAGING_URL: str = "https://acme-staging-v02.api.letsencrypt.org/directory"
    # ACME 注册邮箱
    ACME_ACCOUNT_EMAIL: str = ""
    # 是否使用 staging 环境（开发/测试时设 True）
    ACME_USE_STAGING: bool = True
    # 自动续期提前天数
    SSL_AUTO_RENEW_DAYS: int = 30
    
    # ========================================
    # 插件市场配置
    # ========================================
    PLUGIN_REGISTRY_URL: str = ""
    PLUGIN_REGISTRY_MIRROR: str = "github"  # github / gitee
    GITHUB_PROXY: str = ""
    GITHUB_TOKEN: str = ""
    GITEE_TOKEN: str = ""
    PLUGIN_REGISTRY_CACHE_TTL: int = 3600
    PLUGIN_MAX_PACKAGE_SIZE: int = 50 * 1024 * 1024
    PLUGIN_MAX_UNCOMPRESSED_SIZE: int = 200 * 1024 * 1024
    PLUGIN_MAX_ARCHIVE_FILES: int = 2000
    PLUGIN_MAX_ARCHIVE_SINGLE_FILE_SIZE: int = 50 * 1024 * 1024
    PLUGIN_MAX_COMPRESSION_RATIO: float = 100.0
    PLUGIN_ASSETS_ENABLED_ONLY: bool = True

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
