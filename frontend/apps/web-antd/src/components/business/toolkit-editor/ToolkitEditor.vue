<script lang="ts" setup>
/**
 * Toolkit Editor Component
 * Toolkit 编辑器组件
 *
 * Left: Monaco Editor (Python), right: real-time parse preview (tools + valves).
 * 左侧 Monaco Editor (Python)，右侧实时解析预览（tools + valves）。
 * Supports v-model two-way binding, code templates, .py file upload.
 * 支持 v-model 双向绑定、代码模板、.py 文件上传。
 */
import type { ToolkitParseResult, ToolkitToolInfo } from './types';

import { computed, defineAsyncComponent, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';
import { usePreferences } from '@vben/preferences';

import { useDebounceFn } from '@vueuse/core';
import {
  Alert,
  Badge,
  Button,
  Collapse,
  CollapsePanel,
  Dropdown,
  Menu,
  MenuItem,
  message,
  Spin,
  Tag,
  Tooltip,
  Upload,
} from 'ant-design-vue';

import { $t } from '#/locales';

defineOptions({ name: 'ToolkitEditor' });

const props = withDefaults(
  defineProps<{
    disabled?: boolean;
    /** i18n prefix, e.g. 'admin.ai.skill' */
    localePrefix?: string;
    /** parse API function — caller injects admin or tenant version */
    parseApi?: (source: string) => Promise<ToolkitParseResult>;
    value?: string;
  }>(),
  {
    value: '',
    disabled: false,
    localePrefix: 'admin.ai.skill',
    parseApi: undefined,
  },
);

const emit = defineEmits<{
  parseComplete: [schema: null | Record<string, unknown>];
  'update:value': [val: string];
}>();

// ── i18n helper ──
function t(key: string): string {
  return $t(`${props.localePrefix}.toolkitEditor.${key}`);
}

// ── Dark mode ──
const { isDark } = usePreferences();
const monacoTheme = computed(() => (isDark.value ? 'vs-dark' : 'vs'));

// ── Monaco Editor (lazy-loaded via defineAsyncComponent) ──
const MonacoEditor = defineAsyncComponent({
  loader: () => import('@guolao/vue-monaco-editor'),
  loadingComponent: { render: () => null },
});

const editorOptions = {
  minimap: { enabled: false },
  fontSize: 13,
  lineNumbers: 'on' as const,
  scrollBeyondLastLine: false,
  wordWrap: 'on' as const,
  tabSize: 4,
  insertSpaces: true,
  automaticLayout: true,
};

// ── Parse state ──
const parseResult = ref<null | ToolkitParseResult>(null);
const isParsing = ref(false);

async function doParse(source: string) {
  if (!props.parseApi || !source.trim()) {
    parseResult.value = null;
    emit('parseComplete', null);
    return;
  }
  isParsing.value = true;
  try {
    parseResult.value = await props.parseApi(source);
  } catch {
    parseResult.value = {
      tools: [],
      valves_schema: {},
      errors: [t('networkError')],
    };
  } finally {
    isParsing.value = false;
    emit('parseComplete', parseResult.value?.valves_schema ?? null);
  }
}

const debouncedParse = useDebounceFn(doParse, 800);

function handleEditorChange(val = '') {
  emit('update:value', val);
  debouncedParse(val);
}

// Auto-fill blank template when value is empty (new skill)
watch(
  () => props.value,
  (v) => {
    if (!v || !v.trim()) {
      emit('update:value', BLANK_TEMPLATE);
      debouncedParse(BLANK_TEMPLATE);
    } else if (!parseResult.value) {
      debouncedParse(v);
    }
  },
  { immediate: true },
);

// ── Computed helpers ──
const tools = computed<ToolkitToolInfo[]>(() => parseResult.value?.tools ?? []);
const valvesSchema = computed(() => parseResult.value?.valves_schema ?? {});
const hasValves = computed(() => Object.keys(valvesSchema.value).length > 0);
const errors = computed<string[]>(() => parseResult.value?.errors ?? []);
const hasErrors = computed(() => errors.value.length > 0);

const valvesProperties = computed(() => {
  const schema = valvesSchema.value as Record<string, unknown>;
  return (schema.properties ?? {}) as Record<string, Record<string, unknown>>;
});
const valvesRequired = computed(() => {
  const schema = valvesSchema.value as Record<string, unknown>;
  return (schema.required ?? []) as string[];
});

function getValveType(prop: Record<string, unknown>): string {
  const value = prop.type;
  return typeof value === 'string' && value ? value : 'string';
}

function getValveDescription(prop: Record<string, unknown>): string {
  const value = prop.description;
  return typeof value === 'string' ? value : '';
}

function hasValveDefault(prop: Record<string, unknown>): boolean {
  return Object.prototype.hasOwnProperty.call(prop, 'default');
}

function getValveDefault(prop: Record<string, unknown>): unknown {
  return prop.default;
}

// ── Templates ──
const BLANK_TEMPLATE = `"""
title: My Toolkit
description: A custom toolkit
version: 0.1.0
"""

from pydantic import BaseModel, Field


class Valves(BaseModel):
    api_key: str = Field("", description="API Key")


class Tools:
    def __init__(self):
        self.valves = Valves()

    def hello(self, name: str) -> str:
        """
        Say hello to someone.
        :param name: The person's name
        """
        return f"Hello, {name}!"
`;

const EXAMPLE_TEMPLATE = `"""
title: Weather Toolkit
description: Get weather information for a city
version: 0.1.0
author: NovusAI
requirements: httpx
"""

from pydantic import BaseModel, Field


class Valves(BaseModel):
    api_key: str = Field("", description="Weather API Key")
    base_url: str = Field(
        "https://api.weatherapi.com/v1",
        description="Weather API Base URL",
    )


class Tools:
    def __init__(self):
        self.valves = Valves()

    async def get_current_weather(self, city: str) -> str:
        """
        Get the current weather for a city.
        :param city: City name, e.g. 'Beijing'
        """
        import httpx

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.valves.base_url}/current.json",
                params={"key": self.valves.api_key, "q": city},
            )
            resp.raise_for_status()
            data = resp.json()
            current = data.get("current", {})
            return (
                f"{city}: {current.get('temp_c')}°C, "
                f"{current.get('condition', {}).get('text', 'N/A')}"
            )

    def convert_temperature(self, celsius: float) -> str:
        """
        Convert Celsius to Fahrenheit.
        :param celsius: Temperature in Celsius
        """
        f = celsius * 9 / 5 + 32
        return f"{celsius}°C = {f:.1f}°F"
`;

function applyTemplate(tpl: string) {
  emit('update:value', tpl);
  debouncedParse(tpl);
}

// ── File upload ──
function handleBeforeUpload(file: File): false {
  if (!file.name.endsWith('.py')) {
    message.error(t('onlyPyFiles'));
    return false;
  }
  file
    .text()
    .then((content) => {
      emit('update:value', content);
      debouncedParse(content);
      message.success(file.name);
    })
    .catch(() => {
      message.error(t('networkError'));
    });
  return false;
}

// ── Active panel for collapse ──
const activeKeys = ref<string[]>(['tools']);
</script>

<template>
  <div class="flex h-full min-h-[400px] gap-3">
    <!-- Left: Editor -->
    <div class="flex min-w-0 flex-1 flex-col">
      <!-- Toolbar -->
      <div class="mb-2 flex items-center gap-2">
        <Dropdown :trigger="['click']">
          <Button size="small">
            <template #icon>
              <IconifyIcon icon="lucide:file-code" class="size-3.5" />
            </template>
            {{ t('templateBlank') }}
            <IconifyIcon icon="lucide:chevron-down" class="ml-1 size-3" />
          </Button>
          <template #overlay>
            <Menu>
              <MenuItem @click="applyTemplate(BLANK_TEMPLATE)">
                <IconifyIcon icon="lucide:file" class="mr-1.5 size-3.5" />
                {{ t('templateBlank') }}
              </MenuItem>
              <MenuItem @click="applyTemplate(EXAMPLE_TEMPLATE)">
                <IconifyIcon
                  icon="lucide:file-code-2"
                  class="mr-1.5 size-3.5"
                />
                {{ t('templateExample') }}
              </MenuItem>
            </Menu>
          </template>
        </Dropdown>
        <Upload
          :before-upload="handleBeforeUpload"
          accept=".py"
          :show-upload-list="false"
          :disabled="props.disabled"
        >
          <Button size="small" :disabled="props.disabled">
            <template #icon>
              <IconifyIcon icon="lucide:upload" class="size-3.5" />
            </template>
            {{ t('uploadFile') }}
          </Button>
        </Upload>
      </div>
      <!-- Monaco -->
      <div class="flex-1 overflow-hidden rounded border border-border">
        <Suspense>
          <MonacoEditor
            :value="props.value"
            language="python"
            :theme="monacoTheme"
            :options="editorOptions"
            @change="handleEditorChange"
          />
          <template #fallback>
            <div
              class="flex h-full items-center justify-center text-muted-foreground"
            >
              <Spin />
            </div>
          </template>
        </Suspense>
      </div>
    </div>

    <!-- Right: Preview -->
    <div
      class="w-[320px] shrink-0 overflow-y-auto rounded border border-border p-3"
    >
      <div
        class="mb-2 flex items-center gap-2 text-sm font-medium text-foreground"
      >
        <IconifyIcon icon="lucide:scan-search" class="size-4" />
        {{ t('preview') }}
        <Spin v-if="isParsing" size="small" class="ml-auto" />
      </div>

      <!-- Errors -->
      <Alert
        v-if="hasErrors"
        type="error"
        :message="t('errors')"
        show-icon
        class="mb-3"
      >
        <template #description>
          <ul class="m-0 list-disc pl-4 text-xs">
            <li v-for="(err, i) in errors" :key="i">{{ err }}</li>
          </ul>
        </template>
      </Alert>

      <!-- Tools -->
      <Collapse
        v-model:active-key="activeKeys"
        :bordered="false"
        size="small"
        class="bg-transparent"
      >
        <CollapsePanel key="tools" :header="t('tools')">
          <template #extra>
            <Badge
              :count="tools.length"
              :number-style="{
                backgroundColor: tools.length > 0 ? '#52c41a' : '#d9d9d9',
              }"
            />
          </template>
          <div v-if="tools.length === 0" class="text-xs text-muted-foreground">
            {{ t('noTools') }}
          </div>
          <div v-for="tool in tools" :key="tool.name" class="mb-3 last:mb-0">
            <div class="flex items-center gap-1.5">
              <IconifyIcon icon="lucide:wrench" class="size-3.5 text-primary" />
              <span class="text-sm font-medium text-foreground">{{
                tool.name
              }}</span>
              <Tag
                v-if="tool.is_async"
                color="blue"
                class="ml-auto text-[10px] leading-tight"
              >
                {{ t('async') }}
              </Tag>
            </div>
            <p
              v-if="tool.description"
              class="mt-0.5 text-xs leading-relaxed text-muted-foreground"
            >
              {{ tool.description }}
            </p>
            <div v-if="tool.parameters.length > 0" class="mt-1.5">
              <div
                class="mb-1 text-[10px] uppercase tracking-wider text-muted-foreground"
              >
                {{ t('parameters') }}
              </div>
              <div
                v-for="param in tool.parameters"
                :key="param.name"
                class="mb-1 flex items-center gap-1.5 rounded bg-accent/50 px-2 py-1 text-xs"
              >
                <code class="font-mono text-[11px] text-foreground">{{
                  param.name
                }}</code>
                <Tag
                  :color="param.required ? 'red' : 'default'"
                  class="text-[10px] leading-tight"
                >
                  {{ param.type }}
                </Tag>
                <Tooltip v-if="param.description" :title="param.description">
                  <IconifyIcon
                    icon="lucide:info"
                    class="size-3 cursor-help text-muted-foreground"
                  />
                </Tooltip>
                <span
                  v-if="param.required"
                  class="ml-auto text-[10px] text-destructive"
                  >*</span
                >
              </div>
            </div>
          </div>
        </CollapsePanel>

        <!-- Valves -->
        <CollapsePanel key="valves" :header="t('valves')">
          <template #extra>
            <Badge
              :count="Object.keys(valvesProperties).length"
              :number-style="{
                backgroundColor: hasValves ? '#1677ff' : '#d9d9d9',
              }"
            />
          </template>
          <div v-if="!hasValves" class="text-xs text-muted-foreground">
            {{ t('noValves') }}
          </div>
          <div v-else>
            <div
              v-for="(prop, fieldName) in valvesProperties"
              :key="fieldName"
              class="mb-1.5 rounded bg-accent/50 px-2 py-1.5 text-xs"
            >
              <div class="flex items-center gap-1.5">
                <code class="font-mono text-[11px] text-foreground">{{
                  fieldName
                }}</code>
                <Tag color="processing" class="text-[10px] leading-tight">
                  {{ getValveType(prop) }}
                </Tag>
                <span
                  v-if="valvesRequired.includes(fieldName)"
                  class="ml-auto text-[10px] text-destructive"
                  >*</span
                >
              </div>
              <p
                v-if="getValveDescription(prop)"
                class="mt-0.5 leading-relaxed text-muted-foreground"
              >
                {{ getValveDescription(prop) }}
              </p>
              <div
                v-if="hasValveDefault(prop)"
                class="mt-0.5 text-muted-foreground"
              >
                {{ t('default') }}:
                <code>{{ JSON.stringify(getValveDefault(prop)) }}</code>
              </div>
            </div>
          </div>
        </CollapsePanel>
      </Collapse>
    </div>
  </div>
</template>
