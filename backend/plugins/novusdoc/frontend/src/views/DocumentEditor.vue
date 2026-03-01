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
import { useProFeatures } from '../composables/useProFeatures';

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

// NovusDoc Pro 功能检测
const pro = useProFeatures();
const showVersionDrawer = ref(false);
const showCommentDrawer = ref(false);

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
    router.push(`${getRouteBase()}/docs`);
    return;
  }

  loading.value = true;
  try {
    const data = await getDocApi(docId) as unknown as DocItem;
    doc.value = data;
    titleInput.value = data.title || '';
    // In collaboration mode, editor content comes from Yjs document (via Collaboration extension).
    // Only set content from REST API when collaboration is NOT active.
    if (editorRef.value && data.content && collab.collabExtensions.length === 0) {
      editorRef.value.setContent(data.content as JSONContent);
    }
  } catch {
    message.error($t('plugin.novusdoc.doc.loadFailed'));
    router.push(`${getRouteBase()}/docs`);
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

function getRouteBase(): string {
  return route.path.startsWith('/admin') ? '/admin/plugins/novusdoc' : '/tenant/plugins/novusdoc';
}

function handleBack() {
  if (saveTimer.value) {
    clearTimeout(saveTimer.value);
    saveDoc();
  }
  router.push(`${getRouteBase()}/docs`);
}

async function handleCreateVersion() {
  const docId = getDocIdFromRoute();
  if (!docId || !doc.value) return;
  await saveDoc();
  await pro.createVersion(docId, {
    title: titleInput.value,
    content: editorRef.value?.getJSON(),
    content_text: editorRef.value?.getText(),
    word_count: doc.value.word_count ?? 0,
    version_note: 'manual',
  });
  await pro.loadVersions(docId);
  message.success($t('plugin.novusdoc.pro.createVersion'));
}

async function handleRestoreVersion(versionId: number) {
  const docId = getDocIdFromRoute();
  if (!docId) return;
  const ok = await pro.restoreVersion(docId, versionId);
  if (ok) {
    await loadDoc();
    showVersionDrawer.value = false;
    message.success($t('plugin.novusdoc.pro.restoreVersion'));
  }
}

async function handleShare() {
  const docId = getDocIdFromRoute();
  if (!docId) return;
  const token = await pro.createShare(docId);
  if (token) {
    const shareUrl = `${window.location.origin}/api/public/plugins/novusdoc-pro/api/share/${token}`;
    await navigator.clipboard.writeText(shareUrl);
    message.success($t('plugin.novusdoc.pro.shareCopied'));
  }
}

async function handleExportWord() {
  const docId = getDocIdFromRoute();
  if (!docId) return;
  await pro.exportWord(docId, titleInput.value);
}

async function handleExportPdf() {
  const docId = getDocIdFromRoute();
  if (!docId) return;
  await pro.exportPdf(docId, titleInput.value);
}

async function openVersionDrawer() {
  const docId = getDocIdFromRoute();
  if (!docId) return;
  showVersionDrawer.value = true;
  await pro.loadVersions(docId);
}

async function openCommentDrawer() {
  const docId = getDocIdFromRoute();
  if (!docId) return;
  showCommentDrawer.value = true;
  await pro.loadComments(docId);
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

        <!-- Pro 功能按钮（仅当 novusdoc-pro 已安装时显示） -->
        <template v-if="pro.proAvailable.value">
          <Tooltip :title="$t('plugin.novusdoc.pro.versionHistory')">
            <Button size="small" type="text" @click="openVersionDrawer">
              <IconifyIcon icon="lucide:history" class="size-4" />
            </Button>
          </Tooltip>

          <Tooltip :title="$t('plugin.novusdoc.pro.comments')">
            <Button size="small" type="text" @click="openCommentDrawer">
              <IconifyIcon icon="lucide:message-square" class="size-4" />
            </Button>
          </Tooltip>

          <Tooltip :title="$t('plugin.novusdoc.pro.share')">
            <Button size="small" type="text" @click="handleShare">
              <IconifyIcon icon="lucide:share-2" class="size-4" />
            </Button>
          </Tooltip>

          <Tooltip :title="$t('plugin.novusdoc.pro.exportWord')">
            <Button size="small" type="text" @click="handleExportWord">
              <IconifyIcon icon="lucide:file-text" class="size-4" />
            </Button>
          </Tooltip>

          <Tooltip :title="$t('plugin.novusdoc.pro.exportPdf')">
            <Button size="small" type="text" @click="handleExportPdf">
              <IconifyIcon icon="lucide:file-down" class="size-4" />
            </Button>
          </Tooltip>
        </template>

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
            :disable-history="collab.collabExtensions.length > 0"
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

    <!-- Pro: 版本历史抽屉 -->
    <div v-if="showVersionDrawer" class="nd-pro-drawer">
      <div class="nd-pro-drawer__header">
        <span class="font-semibold">{{ $t('plugin.novusdoc.pro.versionHistory') }}</span>
        <Button size="small" type="text" @click="showVersionDrawer = false">
          <IconifyIcon icon="lucide:x" class="size-4" />
        </Button>
      </div>
      <div class="nd-pro-drawer__actions">
        <Button size="small" @click="handleCreateVersion">
          <IconifyIcon icon="lucide:plus" class="mr-1 size-3" />
          {{ $t('plugin.novusdoc.pro.createVersion') }}
        </Button>
      </div>
      <div class="nd-pro-drawer__list">
        <Spin :spinning="pro.loading.value">
          <div
            v-for="v in pro.versions.value"
            :key="v.id"
            class="nd-pro-version-item"
          >
            <div class="flex items-center justify-between">
              <span class="text-sm font-medium">{{ v.title || $t('plugin.novusdoc.doc.untitled') }}</span>
              <Button size="small" type="link" @click="handleRestoreVersion(v.id)">
                {{ $t('plugin.novusdoc.pro.restoreVersion') }}
              </Button>
            </div>
            <div class="text-xs text-muted-foreground">
              {{ v.creator_name || '' }} · {{ v.created_at ? new Date(v.created_at).toLocaleString() : '' }}
              <span v-if="v.version_note" class="ml-1">· {{ v.version_note }}</span>
            </div>
          </div>
          <div v-if="pro.versions.value.length === 0 && !pro.loading.value" class="p-4 text-center text-sm text-muted-foreground">
            {{ $t('plugin.novusdoc.doc.empty') }}
          </div>
        </Spin>
      </div>
    </div>

    <!-- Pro: 评论抽屉 -->
    <div v-if="showCommentDrawer" class="nd-pro-drawer">
      <div class="nd-pro-drawer__header">
        <span class="font-semibold">{{ $t('plugin.novusdoc.pro.comments') }}</span>
        <Button size="small" type="text" @click="showCommentDrawer = false">
          <IconifyIcon icon="lucide:x" class="size-4" />
        </Button>
      </div>
      <div class="nd-pro-drawer__list">
        <Spin :spinning="pro.loading.value">
          <div
            v-for="c in pro.comments.value"
            :key="c.id"
            class="nd-pro-comment-item"
          >
            <div class="flex items-center justify-between">
              <span class="text-sm font-medium">{{ c.creator_name || $t('plugin.novusdoc.pro.anonymous') }}</span>
              <span class="text-xs text-muted-foreground">{{ c.created_at ? new Date(c.created_at).toLocaleString() : '' }}</span>
            </div>
            <div v-if="c.quoted_text" class="mt-1 rounded border-l-2 border-warning/50 bg-warning/5 px-2 py-1 text-xs text-muted-foreground">
              {{ c.quoted_text }}
            </div>
            <div class="mt-1 text-sm">{{ c.content }}</div>
            <div v-if="c.is_resolved" class="mt-1 text-xs text-success">
              ✓ {{ $t('plugin.novusdoc.pro.resolved') }}
            </div>
          </div>
          <div v-if="pro.comments.value.length === 0 && !pro.loading.value" class="p-4 text-center text-sm text-muted-foreground">
            {{ $t('plugin.novusdoc.doc.empty') }}
          </div>
        </Spin>
      </div>
    </div>
  </div>
</template>
