<script lang="ts" setup>
/**
 * 插件安装向导 — 两步流程：上传 → 预览确认（参考旧版 PluginInstallWizard）
 */
import type { InstallPreview } from '#/api/admin/plugin';

import { computed, ref } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Alert, Button, message, Modal, Tag, Upload } from 'ant-design-vue';

import { installPluginApi, previewPluginInstallApi } from '#/api/admin/plugin';
import { $t } from '#/locales';
import { resolvePluginMetadataIcon } from '#/utils/plugin-metadata-icon';
import { getScopeColor, getScopeText } from '#/utils/scope-helpers';

import { derivePluginType, getTypeColor, getTypeText } from '../data';

const emit = defineEmits<{
  installed: [];
}>();

const visible = ref(false);
const step = ref<'preview' | 'upload'>('upload');
const installing = ref(false);
const previewLoading = ref(false);

const selectedFile = ref<File | null>(null);
const previewInfo = ref<InstallPreview | null>(null);
const expandedItems = ref<Set<string>>(new Set());

const MAX_FILE_SIZE = 50 * 1024 * 1024;

// Structure type → icon (label via i18n) / 结构类型 → 图标（label 通过 i18n 获取）
const structureTypeIcons: Record<string, string> = {
  skills: 'lucide:sparkles',
  api_routes: 'lucide:route',
  hooks: 'lucide:anchor',
  events: 'lucide:radio',
  webhooks: 'lucide:webhook',
  tasks: 'lucide:clock',
  adapters: 'lucide:cpu',
  storage_drivers: 'lucide:database',
  notifications: 'lucide:bell',
  permissions: 'lucide:shield',
  frontend_menus: 'lucide:menu',
};

function open() {
  visible.value = true;
  step.value = 'upload';
  selectedFile.value = null;
  previewInfo.value = null;
  expandedItems.value.clear();
}

function close() {
  visible.value = false;
}

function toggleExpand(type: string) {
  if (expandedItems.value.has(type)) {
    expandedItems.value.delete(type);
  } else {
    expandedItems.value.add(type);
  }
}

async function handleBeforeUpload(file: File) {
  if (!(file instanceof File)) return false;

  if (file.size > MAX_FILE_SIZE) {
    message.error($t('admin.plugin.messages.fileTooLarge'));
    return false;
  }

  selectedFile.value = file;
  previewLoading.value = true;

  try {
    const result = await previewPluginInstallApi(file);
    previewInfo.value = result;
    step.value = 'preview';
  } catch {
    selectedFile.value = null;
  } finally {
    previewLoading.value = false;
  }

  return false;
}

function goBackToUpload() {
  step.value = 'upload';
  selectedFile.value = null;
  previewInfo.value = null;
  expandedItems.value.clear();
}

async function handleInstall() {
  if (!selectedFile.value) return;

  installing.value = true;
  try {
    await installPluginApi(selectedFile.value);
    message.success($t('admin.plugin.messages.installSuccess'));
    close();
    emit('installed');
  } catch (error: unknown) {
    const errMsg =
      (error as Record<string, unknown>)?.message ||
      (error as Record<string, unknown>)?.data;
    if (errMsg) {
      message.error(String(errMsg));
    }
  } finally {
    installing.value = false;
  }
}

const pluginInfo = computed(
  () => (previewInfo.value?.plugin_info || {}) as Record<string, unknown>,
);
const pluginName = computed(
  () =>
    (pluginInfo.value.display_name as string) ||
    (pluginInfo.value.name as string) ||
    '',
);
const pluginVersion = computed(
  () => (pluginInfo.value.version as string) || '',
);
const pluginDesc = computed(
  () => (pluginInfo.value.description as string) || '',
);
const pluginAuthor = computed(() => (pluginInfo.value.author as string) || '');
const pluginIcon = computed(() => (pluginInfo.value.icon as string) || '');
const pluginScope = computed(
  () => (pluginInfo.value.scope as string) || 'all_tenants',
);

const installManifest = computed(
  () => (previewInfo.value?.install_manifest || {}) as Record<string, number>,
);

const structureSummary = computed(() => {
  const manifest = installManifest.value as Record<string, unknown>;
  const items: Array<{
    count: number;
    details: string[];
    icon: string;
    label: string;
    type: string;
  }> = [];
  for (const [type, icon] of Object.entries(structureTypeIcons)) {
    const count = (manifest[type] as number) || 0;
    if (count > 0) {
      const detailsKey = `${type}_details`;
      const details = (manifest[detailsKey] as string[]) || [];
      items.push({
        type,
        count,
        icon,
        label: $t(`admin.plugin.structureType.${type}`),
        details,
      });
    }
  }
  return items;
});

const pluginType = computed(() =>
  derivePluginType(
    (previewInfo.value?.install_manifest as Record<string, unknown>) ?? null,
  ),
);
const capabilities = computed(() => previewInfo.value?.capabilities || []);
const conflicts = computed(() => previewInfo.value?.conflicts || []);
const warnings = computed(() => previewInfo.value?.warnings || []);
const deps = computed(
  () => (previewInfo.value?.dependencies || {}) as Record<string, string[]>,
);

const resolvedPluginMetadataIcon = computed(() =>
  resolvePluginMetadataIcon(
    String(pluginInfo.value.name || 'unknown'),
    pluginIcon.value,
    {
      endpoint: 'admin',
    },
  ),
);

defineExpose({ open });
</script>

<template>
  <Modal
    v-model:open="visible"
    :title="
      step === 'upload'
        ? $t('admin.plugin.upload')
        : $t('admin.plugin.preview.title')
    "
    :footer="null"
    :destroy-on-close="true"
    :width="step === 'preview' ? 700 : 520"
    :mask-closable="!installing"
    :closable="!installing"
  >
    <!-- ===== Step 1: Upload ===== -->
    <div v-if="step === 'upload'" class="py-2">
      <Upload.Dragger
        accept=".zip"
        :multiple="false"
        :show-upload-list="false"
        :disabled="previewLoading"
        :before-upload="handleBeforeUpload"
      >
        <div class="flex flex-col items-center gap-4 py-10">
          <div
            class="flex size-16 items-center justify-center rounded-2xl shadow-lg"
            :style="{
              background:
                'linear-gradient(135deg, hsl(var(--primary)) 0%, hsl(var(--primary) / 75%) 100%)',
            }"
          >
            <IconifyIcon
              :icon="previewLoading ? 'lucide:loader-2' : 'lucide:cloud-upload'"
              class="size-8 text-white"
              :class="{ 'animate-spin': previewLoading }"
            />
          </div>
          <div class="flex flex-col items-center gap-1.5">
            <span class="text-sm font-semibold text-foreground">
              {{
                previewLoading
                  ? $t('admin.plugin.preview.title')
                  : $t('admin.plugin.upload')
              }}
            </span>
            <span class="text-xs text-muted-foreground"> .zip &lt; 50MB </span>
          </div>
        </div>
      </Upload.Dragger>
    </div>

    <!-- ===== Step 2: Preview + Confirm ===== -->
    <div
      v-else-if="step === 'preview' && previewInfo"
      class="flex flex-col gap-5 py-3"
    >
      <!-- 插件基本信息 -->
      <div class="flex items-start gap-4">
        <div
          class="flex size-14 shrink-0 items-center justify-center overflow-hidden rounded-xl bg-primary/10"
        >
          <img
            v-if="resolvedPluginMetadataIcon.kind === 'image'"
            :src="resolvedPluginMetadataIcon.src"
            class="size-7 rounded"
            :alt="pluginName"
          />
          <IconifyIcon
            v-else
            :icon="resolvedPluginMetadataIcon.icon"
            class="size-7 text-primary"
          />
        </div>
        <div class="min-w-0 flex-1">
          <h3 class="text-lg font-bold text-foreground">{{ pluginName }}</h3>
          <div
            class="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground"
          >
            <span class="font-mono">v{{ pluginVersion }}</span>
            <template v-if="pluginAuthor">
              <span class="text-border">·</span>
              <span>{{ pluginAuthor }}</span>
            </template>
          </div>
          <p
            v-if="pluginDesc"
            class="mt-2 text-sm leading-relaxed text-muted-foreground"
          >
            {{ pluginDesc }}
          </p>
        </div>
      </div>

      <!-- 插件结构摘要（可展开的芯片） -->
      <div
        v-if="structureSummary.length > 0"
        class="rounded-xl border border-border/60 bg-muted/30 p-4"
      >
        <h4 class="mb-3 text-sm font-semibold text-foreground">
          {{ $t('admin.plugin.preview.extensions') }}
        </h4>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="item in structureSummary"
            :key="item.type"
            class="inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-all"
            :class="
              expandedItems.has(item.type)
                ? 'border-primary/40 bg-primary/10 text-primary'
                : 'border-border/60 bg-background text-foreground hover:border-primary/30 hover:bg-primary/5'
            "
            @click="toggleExpand(item.type)"
          >
            <IconifyIcon :icon="item.icon" class="size-3.5" />
            <span>{{ item.label }}</span>
            <span
              class="rounded bg-primary/15 px-1 text-[10px] font-bold text-primary"
            >
              {{ item.count }}
            </span>
          </button>
        </div>
        <!-- 展开的详情面板 -->
        <template v-for="item in structureSummary" :key="`detail-${item.type}`">
          <div
            v-if="expandedItems.has(item.type) && item.details.length > 0"
            class="mt-3 rounded-lg border border-border/40 bg-background px-3 py-2"
          >
            <div
              class="mb-1.5 flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground"
            >
              <IconifyIcon :icon="item.icon" class="size-3" />
              {{ item.label }}
            </div>
            <div class="flex flex-wrap gap-1.5">
              <code
                v-for="(detail, idx) in item.details"
                :key="idx"
                class="rounded-md bg-muted/60 px-2 py-0.5 text-[11px] text-foreground/80"
                >{{ detail }}</code
              >
            </div>
          </div>
        </template>
      </div>

      <!-- 能力授权 -->
      <div
        v-if="capabilities.length > 0"
        class="rounded-xl border border-border/60 bg-muted/30 p-4"
      >
        <h4 class="mb-3 text-sm font-semibold text-foreground">
          {{ $t('admin.plugin.preview.capabilities') }}
        </h4>
        <div class="flex flex-wrap gap-2">
          <div
            v-for="cap in capabilities"
            :key="cap.code"
            class="border-geekblue-200 bg-geekblue-50 dark:border-geekblue-700 dark:bg-geekblue-900/30 inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs"
          >
            <IconifyIcon icon="lucide:key" class="text-geekblue-500 size-3.5" />
            <span class="font-medium">{{ cap.code }}</span>
            <span
              v-if="cap.description && cap.description !== cap.code"
              class="text-muted-foreground"
            >
              — {{ cap.description }}
            </span>
          </div>
        </div>
      </div>

      <!-- 标签行 -->
      <div class="flex flex-wrap items-center gap-1.5">
        <Tag :color="getTypeColor(pluginType)" class="!m-0 !rounded-md">
          {{ getTypeText(pluginType) }}
        </Tag>
        <Tag :color="getScopeColor(pluginScope)" class="!m-0 !rounded-md">
          {{ getScopeText(pluginScope) }}
        </Tag>
        <Tag
          v-if="deps.python && deps.python.length > 0"
          color="orange"
          class="!m-0 !rounded-md"
        >
          <IconifyIcon icon="lucide:package" class="mr-0.5 inline size-3" />
          {{ deps.python.length }} Python deps
        </Tag>
        <Tag
          v-if="deps.plugins && deps.plugins.length > 0"
          color="cyan"
          class="!m-0 !rounded-md"
        >
          <IconifyIcon icon="lucide:plug" class="mr-0.5 inline size-3" />
          {{ deps.plugins.length }} plugin deps
        </Tag>
      </div>

      <!-- 冲突警告 -->
      <Alert
        v-if="conflicts.length > 0"
        type="error"
        show-icon
        :message="$t('admin.plugin.preview.conflicts')"
        :description="
          conflicts
            .map((c: Record<string, string>) => c.name || c.reason)
            .join(', ')
        "
      />

      <!-- 警告 -->
      <Alert
        v-for="(warn, idx) in warnings"
        :key="idx"
        type="warning"
        show-icon
        :message="warn"
      />

      <!-- 操作按钮 -->
      <div
        class="flex items-center justify-between border-t border-border/40 pt-4"
      >
        <Button @click="goBackToUpload">
          <IconifyIcon icon="lucide:arrow-left" class="mr-1.5 size-4" />
          {{ $t('admin.plugin.preview.cancel') }}
        </Button>
        <Button
          type="primary"
          size="large"
          :loading="installing"
          :disabled="conflicts.length > 0"
          class="!rounded-xl !px-6 !shadow-lg !shadow-primary/20"
          @click="handleInstall"
        >
          <IconifyIcon icon="lucide:download" class="mr-1.5 size-4" />
          {{ $t('admin.plugin.preview.confirmInstall') }}
        </Button>
      </div>
    </div>
  </Modal>
</template>
