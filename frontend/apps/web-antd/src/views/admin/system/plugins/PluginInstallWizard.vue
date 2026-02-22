<script lang="ts" setup>
/**
 * 插件安装向导 — 两步流程：预览 → 确认安装（含模型选择）
 */
import type { PluginPreviewInfo } from '#/api/admin/plugins';
import type { AIModelInfo } from '#/api/admin/ai-models';

import { computed, ref } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  Alert,
  Button,
  message,
  Modal,
  Select,
  Tag,
  Upload,
} from 'ant-design-vue';

import { MarkdownRender } from '#/components/business/markdown-render';

import { getAIModelListApi } from '#/api/admin/ai-models';
import {
  previewPluginApi,
  type UploadConflictResponse,
  uploadPluginApi,
} from '#/api/admin/plugins';
import { $t } from '#/locales';
import { i18n } from '@vben/locales';

const emit = defineEmits<{
  installed: [];
}>();

// ========== State ==========

const visible = ref(false);
const step = ref<'upload' | 'preview'>('upload');
const installing = ref(false);
const previewLoading = ref(false);

const selectedFile = ref<File | null>(null);
const previewInfo = ref<PluginPreviewInfo | null>(null);
const models = ref<AIModelInfo[]>([]);
const selectedModelId = ref<number | undefined>(undefined);
const modelsLoaded = ref(false);
const expandedItems = ref<Set<string>>(new Set());
const showReadme = ref(false);

// ========== Computed ==========

const needsModelSelect = computed(() => {
  return previewInfo.value?.has_agent ?? false;
});

const structureTypeLabels: Record<string, string> = {
  agent: 'admin.plugin.installWizard.structureType.agent',
  skill_package: 'admin.plugin.installWizard.structureType.skillPackage',
  api_route: 'admin.plugin.installWizard.structureType.apiRoute',
  adapter: 'admin.plugin.installWizard.structureType.adapter',
  hook: 'admin.plugin.installWizard.structureType.hook',
  migration: 'admin.plugin.installWizard.structureType.migration',
  model: 'admin.plugin.installWizard.structureType.model',
  menu: 'admin.plugin.installWizard.structureType.menu',
};

// ========== Methods ==========

function open() {
  visible.value = true;
  step.value = 'upload';
  selectedFile.value = null;
  previewInfo.value = null;
  selectedModelId.value = undefined;
  modelsLoaded.value = false;
  expandedItems.value.clear();
  showReadme.value = false;
}

function toggleExpand(type: string) {
  if (expandedItems.value.has(type)) {
    expandedItems.value.delete(type);
  } else {
    expandedItems.value.add(type);
  }
}

function close() {
  visible.value = false;
}

const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50 MB

async function handleBeforeUpload(file: File) {
  if (!(file instanceof File)) return false;

  if (file.size > MAX_FILE_SIZE) {
    message.error($t('admin.plugin.messages.fileTooLarge'));
    return false;
  }

  selectedFile.value = file;
  previewLoading.value = true;

  try {
    const currentLang = (i18n.global.locale as unknown as { value: string }).value || 'zh-CN';
    const result = await previewPluginApi(file, currentLang);
    previewInfo.value = result;
    step.value = 'preview';

    if (result.has_agent && !modelsLoaded.value) {
      await loadModels();
    }
  } catch {
    selectedFile.value = null;
  } finally {
    previewLoading.value = false;
  }

  return false;
}

async function loadModels() {
  try {
    const res = await getAIModelListApi({
      'page[size]': 200,
      'filter[is_active][eq]': true,
      'filter[type][eq]': 'chat',
      sort: 'name',
    });
    models.value = res.items || [];
    modelsLoaded.value = true;
    // 自动选择第一个模型
    if (models.value.length > 0) {
      selectedModelId.value = models.value[0]!.id;
    }
  } catch {
    // handled
  }
}

async function handleInstall() {
  if (!selectedFile.value || !previewInfo.value) return;

  // 如果含智能体但未选模型，提示
  if (needsModelSelect.value && !selectedModelId.value) {
    message.warning($t('admin.plugin.installWizard.selectModelRequired'));
    return;
  }

  installing.value = true;
  try {
    const res = await uploadPluginApi(
      selectedFile.value,
      false,
      selectedModelId.value,
    );

    if ('conflict' in res && (res as UploadConflictResponse).conflict) {
      const conflictRes = res as UploadConflictResponse;
      installing.value = false;
      Modal.confirm({
        title: $t('admin.plugin.messages.uploadConflict'),
        content: $t('admin.plugin.messages.uploadConflictDesc', {
          name: conflictRes.plugin_name,
          oldVersion: conflictRes.existing_version ?? '-',
          newVersion: conflictRes.new_version,
        }),
        okText: $t('admin.plugin.messages.overwrite'),
        cancelText: $t('common.cancel'),
        onOk: async () => {
          installing.value = true;
          try {
            await uploadPluginApi(
              selectedFile.value!,
              true,
              selectedModelId.value,
            );
            message.success($t('admin.plugin.messages.installSuccess'));
            close();
            emit('installed');
          } finally {
            installing.value = false;
          }
        },
      });
      return;
    }

    const result = res as unknown as Record<string, unknown>;
    if (result.enable_warning) {
      message.warning(
        $t('admin.plugin.messages.installSuccess') +
        ' — ' +
        String(result.enable_warning),
      );
    } else {
      message.success($t('admin.plugin.messages.installSuccess'));
    }
    close();
    emit('installed');
  } catch {
    // handled by interceptor
  } finally {
    installing.value = false;
  }
}

function goBackToUpload() {
  step.value = 'upload';
  selectedFile.value = null;
  previewInfo.value = null;
  expandedItems.value.clear();
  showReadme.value = false;
}

defineExpose({ open, close });
</script>

<template>
  <Modal
    v-model:open="visible"
    :title="
      step === 'upload'
        ? $t('admin.plugin.uploadZip')
        : $t('admin.plugin.installWizard.previewTitle')
    "
    :footer="null"
    :destroy-on-close="true"
    :width="step === 'preview' ? 720 : 520"
    :mask-closable="!installing"
    :closable="!installing"
  >
    <!-- ===== Step 1: Upload ===== -->
    <div v-if="step === 'upload'" class="py-2">
      <Upload.Dragger
        accept=".zip,.nap"
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
                  ? $t('admin.plugin.installWizard.analyzing')
                  : $t('admin.plugin.uploadDragText')
              }}
            </span>
            <span class="text-xs text-muted-foreground">
              {{ $t('admin.plugin.uploadDesc') }}
            </span>
          </div>
        </div>
      </Upload.Dragger>
    </div>

    <!-- ===== Step 2: Preview + Confirm ===== -->
    <div v-else-if="step === 'preview' && previewInfo" class="flex flex-col gap-5 py-3">
      <!-- 插件基本信息 -->
      <div class="flex items-start gap-4">
        <div
          class="flex size-14 shrink-0 items-center justify-center overflow-hidden rounded-xl bg-primary/10"
        >
          <img
            v-if="previewInfo.icon_data_url"
            :src="previewInfo.icon_data_url"
            :alt="previewInfo.display_name"
            class="size-14 rounded-xl object-cover"
          />
          <IconifyIcon
            v-else
            :icon="previewInfo.icon || 'lucide:plug'"
            class="size-7 text-primary"
          />
        </div>
        <div class="min-w-0 flex-1">
          <h3 class="text-lg font-bold text-foreground">
            {{ previewInfo.display_name }}
          </h3>
          <div class="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
            <span class="font-mono">v{{ previewInfo.version }}</span>
            <template v-if="previewInfo.author">
              <span class="text-border">·</span>
              <span>{{ previewInfo.author }}</span>
            </template>
          </div>
          <p
            v-if="previewInfo.description"
            class="mt-2 text-sm leading-relaxed text-muted-foreground"
          >
            {{ previewInfo.description }}
          </p>
        </div>
      </div>

      <!-- 已安装警告 -->
      <Alert
        v-if="previewInfo.is_installed"
        type="warning"
        show-icon
        :message="
          $t('admin.plugin.installWizard.alreadyInstalled', {
            version: previewInfo.existing_version,
          })
        "
      />

      <!-- 插件结构摘要 -->
      <div class="rounded-xl border border-border/60 bg-muted/30 p-4">
        <h4 class="mb-3 text-sm font-semibold text-foreground">
          {{ $t('admin.plugin.installWizard.structureTitle') }}
        </h4>
        <!-- 标签芯片行 -->
        <div class="flex flex-wrap gap-2">
          <button
            v-for="item in previewInfo.structure_summary"
            :key="item.type"
            class="inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-all"
            :class="
              expandedItems.has(item.type)
                ? 'border-primary/40 bg-primary/10 text-primary'
                : item.details?.length
                  ? 'border-border/60 bg-background text-foreground hover:border-primary/30 hover:bg-primary/5'
                  : 'border-border/40 bg-background text-muted-foreground cursor-default'
            "
            @click="item.details?.length ? toggleExpand(item.type) : undefined"
          >
            <IconifyIcon :icon="item.icon" class="size-3.5" />
            <span>{{ $t(structureTypeLabels[item.type] || item.type) }}</span>
            <span class="rounded bg-primary/15 px-1 text-[10px] font-bold text-primary">
              {{ item.count }}
            </span>
          </button>
        </div>
        <!-- 展开的详情面板（在芯片行下方完整宽度展示） -->
        <template v-for="item in previewInfo.structure_summary" :key="`detail-${item.type}`">
          <div
            v-if="expandedItems.has(item.type) && item.details?.length"
            class="mt-3 rounded-lg border border-border/40 bg-background px-3 py-2"
          >
            <div class="mb-1.5 flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground">
              <IconifyIcon :icon="item.icon" class="size-3" />
              {{ $t(structureTypeLabels[item.type] || item.type) }}
            </div>
            <div class="flex flex-wrap gap-1.5">
              <code
                v-for="(detail, idx) in item.details"
                :key="idx"
                class="rounded-md bg-muted/60 px-2 py-0.5 text-[11px] text-foreground/80"
              >{{ detail }}</code>
            </div>
          </div>
        </template>
      </div>

      <!-- 插件文档 -->
      <div v-if="previewInfo.readme_preview" class="rounded-xl border border-border/60 bg-muted/30">
        <button
          class="flex w-full items-center gap-2 px-4 py-3 text-left transition-colors hover:bg-accent/30"
          @click="showReadme = !showReadme"
        >
          <IconifyIcon icon="lucide:book-open" class="size-4 text-primary" />
          <span class="text-sm font-semibold text-foreground">
            {{ $t('admin.plugin.installWizard.readmeTitle') }}
          </span>
          <IconifyIcon
            :icon="showReadme ? 'lucide:chevron-up' : 'lucide:chevron-down'"
            class="ml-auto size-4 text-muted-foreground"
          />
        </button>
        <div
          v-if="showReadme"
          class="max-h-[300px] overflow-y-auto border-t border-border/30 px-4 py-3"
        >
          <MarkdownRender :content="previewInfo.readme_preview" />
        </div>
      </div>

      <!-- 标签行 -->
      <div class="flex flex-wrap items-center gap-1.5">
        <Tag color="geekblue" class="!m-0 !rounded-md">
          {{ $t(`admin.plugin.type_options.${previewInfo.plugin_type}`) }}
        </Tag>
        <Tag color="purple" class="!m-0 !rounded-md">
          {{ $t(`admin.plugin.scope_options.${previewInfo.scope}`) }}
        </Tag>
        <Tag v-if="previewInfo.locale_langs.length > 0" color="cyan" class="!m-0 !rounded-md">
          <IconifyIcon icon="lucide:globe" class="mr-0.5 inline size-3" />
          {{ previewInfo.locale_langs.join(', ') }}
        </Tag>
      </div>

      <!-- 模型选择（仅当含智能体时显示） -->
      <div
        v-if="needsModelSelect"
        class="rounded-xl border border-warning/30 bg-warning/5 p-4"
      >
        <div class="mb-2 flex items-center gap-2">
          <IconifyIcon icon="lucide:bot" class="size-4 text-warning" />
          <span class="text-sm font-semibold text-foreground">
            {{ $t('admin.plugin.installWizard.modelSelectTitle') }}
          </span>
        </div>
        <p class="mb-3 text-xs text-muted-foreground">
          {{ $t('admin.plugin.installWizard.modelSelectDesc') }}
        </p>
        <Select
          v-model:value="selectedModelId"
          :placeholder="$t('admin.plugin.installWizard.modelSelectPlaceholder')"
          :loading="!modelsLoaded"
          class="w-full"
          show-search
          :filter-option="
            (input, option) =>
              String(option?.label ?? '')
                .toLowerCase()
                .includes(String(input).toLowerCase())
          "
          :options="
            models.map((m) => ({
              value: m.id,
              label: `${m.name}${m.provider_name ? ` (${m.provider_name})` : ''}`,
            }))
          "
        />
      </div>

      <!-- 操作按钮 -->
      <div class="flex items-center justify-between border-t border-border/40 pt-4">
        <Button @click="goBackToUpload">
          <IconifyIcon icon="lucide:arrow-left" class="mr-1.5 size-4" />
          {{ $t('common.back') }}
        </Button>
        <Button
          type="primary"
          :loading="installing"
          :disabled="needsModelSelect && !selectedModelId"
          @click="handleInstall"
        >
          <IconifyIcon icon="lucide:download" class="mr-1.5 size-4" />
          {{ $t('admin.plugin.installWizard.confirmInstall') }}
        </Button>
      </div>
    </div>
  </Modal>
</template>
