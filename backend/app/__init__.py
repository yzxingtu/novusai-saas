"""
NovusAI SaaS Backend Application
"""

import warnings

# 抑制 requests 库版本兼容检查的噪音警告（urllib3/charset_normalizer 版本超出其预设测试范围，实际兼容）
# 放在此处以确保在 reloader 进程和 worker 进程中均生效（app/__init__.py 是最早被导入的文件）
warnings.filterwarnings("ignore", category=Warning, module=r"requests\.__init__")

__version__ = "0.1.0"

