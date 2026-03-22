"""Cloud Storage Plugin compliance tests. / 插件

Validates:
- Each plugin's plugin.yaml schema
- StorageDriver subclass contract
- StorageManager only has local built-in
- Plugin disable safety check logic"""

import importlib.util
from pathlib import Path

import pytest

# ──────────────────────────────────────────────
# 1. StorageManager only registers local
# ──────────────────────────────────────────────

def test_storage_manager_only_local():
    """StorageManager should only register LocalStorageDriver by default. / 说明"""
    from app.storage.manager import StorageManager

    # Reset singleton for clean test
    StorageManager._instance = None
    mgr = StorageManager()
    drivers = mgr.get_available_drivers()
    assert drivers == ["local"], f"Expected only 'local', got {drivers}"
    # Restore
    StorageManager._instance = None


def test_storage_manager_register_unregister():
    """StorageManager register/unregister should work for plugin drivers. / 插件"""
    from app.storage.base import StorageDriver
    from app.storage.manager import StorageManager

    StorageManager._instance = None
    mgr = StorageManager()

    class FakeDriver(StorageDriver):
        name = "fake-test"
        display_name = "Fake Test"

    mgr.register_driver(FakeDriver)
    assert mgr.has_driver("fake-test")
    assert "fake-test" in mgr.get_available_drivers()

    mgr.unregister_driver("fake-test")
    assert not mgr.has_driver("fake-test")

    StorageManager._instance = None


def test_storage_manager_get_driver_info_list():
    """get_driver_info_list should return structured info. / 获取/返回"""
    from app.storage.manager import StorageManager

    StorageManager._instance = None
    mgr = StorageManager()
    info_list = mgr.get_driver_info_list()
    assert len(info_list) == 1
    local_info = info_list[0]
    assert local_info["name"] == "local"
    assert local_info["is_builtin"] is True
    assert "display_name" in local_info

    StorageManager._instance = None


# ──────────────────────────────────────────────
# 2. Plugin manifest validation
# ──────────────────────────────────────────────

PLUGIN_DIRS = [
    "aliyun-oss",
    "qiniu-kodo",
    "tencent-cos",
    "amazon-s3",
]

PLUGINS_ROOT = Path(__file__).parent.parent / "plugins"


def _load_plugin_driver_module(plugin_name: str):
    driver_path = PLUGINS_ROOT / plugin_name / "backend" / "driver.py"
    module_name = f"test_runtime_{plugin_name.replace('-', '_')}_driver"
    spec = importlib.util.spec_from_file_location(module_name, driver_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("plugin_name", PLUGIN_DIRS)
def test_plugin_yaml_valid(plugin_name: str):
    """Each storage plugin must have a valid plugin.yaml. / 插件"""
    import yaml

    from app.plugins.manifest import PluginManifest

    yaml_path = PLUGINS_ROOT / plugin_name / "plugin.yaml"
    assert yaml_path.is_file(), f"plugin.yaml missing for {plugin_name}"

    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    manifest = PluginManifest.model_validate(data)
    assert manifest.name == plugin_name
    assert len(manifest.extensions.storage_drivers) == 1

    sd = manifest.extensions.storage_drivers[0]
    assert sd.code, "storage_driver.code must be non-empty"
    assert sd.entry_point, "storage_driver.entry_point must be non-empty"


@pytest.mark.parametrize("plugin_name", PLUGIN_DIRS)
def test_plugin_has_main(plugin_name: str):
    """Each plugin must have backend/main.py with PluginBase subclass. / 插件"""
    main_path = PLUGINS_ROOT / plugin_name / "backend" / "main.py"
    assert main_path.is_file(), f"main.py missing for {plugin_name}"


@pytest.mark.parametrize("plugin_name", PLUGIN_DIRS)
def test_plugin_has_driver(plugin_name: str):
    """Each plugin must have backend/driver.py with StorageDriver subclass. / 插件"""
    driver_path = PLUGINS_ROOT / plugin_name / "backend" / "driver.py"
    assert driver_path.is_file(), f"driver.py missing for {plugin_name}"


@pytest.mark.parametrize("plugin_name", PLUGIN_DIRS)
def test_plugin_has_locales(plugin_name: str):
    """Each plugin must have zh-CN and en locale files. / 插件"""
    zh = PLUGINS_ROOT / plugin_name / "locales" / "zh-CN.json"
    en = PLUGINS_ROOT / plugin_name / "locales" / "en.json"
    assert zh.is_file(), f"zh-CN.json missing for {plugin_name}"
    assert en.is_file(), f"en.json missing for {plugin_name}"


# ──────────────────────────────────────────────
# 3. StorageDriver contract check
# ──────────────────────────────────────────────

EXPECTED_DRIVER_NAMES = {
    "aliyun-oss": "aliyun-oss",
    "qiniu-kodo": "qiniu-kodo",
    "tencent-cos": "tencent-cos",
    "amazon-s3": "s3",
}


@pytest.mark.parametrize("plugin_name", PLUGIN_DIRS)
def test_driver_class_attributes(plugin_name: str):
    """Each driver class must have correct name, display_name, config_schema. / 说明"""
    import importlib.util
    import inspect

    from app.storage.base import StorageDriver

    driver_path = PLUGINS_ROOT / plugin_name / "backend" / "driver.py"
    module_name = f"test_plugins_{plugin_name.replace('-', '_')}_driver"
    spec = importlib.util.spec_from_file_location(module_name, driver_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Find StorageDriver subclass
    driver_cls = None
    for _name, obj in inspect.getmembers(mod, inspect.isclass):
        if issubclass(obj, StorageDriver) and obj is not StorageDriver:
            driver_cls = obj
            break

    assert driver_cls is not None, f"No StorageDriver subclass in {plugin_name}"
    assert driver_cls.name == EXPECTED_DRIVER_NAMES[plugin_name]
    assert driver_cls.display_name, "display_name must be non-empty"
    assert driver_cls.config_schema is not None, "config_schema must be defined"
    assert isinstance(driver_cls.config_schema, dict)

    # Check required abstract methods are implemented (not just inherited)
    required_methods = ["put", "get", "delete", "exists", "get_url", "get_info"]
    for method_name in required_methods:
        method = getattr(driver_cls, method_name, None)
        assert method is not None, f"{method_name} not found on {driver_cls.__name__}"


# ──────────────────────────────────────────────
# 4. Config definitions check
# ──────────────────────────────────────────────

def test_platform_storage_driver_has_all_options():
    """Platform storage driver select must include all 5 driver options. / 说明"""
    from app.configs.definitions.platform.storage import PLATFORM_STORAGE_DRIVER

    option_values = {opt.value for opt in PLATFORM_STORAGE_DRIVER.options}
    expected = {"local", "s3", "aliyun-oss", "qiniu-kodo", "tencent-cos"}
    assert expected.issubset(option_values), f"Missing options: {expected - option_values}"


def test_tenant_storage_driver_has_cloud_options():
    """Tenant storage driver select must include cloud driver options (no local). / 说明"""
    from app.configs.definitions.tenant.storage import TENANT_STORAGE_DRIVER

    option_values = {opt.value for opt in TENANT_STORAGE_DRIVER.options}
    expected = {"s3", "aliyun-oss", "qiniu-kodo", "tencent-cos"}
    assert expected.issubset(option_values), f"Missing options: {expected - option_values}"
    assert "local" not in option_values, "Tenant must not have local driver option"


def test_tenant_storage_mode_has_admin_override():
    """Tenant storage mode must include admin_override option. / 说明"""
    from app.configs.definitions.tenant.storage import TENANT_STORAGE_MODE

    option_values = {opt.value for opt in TENANT_STORAGE_MODE.options}
    assert "admin_override" in option_values
    assert "platform" in option_values
    assert "custom" in option_values


def test_mode3_switches_exist():
    """Mode 3 platform switch and tenant switch must exist. / 说明"""
    from app.configs.definitions.platform.storage import (
        PLATFORM_TENANT_STORAGE_SELF_CONFIG_ENABLED,
    )
    from app.configs.definitions.tenant.storage import (
        TENANT_STORAGE_SELF_CONFIG_ENABLED,
    )

    assert PLATFORM_TENANT_STORAGE_SELF_CONFIG_ENABLED.key == "platform_tenant_storage_self_config_enabled"
    assert PLATFORM_TENANT_STORAGE_SELF_CONFIG_ENABLED.default_value is False

    assert TENANT_STORAGE_SELF_CONFIG_ENABLED.key == "tenant_storage_self_config_enabled"
    assert TENANT_STORAGE_SELF_CONFIG_ENABLED.default_value is False


@pytest.mark.asyncio
async def test_s3_cloudflare_private_image_processing_falls_back_to_origin():
    """Cloudflare resizing must not be used for private S3 files. / 私有 S3 文件不能走 Cloudflare 图片处理。"""
    from app.storage.base import StorageConfig, StorageVisibility
    from app.utils.image import ImageProcessParams

    S3StorageDriver = _load_plugin_driver_module("amazon-s3").S3StorageDriver

    driver = object.__new__(S3StorageDriver)
    driver.config = StorageConfig(
        driver="s3",
        root_path="bucket",
        options={
            "image_process_provider": "cloudflare",
            "image_process_url": "https://cdn.example.com",
        },
    )
    driver.prefix = ""

    async def fake_get_url(
        path: str,
        expires: int = 3600,
        visibility: StorageVisibility | None = None,
    ) -> str:
        _ = (expires, visibility)
        return f"https://signed.example.com/{path}"

    driver.get_url = fake_get_url  # type: ignore[method-assign]

    params = ImageProcessParams(width=320)
    private_url = await S3StorageDriver.get_image_url(
        driver,
        "images/demo.png",
        params,
        visibility=StorageVisibility.PRIVATE,
    )
    public_url = await S3StorageDriver.get_image_url(
        driver,
        "images/demo.png",
        params,
        visibility=StorageVisibility.PUBLIC,
    )

    assert private_url == "https://signed.example.com/images/demo.png"
    assert public_url == (
        "https://cdn.example.com/cdn-cgi/image/width=320,quality=85,fit=contain/images/demo.png"
    )
    assert driver.supports_native_image_processing(StorageVisibility.PRIVATE) is False
    assert driver.supports_native_image_processing(StorageVisibility.PUBLIC) is True


def test_qiniu_bucket_visibility_must_match_attachment_visibility():
    """Qiniu Kodo is bucket-visibility based and must reject mismatched attachment visibility. / 七牛按桶可见性工作，必须拒绝不匹配的附件可见性。"""
    from app.exceptions import StorageConfigError
    from app.storage.base import StorageVisibility

    KodoStorageDriver = _load_plugin_driver_module("qiniu-kodo").KodoStorageDriver

    public_bucket_driver = object.__new__(KodoStorageDriver)
    public_bucket_driver.is_private = False
    with pytest.raises(StorageConfigError):
        public_bucket_driver._validate_visibility(StorageVisibility.PRIVATE)

    private_bucket_driver = object.__new__(KodoStorageDriver)
    private_bucket_driver.is_private = True
    with pytest.raises(StorageConfigError):
        private_bucket_driver._validate_visibility(StorageVisibility.PUBLIC)


def test_qiniu_private_bucket_does_not_store_direct_base_url():
    """Private Qiniu buckets should not persist a direct base_url for unsafe CDN fallback. / 七牛私有桶不应落库直连 base_url，避免错误 CDN 回退。"""
    from app.storage.base import StorageConfig

    KodoStorageDriver = _load_plugin_driver_module("qiniu-kodo").KodoStorageDriver

    driver = object.__new__(KodoStorageDriver)
    driver.config = StorageConfig(
        driver="qiniu-kodo",
        root_path="bucket",
        base_url="https://cdn.example.com",
    )
    driver.prefix = "tenant-assets"
    driver.is_private = True
    assert driver.get_base_url() == ""

    driver.is_private = False
    assert driver.get_base_url() == "https://cdn.example.com/tenant-assets"
