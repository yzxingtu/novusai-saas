<script lang="ts" setup>
import { ref, onMounted, onUnmounted, watch } from 'vue';
import { Button, Tooltip, Spin, message } from 'ant-design-vue';
import { IconifyIcon, $t } from '@novus/plugin-shared';
import type { JSONContent } from '@tiptap/core';
import { useRoute, useRouter } from 'vue-router';

import NovusEditor from '../components/NovusEditor.vue';
import EditorToolbar from '../components/EditorToolbar.vue';
import AIBubbleMenu from '../components/AIBubbleMenu.vue';
import AISidebar from '../components/AISidebar.vue';
import type { DocItem } from '../api/docs';
import { getDocApi, updateDocApi } from '../api/docs';
import { useDocAI } from '../composables/useDocAI';
import { useCollab } from '../composables/useCollab';

const route = useRoute();
const router = useRouter();

const loading = ref(true);
const saving = ref(false);
const doc = ref<DocItem | null>(null);
const editorRef = ref<InstanceType<typeof NovusEditor> | null>(null);
const titleInput = ref('');
const saveTimer = ref<ReturnType<typeof setTimeout> | null>(null);
const lastSavedAt = ref('');
const showAISidebar = ref(false);
const aiSidebarRef = ref<InstanceType<typeof AISidebar> | null>(null);

const docAI = useDocAI(
  () => getDocIdFromRoute() ?? 0,
  () => editorRef.value?.editor,
);

// NovusDoc Pro 协作集成
const collab = useCollab(getDocIdFromRoute() ?? 0);

function getDocIdFromRoute(): number | null {
  const raw = route.params.docId;
  const parsed = Number(raw);
  if (!Number.isInteger(parsed) || parsed <= 0) {
    return null;
  }
  return parsed;
}

async function loadDoc() {
  const docId = getDocIdFromRoute();
  if (!docId) {
    message.error($t('plugin.novusdoc.doc.invalidId'));
    router.push('/tenant/plugins/novusdoc/docs');
    return;
  }

  loading.value = true;
  try {
    const data = await getDocApi(docId) as unknown as DocItem;
    doc.value = data;
    titleInput.value = data.title || '';
    if (editorRef.value && data.content) {
      editorRef.value.setContent(data.content as JSONContent);
    }
  } catch {
    message.error($t('plugin.novusdoc.doc.loadFailed'));
    router.push('/tenant/plugins/novusdoc/docs');
  } finally {
    loading.value = false;
  }
}

async function saveDoc() {
  if (!doc.value || saving.value) return;
  saving.value = true;
  try {
    const json = editorRef.value?.getJSON();
    await updateDocApi(doc.value.id, {
      title: titleInput.value,
      content: json,
    });
    lastSavedAt.value = new Date().toLocaleTimeString();
  } catch {
    // handled by global interceptor
  } finally {
    saving.value = false;
  }
}

function scheduleAutoSave() {
  if (saveTimer.value) {
    clearTimeout(saveTimer.value);
  }
  saveTimer.value = setTimeout(() => {
    saveDoc();
  }, 3000);
}

function handleEditorUpdate(_json: JSONContent, _text: string, wordCount: number) {
  if (doc.value) {
    doc.value.word_count = wordCount;
  }
  scheduleAutoSave();
}

function handleTitleChange() {
  scheduleAutoSave();
}

function handleBack() {
  if (saveTimer.value) {
    clearTimeout(saveTimer.value);
    saveDoc();
  }
  router.push('/tenant/plugins/novusdoc/docs');
}

function handleKeyboard(e: KeyboardEvent) {
  const mod = e.ctrlKey || e.metaKey;
  if (mod && e.key === 's') {
    e.preventDefault();
    saveDoc();
  }
  if (mod && e.shiftKey && e.key === 'a') {
    e.preventDefault();
    showAISidebar.value = !showAISidebar.value;
  }
}

onMounted(async () => {
  loadDoc();
  document.addEventListener('keydown', handleKeyboard);
  // 连接协作服务（如果 Pro 已加载）
  if (collab.collabExtensions.length > 0) {
    await collab.connect();
  }
});

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeyboard);
  if (saveTimer.value) clearTimeout(saveTimer.value);
  collab.disconnect();
});

watch(() => route.params.docId, () => {
  loadDoc();
});

function handleAIAction(feature: string, extra?: Record<string, string>) {
  docAI.runAIFeature(feature as Parameters<typeof docAI.runAIFeature>[0], extra);
}

async function handleAISidebarSend(
  msg: string,
  history: Array<{ role: string; content: string }>,
) {
  const reply = await docAI.aiChat(msg, history);
  if (reply && aiSidebarRef.value) {
    aiSidebarRef.value.addAssistantMessage(reply);
  }
}
</script>

<template>
  <div class="nd-editor-page">
    <!-- Top nav bar -->
    <header class="nd-editor-header">
      <div class="flex items-center gap-2">
        <Tooltip :title="$t('plugin.novusdoc.toolbar.back')">
          <Button size="small" type="text" @click="handleBack">
            <IconifyIcon icon="lucide:arrow-left" class="size-4" />
          </Button>
        </Tooltip>

        <IconifyIcon icon="lucide:file-text" class="size-4 text-muted-foreground" />

        <input
          v-model="titleInput"
          class="nd-title-input"
          :placeholder="$t('plugin.novusdoc.doc.untitled')"
          @input="handleTitleChange"
          @keydown.enter="editorRef?.focus()"
        />
      </div>

      <div class="flex items-center gap-3">
        <span v-if="saving" class="text-xs text-muted-foreground">
          {{ $t('plugin.novusdoc.doc.saving') }}
        </span>
        <span v-else-if="lastSavedAt" class="text-xs text-muted-foreground">
          {{ $t('plugin.novusdoc.doc.saved') }} {{ lastSavedAt }}
        </span>

        <span class="text-xs text-muted-foreground">
          {{ doc?.word_count ?? 0 }} {{ $t('plugin.novusdoc.doc.chars') }}
        </span>

        <Tooltip :title="saving ? $t('plugin.novusdoc.doc.saving') : $t('plugin.novusdoc.doc.saved')">
          <Button size="small" @click="saveDoc" :loading="saving">
            <IconifyIcon icon="lucide:save" class="mr-1 size-4" />
            {{ saving ? $t('plugin.novusdoc.doc.saving') : $t('plugin.novusdoc.doc.saved') }}
          </Button>
        </Tooltip>

        <!-- 在线协作用户（Pro） -->
        <div v-if="collab.collabEnabled.value && collab.onlineUsers.value.length > 0" class="flex items-center gap-1">
          <div
            v-for="(u, idx) in collab.onlineUsers.value.slice(0, 5)"
            :key="u.userId ?? idx"
            class="nd-collab-avatar"
            :style="{ backgroundColor: u.color, marginLeft: idx > 0 ? '-4px' : '0' }"
            :title="u.username || 'Anonymous'"
          >
            {{ (u.username || '?').charAt(0).toUpperCase() }}
          </div>
          <span v-if="collab.onlineUsers.value.length > 5" class="text-xs text-muted-foreground ml-1">
            +{{ collab.onlineUsers.value.length - 5 }}
          </span>
        </div>

        <Tooltip :title="$t('plugin.novusdoc.ai.assistant')">
          <Button
            size="small"
            :type="showAISidebar ? 'primary' : 'text'"
            @click="showAISidebar = !showAISidebar"
          >
            <IconifyIcon icon="lucide:sparkles" class="size-4" />
          </Button>
        </Tooltip>
      </div>
    </header>

    <!-- Toolbar -->
    <EditorToolbar :editor="editorRef?.editor" />

    <!-- Editor content + AI panels -->
    <div class="flex flex-1 min-h-0">
      <Spin :spinning="loading" class="flex-1 overflow-y-auto">
        <div class="nd-editor-content">
          <NovusEditor
            ref="editorRef"
            :content="doc?.content as JSONContent"
            :editable="!loading"
            :extra-extensions="collab.collabExtensions"
            @update="handleEditorUpdate"
          />
        </div>

        <!-- AI BubbleMenu (floats above selected text - action buttons only) -->
        <AIBubbleMenu
          v-if="editorRef?.editor && !loading && !docAI.ghostText.value && !docAI.loading.value"
          :editor="editorRef.editor"
          :loading="false"
          ghost-text=""
          error=""
          @action="handleAIAction"
          @accept="docAI.acceptGhostText()"
          @dismiss="docAI.dismissGhostText()"
          @cancel="docAI.cancel()"
        />

        <!-- AI Result Panel (inside scroll area, sticky at bottom) -->
        <div v-if="docAI.loading.value || docAI.ghostText.value || docAI.error.value" class="nd-ai-result-panel">
          <div v-if="docAI.loading.value" class="nd-ai-result-loading">
            <span class="nd-ai-result-dots">
              <span class="nd-ai-rdot"></span>
              <span class="nd-ai-rdot"></span>
              <span class="nd-ai-rdot"></span>
            </span>
            <span class="text-xs text-muted-foreground">{{ $t('plugin.novusdoc.ai.generating') }}</span>
            <Button size="small" type="text" @click="docAI.cancel()">
              <IconifyIcon icon="lucide:x" class="size-3" />
            </Button>
          </div>
          <div v-else-if="docAI.ghostText.value" class="nd-ai-result-preview">
            <div class="nd-ai-result-text">{{ docAI.ghostText.value.slice(0, 300) }}{{ docAI.ghostText.value.length > 300 ? '...' : '' }}</div>
            <div class="nd-ai-result-actions">
              <Button size="small" type="primary" @click="docAI.acceptGhostText()">
                <IconifyIcon icon="lucide:check" class="mr-1 size-3" />
                {{ $t('plugin.novusdoc.ai.accept') }}
              </Button>
              <Button size="small" @click="docAI.dismissGhostText()">
                <IconifyIcon icon="lucide:x" class="mr-1 size-3" />
                {{ $t('plugin.novusdoc.ai.dismiss') }}
              </Button>
            </div>
          </div>
          <div v-else-if="docAI.error.value" class="nd-ai-result-error">
            <IconifyIcon icon="lucide:alert-circle" class="size-4" />
            <span class="text-xs">{{ docAI.error.value }}</span>
            <Button size="small" type="text" @click="docAI.dismissGhostText()">
              <IconifyIcon icon="lucide:x" class="size-3" />
            </Button>
          </div>
        </div>
      </Spin>

      <!-- AI Sidebar (right panel) -->
      <AISidebar
        v-if="showAISidebar"
        ref="aiSidebarRef"
        :loading="docAI.loading.value"
        :error="docAI.error.value"
        @send="handleAISidebarSend"
        @action="handleAIAction"
        @close="showAISidebar = false"
      />
    </div>
  </div>
</template>
