<script lang="ts" setup>
/**
 * NovusDoc document editor — full-page editor using platform RichTextEditor (mode=full).
 * NovusDoc 文档编辑器 — 使用平台 RichTextEditor 的全页编辑模式。
 *
 * Auto-saves content with debounce. The editor-domain AI writing interaction is
 * owned by the platform RichTextEditor via the explicit aiWriting mount option;
 * this plugin page only passes document/editor metadata and never uses page
 * perception, page operation, or DOM-scanning AI runtime payloads.
 */
import type {
  DocDetail,
  MountedRichTextEditor,
  NovusPluginSharedAPI,
} from '../types';

import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue';

import { exportDocumentAsBlob, getDoc, updateDoc } from '../api/novusdoc';
import {
  getNovusdocPermissionCodes,
  hasNovusdocAccess,
  resolveRouteAccessCodes,
} from '../permissions';

const AI_WRITING_FEATURE_CODE = 'system.ai_writing' as const;

const shared = (window as unknown as { NovusPluginShared?: NovusPluginSharedAPI })
  .NovusPluginShared;

const $t = (key: string, params?: Record<string, unknown>) => {
  const raw = shared?.$t?.(key, params) ?? key.split('.').pop() ?? key;
  if (params && typeof raw === 'string') {
    return Object.entries(params).reduce(
      (s, [k, v]) => s.replace(new RegExp(`\\{${k}\\}`, 'g'), String(v ?? '')),
      raw,
    );
  }
  return raw;
};

const props = defineProps<{ id: string | number }>();
const docId = computed(() => Number(props.id));

const doc = ref<DocDetail | null>(null);
const loading = ref(true);
const saving = ref(false);
const saved = ref(false);
const title = ref('');
const wordCount = ref(0);

const editorContainer = ref<HTMLElement | null>(null);
const exportMenuOpen = ref(false);
const exportMenuRef = ref<HTMLElement | null>(null);
const mountedEditor = shallowRef<MountedRichTextEditor | null>(null);

const isAdmin = computed(() => location.pathname.includes('/admin/'));
const apiPrefix = computed(() => (isAdmin.value ? '/admin' : '/tenant'));
const permissionScope = computed(() => (isAdmin.value ? 'admin' : 'tenant'));
const permissionCodes = computed(() =>
  getNovusdocPermissionCodes(permissionScope.value),
);
const routeAccessCodes = computed(() =>
  resolveRouteAccessCodes(
    shared?.router?.currentRoute?.value?.meta,
    [permissionCodes.value.view],
  ),
);
const canView = computed(() => hasNovusdocAccess(routeAccessCodes.value));
const canUpdate = computed(
  () => canView.value && hasNovusdocAccess(permissionCodes.value.update),
);
const canExport = computed(
  () => canView.value && hasNovusdocAccess(permissionCodes.value.export),
);

function updateWordCountFromText(text: string) {
  wordCount.value = text.trim() ? text.trim().split(/\s+/).length : 0;
}

async function loadDocument() {
  if (!canView.value) {
    doc.value = null;
    loading.value = false;
    return;
  }
  loading.value = true;
  try {
    const res = await getDoc(docId.value);
    doc.value = res.document;
    title.value = res.document.title;
    wordCount.value = res.document.word_count;
  } catch {
    doc.value = null;
  } finally {
    loading.value = false;
  }
}

function mountEditor() {
  if (!editorContainer.value || !doc.value) return;
  if (!shared?.mountRichTextEditor) return;

  mountedEditor.value = shared.mountRichTextEditor(editorContainer.value, {
    content: doc.value.content,
    mode: 'full',
    upload: true,
    editable: canUpdate.value,
    placeholder: $t('plugin.novusdoc.doc.untitled'),
    aiWriting: {
      enabled: canUpdate.value,
      apiPrefix: apiPrefix.value,
      documentTitle: title.value,
      featureCode: AI_WRITING_FEATURE_CODE,
      i18nPrefix: 'plugin.novusdoc.ai',
      configurePath: isAdmin.value ? '/admin/ai/agent-assignments' : undefined,
      canConfigure: isAdmin.value,
    },
    onChange: (_json: unknown, _html: string, text: string) => {
      updateWordCountFromText(text);
      debounceSave();
    },
  });
}

let saveTimer: ReturnType<typeof setTimeout> | null = null;
const AUTO_SAVE_MS = 3000;

function debounceSave() {
  if (saveTimer) clearTimeout(saveTimer);
  saved.value = false;
  saveTimer = setTimeout(() => {
    saveNow();
  }, AUTO_SAVE_MS);
}

async function saveNow() {
  if (!canUpdate.value || !mountedEditor.value || !doc.value) return;
  saving.value = true;
  try {
    const json = mountedEditor.value.getJSON();
    const html = mountedEditor.value.getHTML();
    const text = mountedEditor.value.getText();
    await updateDoc(doc.value.id, {
      title: title.value,
      content: json,
      content_html: html,
      content_text: text,
      word_count: wordCount.value,
    });
    saved.value = true;
  } catch {
    saved.value = false;
  } finally {
    saving.value = false;
  }
}

function onTitleChange() {
  if (!canUpdate.value) return;
  debounceSave();
}

async function toggleStatus() {
  if (!canUpdate.value || !doc.value) return;
  const newStatus = doc.value.status === 'draft' ? 'published' : 'draft';
  try {
    const res = await updateDoc(doc.value.id, { status: newStatus });
    doc.value = { ...doc.value, ...res.document };
  } catch {
    // 错误由 requestClient 统一提示 / requestClient owns the error UX.
  }
}

function goBack() {
  const base = isAdmin.value ? '/admin/plugins/novusdoc' : '/tenant/plugins/novusdoc';
  if (shared?.router) {
    shared.router.push(base);
  } else {
    window.location.href = base;
  }
}

async function onExport(format: 'html' | 'md' | 'pdf') {
  if (!canExport.value || !doc.value) return;
  exportMenuOpen.value = false;
  const downloadBlob = shared?.downloadBlob;
  if (!downloadBlob) {
    return;
  }
  try {
    const blob = await exportDocumentAsBlob(doc.value.id, format);
    const ext = format === 'md' ? 'md' : format;
    const safeTitle = (doc.value.title || 'document').replace(/[/\\:*?"<>|]/g, '_');
    downloadBlob(blob, { filename: `${safeTitle}.${ext}` });
  } catch {
    // 错误由 requestClient 统一提示 / requestClient owns the error UX.
  }
}

watch(title, onTitleChange);

function handleExportMenuClickOutside(e: MouseEvent) {
  const container = (e.target as Element)?.closest?.('[data-export-dropdown]');
  if (!container) {
    exportMenuOpen.value = false;
  }
}
watch(exportMenuOpen, (open) => {
  if (open) {
    nextTick(() => setTimeout(() => document.addEventListener('click', handleExportMenuClickOutside), 0));
  } else {
    document.removeEventListener('click', handleExportMenuClickOutside);
  }
});

onMounted(async () => {
  if (!canView.value) {
    loading.value = false;
    return;
  }
  await loadDocument();
  if (doc.value) {
    await nextTickMount();
  }
});

/** Brief delay so the editor container is ready before mounting RichTextEditor. */
async function nextTickMount() {
  await new Promise((resolve) => setTimeout(resolve, 50));
  mountEditor();
}

onBeforeUnmount(() => {
  document.removeEventListener('click', handleExportMenuClickOutside);
  if (saveTimer) clearTimeout(saveTimer);
  if (mountedEditor.value) {
    saveNow();
    mountedEditor.value.destroy();
  }
});

const saveStatusText = computed(() => {
  if (!canUpdate.value) return '';
  if (saving.value) return $t('plugin.novusdoc.doc.saving');
  if (saved.value) return $t('plugin.novusdoc.doc.saved');
  return '';
});
</script>

<template>
  <div class="flex h-full flex-col bg-background text-foreground">
    <div
      v-if="!canView"
      data-testid="novusdoc-no-permission"
      class="flex flex-1 items-center justify-center text-muted-foreground"
    >
      {{ $t('common.noPermissions') }}
    </div>
    <template v-else>
      <!-- ── Header bar ── -->
      <header class="flex shrink-0 items-center gap-3 border-b border-border bg-card px-4 py-2">
        <!-- Back -->
        <button
          type="button"
          class="flex h-8 w-8 items-center justify-center rounded text-muted-foreground hover:bg-accent"
          :aria-label="$t('common.back')"
          @click="goBack"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6" /></svg>
        </button>

        <!-- Title input -->
        <input
          v-model="title"
          data-testid="novusdoc-editor-title"
          class="flex-1 border-none bg-transparent text-base font-medium outline-none placeholder:text-muted-foreground"
          :placeholder="$t('plugin.novusdoc.doc.untitled')"
          :readonly="!canUpdate"
        />

        <!-- Word count -->
        <span class="whitespace-nowrap text-xs text-muted-foreground">
          {{ wordCount }} {{ $t('plugin.novusdoc.doc.wordCount') }}
        </span>

        <!-- Save status -->
        <span v-if="saveStatusText" class="text-xs" :class="saved ? 'text-green-600' : 'text-muted-foreground'">
          {{ saveStatusText }}
        </span>

        <!-- Status badge -->
        <button
          v-if="doc && canUpdate"
          type="button"
          data-testid="novusdoc-toggle-status"
          class="inline-flex items-center rounded px-2 py-1 text-xs font-medium transition-colors"
          :class="doc.status === 'published' ? 'bg-green-100 text-green-700 hover:bg-green-200 dark:bg-green-900/30 dark:text-green-400' : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-400'"
          @click="toggleStatus"
        >
          {{ doc.status === 'published' ? $t('plugin.novusdoc.status.published') : $t('plugin.novusdoc.status.draft') }}
        </button>

        <!-- Export dropdown (click to open, fix hover gap causing "cannot select") -->
        <div
          v-if="canExport"
          class="relative"
          data-export-dropdown
        >
          <button
            type="button"
            data-testid="novusdoc-export-menu"
            class="flex h-8 w-8 items-center justify-center rounded text-muted-foreground hover:bg-accent"
            :aria-label="$t('plugin.novusdoc.doc.export')"
            @click.stop="exportMenuOpen = !exportMenuOpen"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></svg>
          </button>
          <div
            v-show="exportMenuOpen"
            ref="exportMenuRef"
            class="absolute right-0 top-full z-20 mt-1 flex min-w-[140px] flex-col rounded-md border border-border bg-popover py-1 shadow-md"
          >
            <button type="button" class="w-full px-3 py-1.5 text-left text-sm hover:bg-accent" @click="onExport('html')">
              {{ $t('plugin.novusdoc.doc.exportHTML') }}
            </button>
            <button type="button" class="w-full px-3 py-1.5 text-left text-sm hover:bg-accent" @click="onExport('md')">
              {{ $t('plugin.novusdoc.doc.exportMarkdown') }}
            </button>
            <button type="button" class="w-full px-3 py-1.5 text-left text-sm hover:bg-accent" @click="onExport('pdf')">
              {{ $t('plugin.novusdoc.doc.exportPDF') }}
            </button>
          </div>
        </div>
      </header>

      <!-- ── Editor area ── -->
      <div v-if="loading" class="flex flex-1 items-center justify-center text-muted-foreground">
        <svg class="mr-2 animate-spin" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-6.219-8.56" /></svg>
        {{ $t('common.loading') }}
      </div>

      <div v-else-if="!doc" class="flex flex-1 items-center justify-center text-muted-foreground">
        {{ $t('common.noData') }}
      </div>

      <div
        v-else
        ref="editorContainer"
        data-testid="novusdoc-editor-container"
        class="min-h-0 flex-1 overflow-hidden"
      />
    </template>
  </div>
</template>
