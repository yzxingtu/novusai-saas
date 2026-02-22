<script setup lang="ts">
/**
 * 富文本编辑器 - 编辑器页面
 *
 * 全屏编辑器布局，加载文档数据并初始化 RichEditor 组件。
 * 初始化流程：
 * 1. 加载插件配置 → 获取 AI/协作开关
 * 2. 如果 AI 开启 → resolve 智能体绑定
 * 3. 加载文档数据
 * 4. 根据配置条件渲染编辑器功能
 */
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { Alert, Button, Spin, message } from 'ant-design-vue';

import { $t } from '#/locales';
import { useRichEditorApi } from '#/views/tenant/plugins/rich-editor/composables/use-rich-editor-api';

import RichEditor from './components/RichEditor.vue';
import { useEditorConfig } from './composables/use-editor-config';
import { useEditorAIResolve } from './composables/use-editor-ai-resolve';

const route = useRoute();
const router = useRouter();
const {
  getDocument,
  createDocument,
  autoSave,
} = useRichEditorApi();

// ==================== 插件配置（T10） ====================

const {
  config: pluginConfig,
  aiEnabled,
  collaborationEnabled,
  init: initConfig,
} = useEditorConfig();

// ==================== AI Resolve（T13） ====================

const {
  aiReadyState,
  resolvedAgentName,
  resolve: resolveAI,
} = useEditorAIResolve();

/** AI 最终可用状态：config 开启 + resolve 成功 */
const isAIReady = computed(() => aiReadyState.value === 'ready');

// ==================== 文档状态 ====================

const loading = ref(true);
const saving = ref(false);
const lastSaved = ref<string | null>(null);
const documentId = ref<number | null>(null);
const documentData = ref<Record<string, unknown>>({});
const documentVersion = ref(1);
const content = ref('');
const title = ref('');

// 自动保存定时器
let autoSaveTimer: ReturnType<typeof setTimeout> | null = null;

/** 自动保存间隔（从插件配置获取，默认 30s） */
const autoSaveInterval = computed(() =>
  (pluginConfig.value.auto_save_interval || 30) * 1000,
);

const isNew = computed(() => route.params.id === 'new');

// ==================== 初始化 ====================

async function initialize() {
  loading.value = true;
  try {
    // 1. 加载插件配置
    await initConfig();

    // 2. 如果 AI 开启 → resolve 智能体
    if (aiEnabled.value) {
      await resolveAI(true);
    }

    // 3. 加载文档
    await loadDocument();
  } finally {
    loading.value = false;
  }
}

async function loadDocument() {
  if (isNew.value) {
    return;
  }

  const id = Number(route.params.id);
  if (Number.isNaN(id)) {
    router.replace('/tenant/plugins/rich-editor');
    return;
  }

  try {
    const res = await getDocument(id);
    documentId.value = res.id;
    documentData.value = res;
    documentVersion.value = res.version || 1;
    content.value = res.content_html || '';
    title.value = res.title || '';
  } catch {
    message.error($t('tenant.richEditor.error.loadFailed'));
    router.replace('/tenant/plugins/rich-editor');
  }
}

// ==================== 保存 ====================

async function handleSave() {
  if (saving.value) return;
  saving.value = true;

  try {
    if (isNew.value && !documentId.value) {
      const res = await createDocument({
        title: title.value || $t('tenant.richEditor.untitled'),
        content_html: content.value,
        status: 'draft',
      });
      documentId.value = res.id;
      documentVersion.value = res.version || 1;
      router.replace(`/tenant/plugins/rich-editor/editor/${res.id}`);
      message.success($t('tenant.richEditor.message.created'));
    } else if (documentId.value) {
      const wordCount = (content.value || '')
        .replace(/<[^>]*>/g, '')
        .trim()
        .split(/\s+/)
        .filter(Boolean).length;
      const charCount = (content.value || '').replace(/<[^>]*>/g, '').length;

      const res = await autoSave(documentId.value, {
        content_html: content.value,
        word_count: wordCount,
        character_count: charCount,
        version: documentVersion.value,
      });
      documentVersion.value = res.version;
    }
    lastSaved.value = new Date().toLocaleTimeString();
  } catch {
    message.error($t('tenant.richEditor.error.saveFailed'));
  } finally {
    saving.value = false;
  }
}

function handleTitleChange(e: Event) {
  title.value = (e.target as HTMLInputElement).value;
  scheduleAutoSave();
}

function handleContentUpdate(html: string) {
  content.value = html;
  scheduleAutoSave();
}

function scheduleAutoSave() {
  if (autoSaveTimer) clearTimeout(autoSaveTimer);
  autoSaveTimer = setTimeout(() => {
    handleSave();
  }, autoSaveInterval.value);
}

// ==================== AI 操作 ====================

function handleAiAction(_action: string) {
  // AI action 由 useEditorAI composable 在组件内部处理
  // 后续可扩展：打开 AI 面板等
}

function goBack() {
  router.push('/tenant/plugins/rich-editor');
}

onMounted(() => {
  initialize();
});

onUnmounted(() => {
  if (autoSaveTimer) clearTimeout(autoSaveTimer);
});
</script>

<template>
  <div class="rich-editor-page flex h-screen flex-col">
    <!-- 顶部栏 -->
    <div
      class="bg-card/80 border-border sticky top-0 z-10 flex items-center justify-between border-b px-4 py-2 backdrop-blur"
    >
      <div class="flex items-center gap-3">
        <Button type="text" size="small" @click="goBack">
          <span class="icon-[lucide--arrow-left] h-4 w-4" />
        </Button>
        <input
          :value="title"
          :placeholder="$t('tenant.richEditor.titlePlaceholder')"
          class="text-foreground bg-transparent text-lg font-medium outline-none"
          style="min-width: 200px"
          @input="handleTitleChange"
        />
      </div>

      <div class="flex items-center gap-3">
        <!-- 保存状态 -->
        <span v-if="saving" class="text-muted-foreground flex items-center gap-1 text-xs">
          <span class="icon-[lucide--loader-2] h-3 w-3 animate-spin" />
          {{ $t('tenant.richEditor.saving') }}
        </span>
        <span v-else-if="lastSaved" class="text-muted-foreground flex items-center gap-1 text-xs">
          <span class="icon-[lucide--check] h-3 w-3" />
          {{ $t('tenant.richEditor.saved') }} {{ lastSaved }}
        </span>

        <!-- AI 状态指示 -->
        <span
          v-if="aiEnabled && aiReadyState === 'ready'"
          class="flex items-center gap-1 text-xs text-primary"
          :title="resolvedAgentName || ''"
        >
          <span class="icon-[lucide--sparkles] h-3 w-3" />
          AI
        </span>

        <Button type="primary" size="small" :loading="saving" @click="handleSave">
          <template #icon>
            <span class="icon-[lucide--save] mr-1" />
          </template>
          {{ $t('tenant.richEditor.save') }}
        </Button>
      </div>
    </div>

    <!-- AI 未配置提示（ai_enabled=true 但 resolve 失败） -->
    <Alert
      v-if="aiEnabled && aiReadyState === 'not_configured'"
      type="info"
      show-icon
      closable
      class="mx-4 mt-2"
      :message="$t('tenant.richEditor.ai.notConfigured')"
    />

    <!-- 编辑器主体 -->
    <div class="flex-1 overflow-auto">
      <Spin :spinning="loading" class="h-full">
        <div class="mx-auto max-w-[800px] px-8 py-8">
          <RichEditor
            v-if="!loading"
            :content="content"
            :readonly="false"
            :placeholder="$t('tenant.richEditor.editorPlaceholder')"
            :document-title="title"
            :document-id="documentId ?? undefined"
            :enable-collaboration="collaborationEnabled"
            :enable-ai="isAIReady"
            @update:content="handleContentUpdate"
            @ai-action="handleAiAction"
          />
        </div>
      </Spin>
    </div>
  </div>
</template>

<style scoped>
.rich-editor-page {
  background: var(--background);
}
</style>
