"""API 测试配置文件 / API.

可通过环境变量或直接修改此文件配置测试参数"""
import os


class TestConfig:
    """测试配置 / Test."""

    # API 基础配置
    BASE_URL: str = os.getenv("TEST_API_BASE_URL", "http://localhost:8000")

    # 平台管理员账号
    ADMIN_USERNAME: str = os.getenv("TEST_ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.getenv("TEST_ADMIN_PASSWORD", "admin123456")

    # 企业管理员账号（需要先创建企业和企业管理员后配置）
    TENANT_ADMIN_USERNAME: str = os.getenv("TEST_TENANT_ADMIN_USERNAME", "")
    TENANT_ADMIN_PASSWORD: str = os.getenv("TEST_TENANT_ADMIN_PASSWORD", "")

    # 企业用户账号（需要先创建企业用户后配置）
    TENANT_USER_USERNAME: str = os.getenv("TEST_TENANT_USER_USERNAME", "")
    TENANT_USER_PASSWORD: str = os.getenv("TEST_TENANT_USER_PASSWORD", "")

    # 请求超时时间（秒）
    TIMEOUT: int = int(os.getenv("TEST_TIMEOUT", "30"))

    # 默认语言
    LANGUAGE: str = os.getenv("TEST_LANGUAGE", "zh-cn")

    # 测试数据配置
    TEST_TENANT_CODE: str = "test_tenant"
    TEST_TENANT_NAME: str = "测试企业"
    TEST_ROLE_CODE: str = "test_role"
    TEST_ROLE_NAME: str = "测试角色"


config = TestConfig()
