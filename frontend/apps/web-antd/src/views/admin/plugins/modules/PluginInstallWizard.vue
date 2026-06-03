<script lang="ts" setup>
/**
 * 插件安装向导 — 两步流程：上传 → 预览确认（参考旧版 PluginInstallWizard）
 */
import type { InstallPreview } from '#/api/admin/plugin';
import type { MarketplacePluginItem } from '#/api/admin/plugin-marketplace';

import { computed, ref } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Alert, Button, message, Modal, Tag, Upload } from 'ant-design-vue';

import {
  getPluginTenantExposureColor,
  getPluginTenantExposureLabelKey,
  installPluginApi,
  previewPluginInstallApi,
  resolvePluginCompatibilityProfile,
} from '#/api/admin/plugin';
import {
  marketplaceConfirmInstallApi,
  marketplacePreviewInstallApi,
} from '#/api/admin/plugin-marketplace';
import { $t } from '#/locales';
import { resolvePluginMetadataIcon } from '#/utils/plugin-metadata-icon';
import { getScopeColor, getScopeText } from '#/utils/scope-helpers';

import { getTypeColor, getTypeText } from '../data';
import {
  deriveInstallPreviewPluginType,
  summarizeInstallManifest,
} from '../plugin-preview';

const emit = defineEmits<{
  installed: [];
}>();

type InstallSource = 'marketplace' | 'upload';
type MarketplaceInstallTarget = Pick<
  MarketplacePluginItem,
  'display_name' | 'name' | 'slug' | 'version'
>;

const visible = ref(false);
const installSource = ref<InstallSource>('upload');
const step = ref<'preview' | 'upload'>('upload');
const installing = ref(false);
const previewLoading = ref(false);

const marketplaceTarget = ref<MarketplaceInstallTarget | null>(null);
const selectedFile = ref<File | null>(null);
const previewInfo = ref<InstallPreview | null>(null);
const expandedItems = ref<Set<string>>(new Set());

const MAX_FILE_SIZE = 50 * 1024 * 1024;

function resetPreviewStep() {
  previewInfo.value = null;
  expandedItems.value.clear();
}

function resetWizard() {
  installSource.value = 'upload';
  step.value = 'upload';
  previewLoading.value = false;
  installing.value = false;
  marketplaceTarget.value = null;
  selectedFile.value = null;
  resetPreviewStep();
}

function open() {
  resetWizard();
  visible.value = true;
}

async function openMarketplace(plugin: MarketplaceInstallTarget) {
  resetWizard();
  installSource.value = 'marketplace';
  marketplaceTarget.value = plugin;
  visible.value = true;
  step.value = 'preview';
  previewLoading.value = true;

  try {
    previewInfo.value = await marketplacePreviewInstallApi(
      plugin.slug || plugin.name,
    );
  } catch {
    visible.value = false;
    resetWizard();
  } finally {
    previewLoading.value = false;
  }
}

function close(force = false) {
  if (!force && (installing.value || previewLoading.value)) return;
  visible.value = false;
  resetWizard();
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
  installSource.value = 'upload';
  resetPreviewStep();
  step.value = 'preview';
  previewLoading.value = true;

  try {
    const result = await previewPluginInstallApi(file);
    previewInfo.value = result;
  } catch {
    selectedFile.value = null;
    step.value = 'upload';
  } finally {
    previewLoading.value = false;
  }

  return false;
}

function goBackToUpload() {
  if (installSource.value === 'marketplace') {
    close(true);
    return;
  }
  selectedFile.value = null;
  resetPreviewStep();
  step.value = 'upload';
}

async function handleInstall() {
  const previewToken = previewInfo.value?.preview_token;
  if (!previewToken) return;

  installing.value = true;
  try {
    if (installSource.value === 'marketplace') {
      const target = marketplaceTarget.value;
      const slug = target?.slug || target?.name;
      if (!slug) return;
      await marketplaceConfirmInstallApi(slug, {
        previewToken,
      });
    } else {
      if (!selectedFile.value) return;
      await installPluginApi(selectedFile.value, previewToken);
    }
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
  () => previewInfo.value?.install_manifest ?? {},
);

const structureSummary = computed(() =>
  summarizeInstallManifest(installManifest.value),
);

const pluginType = computed(() =>
  deriveInstallPreviewPluginType(previewInfo.value?.install_manifest),
);
const capabilities = computed(() => previewInfo.value?.capabilities || []);
const conflicts = computed(() => previewInfo.value?.conflicts || []);
const warnings = computed(() => previewInfo.value?.warnings || []);
const deps = computed(
  () =>
    previewInfo.value?.dependencies || {
      python: [],
      plugins: [],
    },
);
const compatibilityProfile = computed(() =>
  resolvePluginCompatibilityProfile(
    previewInfo.value ?? {
      plugin_info: pluginInfo.value,
      scope: pluginScope.value,
    },
  ),
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

const canConfirmInstall = computed(() => {
  if (previewLoading.value || conflicts.value.length > 0) {
    return false;
  }
  if (installSource.value === 'marketplace') {
    return Boolean(marketplaceTarget.value && previewInfo.value?.preview_token);
  }
  return Boolean(selectedFile.value && previewInfo.value?.preview_token);
});

function getSaasCompatibilityColor(): string {
  return compatibilityProfile.value.saasCompatible ? 'success' : 'default';
}

function getSingleManagementCompatibilityColor(): string {
  return compatibilityProfile.value.singleManagementCompatible
    ? 'processing'
    : 'default';
}

function getSaasCompatibilityText(): string {
  return $t(
    compatibilityProfile.value.saasCompatible
      ? 'admin.plugin.compatibility.edition.saasCompatible'
      : 'admin.plugin.compatibility.edition.saasIncompatible',
  );
}

function getSingleManagementCompatibilityText(): string {
  return $t(
    compatibilityProfile.value.singleManagementCompatible
      ? 'admin.plugin.compatibility.edition.singleManagementCompatible'
      : 'admin.plugin.compatibility.edition.singleManagementIncompatible',
  );
}

function getTenantExposureText(): string {
  return $t(
    getPluginTenantExposureLabelKey(
      compatibilityProfile.value.tenantExposureMode,
    ),
  );
}

defineExpose({ open, openMarketplace });
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
    :mask-closable="!installing && !previewLoading"
    :closable="!installing && !previewLoading"
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
            <span class="text-xs text-muted-foreground">
              {{ $t('admin.plugin.uploadHint') }}
            </span>
          </div>
        </div>
      </Upload.Dragger>
    </div>

    <!-- ===== Step 2: Preview + Confirm ===== -->
    <div v-else-if="step === 'preview'" class="flex flex-col gap-5 py-3">
      <div
        v-if="previewLoading"
        class="flex flex-col items-center gap-4 py-16 text-center"
      >
        <IconifyIcon
          icon="lucide:loader-2"
          class="size-8 animate-spin text-primary"
        />
        <div class="space-y-1">
          <p class="text-sm font-semibold text-foreground">
            {{ $t('admin.plugin.preview.title') }}
          </p>
          <p class="text-xs text-muted-foreground">
            {{
              marketplaceTarget?.display_name ||
              marketplaceTarget?.name ||
              pluginName ||
              ''
            }}
          </p>
        </div>
      </div>

      <template v-else-if="previewInfo">
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
          <template
            v-for="item in structureSummary"
            :key="`detail-${item.type}`"
          >
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
              <IconifyIcon
                icon="lucide:key"
                class="text-geekblue-500 size-3.5"
              />
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
          <Tag :color="getSaasCompatibilityColor()" class="!m-0 !rounded-md">
            {{ getSaasCompatibilityText() }}
          </Tag>
          <Tag
            :color="getSingleManagementCompatibilityColor()"
            class="!m-0 !rounded-md"
          >
            {{ getSingleManagementCompatibilityText() }}
          </Tag>
          <Tag
            :color="
              getPluginTenantExposureColor(
                compatibilityProfile.tenantExposureMode,
              )
            "
            class="!m-0 !rounded-md"
          >
            {{ getTenantExposureText() }}
          </Tag>
          <Tag
            v-if="compatibilityProfile.tenantAssignmentRequired"
            color="orange"
            class="!m-0 !rounded-md"
          >
            {{
              $t('admin.plugin.compatibility.tenantExposure.explicitRequired')
            }}
          </Tag>
          <Tag
            v-if="deps.python && deps.python.length > 0"
            color="orange"
            class="!m-0 !rounded-md"
          >
            <IconifyIcon icon="lucide:package" class="mr-0.5 inline size-3" />
            {{ deps.python.length }}
            {{ $t('admin.plugin.preview.pythonDeps') }}
          </Tag>
          <Tag
            v-if="deps.plugins && deps.plugins.length > 0"
            color="cyan"
            class="!m-0 !rounded-md"
          >
            <IconifyIcon icon="lucide:plug" class="mr-0.5 inline size-3" />
            {{ deps.plugins.length }}
            {{ $t('admin.plugin.preview.pluginDeps') }}
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
            :disabled="!canConfirmInstall"
            class="!rounded-xl !px-6 !shadow-lg !shadow-primary/20"
            @click="handleInstall"
          >
            <IconifyIcon icon="lucide:download" class="mr-1.5 size-4" />
            {{ $t('admin.plugin.preview.confirmInstall') }}
          </Button>
        </div>
      </template>
    </div>
  </Modal>
</template>
