"""Scaffold templates for plugin_cli. / plugin_cli 的脚手架模板资源。"""

_MINIMAL_PLUGIN_YAML = """name: {name}
version: "1.0.0"
display_name:
  zh-CN: "{display_name}"
  en: "{display_name_en}"
description:
  zh-CN: "{description}"
  en: "{description_en}"
author: ""
icon: ""
scope: all_tenants

capabilities: []

extensions: {{}}

dependencies:
  python: []
  plugins: []

pricing:
  type: free
"""

_MINIMAL_MAIN_PY = '''"""
{display_name} 插件
"""

from app.plugins.base import PluginBase


class {class_name}Plugin(PluginBase):
    """{display_name}"""

    async def on_install(self, ctx) -> None:
        ctx.get_logger().info("{name} installed")

    async def on_enable(self, ctx) -> None:
        ctx.get_logger().info("{name} enabled")
'''

_SKILL_RESOLVER_PY = '''"""
{display_name} 技能解析器
"""

from app.ai.tools.types import ToolDefinition, ToolParameter


def resolve(skill, config: dict) -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="{name}_query",
            description="TODO: describe your tool",
            tool_type="{name}",
            parameters=[
                ToolParameter(
                    name="input",
                    type="string",
                    description="Input parameter",
                    required=True,
                ),
            ],
            config=config,
            enabled=True,
        ),
    ]
'''

_SKILL_EXECUTOR_PY = '''"""
{display_name} 工具执行器
"""

from __future__ import annotations

import time
from typing import Any, TYPE_CHECKING

from app.ai.tools.executors.base import BaseToolExecutor
from app.ai.tools.types import ToolDefinition, ToolResult

if TYPE_CHECKING:
    from app.ai.tools.types import ExecutionContext


class {class_name}Executor(BaseToolExecutor):
    """{display_name} 执行器"""

    async def validate(self, definition: ToolDefinition, arguments: dict[str, Any]) -> bool:
        return bool(arguments.get("input"))

    async def execute(
        self,
        definition: ToolDefinition,
        tool_call_id: str,
        arguments: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> ToolResult:
        start = time.perf_counter()
        # TODO: implement your tool logic
        output = f"Result for: {{arguments.get('input', '')}}"
        duration_ms = int((time.perf_counter() - start) * 1000)
        return ToolResult(
            tool_call_id=tool_call_id,
            name=definition.name,
            success=True,
            output=output,
            duration_ms=duration_ms,
        )
'''

_SKILL_PLUGIN_YAML_EXT = """
extensions:
  skills:
    - name: {name}-query
      type: {name}
      display_name:
        zh-CN: "{display_name}"
        en: "{display_name_en}"
      entry_point: "skills.{name_underscore}_resolver"
"""

_FULLMOD_YAML_FRONTEND_EXT = """
  frontend:
    pages:
      - name: "{name_underscore}_admin_home"
        path: "/admin/plugins/{name}"
        component: "{class_name}Page"
        scope: "admin"
        icon: "lucide:puzzle"
        # pages[*].title controls the host route/page title.
        title:
          zh-CN: "{display_name}"
          en: "{display_name_en}"
        menu:
          parent: "system_mgmt"
          sort_order: 95
          icon: "lucide:puzzle"
          # pages[*].menu.title controls the host sidebar label, not registerLocale().
          title:
            zh-CN: "{display_name}"
            en: "{display_name_en}"
    dev:
      entry: "src/index.ts"
    release:
      manifest: "plugin.manifest.json"
"""

_FE_INDEX_TS = '''/**
 * {display_name} 插件前端入口
 * registerLocale() 只负责页面内部文案；菜单标题与页面标题仍来自 plugin.yaml 的
 * pages[*].title / pages[*].menu.title。
 */
import type {{ NovusPluginSharedAPI }} from './types';

import {class_name}Page from './{class_name}Page.vue';
import {{ zhCN, enUS }} from './locales';

export function setup(): void {{
  const shared = (window as unknown as Record<string, unknown>)
    .NovusPluginShared as NovusPluginSharedAPI | undefined;

  if (shared?.registerLocale) {{
    // registerLocale() only affects plugin-internal copy.
    // Host menu/page titles still come from plugin.yaml pages[*].title / pages[*].menu.title.
    shared.registerLocale('zh-CN', 'plugin.{name}', zhCN);
    shared.registerLocale('zh', 'plugin.{name}', zhCN);
    shared.registerLocale('en-US', 'plugin.{name}', enUS);
    shared.registerLocale('en', 'plugin.{name}', enUS);
  }}
}}

export {{ {class_name}Page }};
'''

_FE_LOCALES_TS = '''/**
 * {display_name} 插件 i18n
 * 这里的 key 传相对 key，例如 {{ title, description }}；
 * 不要再写完整前缀 plugin.{name}.title，prefix 由宿主在 registerLocale() 时包裹。
 */
export const zhCN: Record<string, string> = {{
  title: "{display_name}",
  description: "{display_name}插件",
}};

export const enUS: Record<string, string> = {{
  title: "{display_name_en}",
  description: "{display_name_en} plugin",
}};
'''

_FE_TYPES_TS = '''/**
 * 宿主共享 API 类型声明（仅用于类型提示，不打入 bundle）
 */
export interface NovusPluginSharedAPI {{
  requestClient: {{
    get: <T = unknown>(url: string, config?: Record<string, unknown>) => Promise<T>;
    post: <T = unknown>(url: string, data?: unknown, config?: Record<string, unknown>) => Promise<T>;
  }};
  $t: (key: string, ...args: unknown[]) => string;
  IconifyIcon: unknown;
  usePluginSlotsStore: () => unknown;
  // Only registers plugin-internal i18n messages; it does not change manifest-derived menu/page titles.
  registerLocale: (locale: string, prefix: string, messages: Record<string, unknown>) => void;
}}
'''

_FE_PAGE_VUE = '''<script lang="ts" setup>
import {{ $t }} from '@novus/plugin-shared';
</script>

<template>
  <section class="{prefix}-page">
    <h1>{{{{ $t('plugin.{name}.title') }}}}</h1>
    <p>{{{{ $t('plugin.{name}.description') }}}}</p>
  </section>
</template>

<style>
.{prefix}-page {{
  padding: 24px;
}}

.{prefix}-page h1 {{
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 8px;
}}

.{prefix}-page p {{
  color: rgb(100 116 139);
  line-height: 1.6;
}}
</style>
'''

_FE_PACKAGE_JSON = '''{{
  "name": "@novus-plugin/{name}",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": {{
    "build": "vite build"
  }},
  "devDependencies": {{
    "@vitejs/plugin-vue": "^5.2.0",
    "typescript": "~5.7.0",
    "vite": "^6.0.0",
    "vue": "^3.5.0"
  }}
}}
'''

_FE_VITE_CONFIG_TS = '''/**
 * 插件前端 UMD 构建配置
 *
 * 正式运行时由 dist/plugin.manifest.json 声明入口与资源，不再固定依赖 dist/index.js。
 */
import {{ defineConfig }} from 'vite';
import vue from '@vitejs/plugin-vue';
import {{ resolve }} from 'node:path';

export default defineConfig({{
  plugins: [vue()],
  build: {{
    outDir: 'dist',
    emptyOutDir: true,
    lib: {{
      entry: resolve(__dirname, 'src/index.ts'),
      name: 'NovusPlugin_{name_underscore}',
      formats: ['umd'],
      fileName: () => 'plugin.js',
    }},
    rollupOptions: {{
      external: ['vue', 'vue-router', 'ant-design-vue', '@novus/plugin-shared'],
      output: {{
        globals: {{
          vue: 'Vue',
          'vue-router': 'VueRouter',
          'ant-design-vue': 'AntDesignVue',
          '@novus/plugin-shared': 'NovusPluginShared',
        }},
        assetFileNames: 'assets/[name][extname]',
      }},
    }},
    cssCodeSplit: true,
    minify: 'esbuild',
  }},
}});
'''

_FE_GITIGNORE = """node_modules/
dist/
"""

_STORAGE_YAML_EXT = """
extensions:
  storage_drivers:
    - code: {name}
      display_name:
        zh-CN: "{display_name}存储"
        en: "{display_name_en} Storage"
      entry_point: "backend.driver.{class_name}Driver"

config_schema:
  type: object
  properties:
    access_key:
      type: string
      x-encrypted: true
      title: Access Key
    secret_key:
      type: string
      x-encrypted: true
      title: Secret Key
    bucket:
      type: string
      title: Bucket Name
  required: [access_key, secret_key, bucket]
"""

_STORAGE_DRIVER_PY = '''"""\n{display_name} 存储驱动\n"""
from __future__ import annotations
from typing import Any

from app.storage.base import StorageDriver


class {class_name}Driver(StorageDriver):
    name = "{name}"

    def __init__(self, config: dict[str, Any]) -> None:
        self._access_key = config.get("access_key", "")
        self._secret_key = config.get("secret_key", "")
        self._bucket = config.get("bucket", "")

    async def put(self, path: str, content: Any, mime_type: str | None = None, **kwargs: Any) -> Any:
        raise NotImplementedError

    async def get(self, path: str) -> Any:
        raise NotImplementedError

    async def delete(self, path: str) -> bool:
        raise NotImplementedError

    async def exists(self, path: str) -> bool:
        raise NotImplementedError

    async def get_url(self, path: str, expires: int = 3600, **kwargs: Any) -> str:
        raise NotImplementedError
'''
