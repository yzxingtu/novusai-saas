<script lang="ts" setup>
/**
 * NovusDoc document editor — full-page editor using platform RichTextEditor (mode=full)
 * NovusDoc 文档编辑器 — 使用平台 RichTextEditor 的全页编辑模式
 * Auto-saves content with debounce. Provides title editing, status toggle, and export.
 * 防抖自动保存。支持标题编辑、状态切换和导出。
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue';
import type { DocDetail } from '../types';
import { getDoc, updateDoc, getExportUrl } from '../api/novusdoc';

const shared = (window as unknown as Record<string, unknown>).NovusPluginShared as {
  $t?: (k: string) => string;
  router?: { push: (to: string) => void; currentRoute?: { value?: { params?: Record<string, string> } } };
  listPageOperations?: (key: string) => readonly { name: string }[];
  registerPageContext?: (key: string, resolver: () => unknown) => () => void;
  appendPageOperations?: (key: string, ops: unknown[]) => () => void;
} | undefined;

const $t = (key: string) => {
  return shared?.$t?.(key) ?? key.split('.').pop() ?? key;
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
const mountedEditor = shallowRef<{
  getJSON(): unknown;
  getHTML(): string;
  getText(): string;
  setContent(content: unknown): void;
  focus(): void;
  destroy(): void;
} | null>(null);

const isAdmin = computed(() => location.pathname.includes('/admin/'));

async function loadDocument() {
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

  const shared = (window as unknown as Record<string, unknown>).NovusPluginShared as {
    mountRichTextEditor: (
      target: HTMLElement,
      options: Record<string, unknown>,
    ) => {
      getJSON(): unknown;
      getHTML(): string;
      getText(): string;
      setContent(content: unknown): void;
      focus(): void;
      destroy(): void;
    };
  } | undefined;

  if (!shared?.mountRichTextEditor) return;

  mountedEditor.value = shared.mountRichTextEditor(editorContainer.value, {
    content: doc.value.content,
    mode: 'full',
    ai: true,
    upload: true,
    editable: true,
    placeholder: $t('plugin.novusdoc.doc.untitled'),
    contextTitle: title.value,
    pageKey: editorPageKey.value,
    onChange: (_json: unknown, _html: string, text: string) => {
      wordCount.value = text.trim() ? text.trim().split(/\s+/).length : 0;
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
  if (!mountedEditor.value || !doc.value) return;
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
  debounceSave();
}

async function toggleStatus() {
  if (!doc.value) return;
  const newStatus = doc.value.status === 'draft' ? 'published' : 'draft';
  try {
    const res = await updateDoc(doc.value.id, { status: newStatus });
    doc.value = { ...doc.value, ...res.document };
  } catch {
    // fail silently
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

function onExport(format: 'html' | 'md') {
  if (!doc.value) return;
  window.open(getExportUrl(doc.value.id, format), '_blank');
}

watch(title, onTitleChange);

// ── Page Awareness / 页面感知 ──
const editorPageKey = computed(() => {
  const base = isAdmin.value ? 'admin.plugins.novusdoc.editor' : 'tenant.plugins.novusdoc.editor';
  return docId.value ? `${base}.${docId.value}` : base;
});

let cleanupContext: (() => void) | undefined;
let cleanupOps: (() => void) | undefined;

const documentOps = [
  {
    name: 'save_document',
    label: $t('plugin.novusdoc.doc.saving') || 'Save document',
    description: 'Save the current document immediately',
    readonly: false,
    handler: async () => {
      await saveNow();
      return { success: true, message: `Document "${title.value}" saved` };
    },
  },
  {
    name: 'toggle_status',
    label: 'Toggle publish status',
    description: 'Switch between draft and published status',
    readonly: false,
    handler: async () => {
      await toggleStatus();
      return { success: true, message: `Status changed to ${doc.value?.status}` };
    },
  },
  {
    name: 'update_title',
    label: 'Update document title',
    description: 'Change the document title',
    readonly: false,
    params: { title: { type: 'string', description: 'New document title' } },
    handler: async (params: Record<string, unknown>) => {
      title.value = String(params.title || '');
      debounceSave();
      return { success: true, message: `Title updated to "${title.value}"` };
    },
  },
  {
    name: 'export_document',
    label: $t('plugin.novusdoc.doc.exportHTML') || 'Export document',
    description: 'Export document in HTML or Markdown format',
    readonly: true,
    params: { format: { type: 'string', enum: ['html', 'md'], description: 'Export format' } },
    handler: async (params: Record<string, unknown>) => {
      const fmt = (params.format as 'html' | 'md') || 'html';
      onExport(fmt);
      return { success: true, message: `Export initiated in ${fmt} format` };
    },
  },
];

const DOCUMENT_BODY_EXCERPT_LEN = 3500;

const EDITOR_CAPABILITIES_DESC =
  'HTML rich text editor. Body excerpt in document_body_text; full HTML via get_editor_html. '
  + 'Content params MUST be HTML, NOT Markdown. '
  + 'PARTIAL EDIT: get_editor_html → replace_section(old_html="...", new_html="...") to change one section only. '
  + 'FULL REWRITE: replace_content replaces the ENTIRE document — use only when rewriting everything. '
  + 'APPEND/INSERT: append_content adds to end, insert_content at cursor. '
  + 'Document ops: save_document, toggle_status, update_title, export_document.';

function setupEditorPageAwareness() {
  cleanupContext?.();
  cleanupOps?.();

  if (shared?.registerPageContext) {
    cleanupContext = shared.registerPageContext(editorPageKey.value, () => {
      const fullText = mountedEditor.value?.getText?.() ?? '';
      const documentBodyText = fullText.slice(0, DOCUMENT_BODY_EXCERPT_LEN);
      const documentBodyLength = fullText.length;
      return {
        page_key: editorPageKey.value,
        page_title: title.value || $t('plugin.novusdoc.doc.untitled'),
        page_data: {
          entity_name: $t('plugin.novusdoc.doc.title'),
          entity_description: EDITOR_CAPABILITIES_DESC,
          document_id: docId.value,
          document_title: title.value,
          document_status: doc.value?.status,
          word_count: wordCount.value,
          is_saving: saving.value,
          has_editor: !!mountedEditor.value,
          document_body_text: documentBodyText,
          document_body_length: documentBodyLength,
        },
      };
    });
  }

  // Append document ops so we do not replace platform editor ops (get_editor_html, replace_section, etc.)
  if (shared?.appendPageOperations) {
    cleanupOps = shared.appendPageOperations(editorPageKey.value, documentOps);
  }
}

onMounted(async () => {
  await loadDocument();
  if (doc.value) {
    await nextTickMount();
    await nextTick();
    // Wait until platform useEditorPageOps has registered editor ops, then we append document ops (appendPageOperations).
    await waitForEditorPageOps();
    setupEditorPageAwareness();
  }
});

/** Brief delay so the editor container is ready before mounting RichTextEditor. */
async function nextTickMount() {
  await new Promise(r => setTimeout(r, 50));
  mountEditor();
}

const EDITOR_OPS_POLL_MS = 80;
const EDITOR_OPS_POLL_MAX = 2000;

/** Wait until platform has registered editor ops (e.g. get_editor_html) so appendPageOperations does not get overwritten. */
async function waitForEditorPageOps() {
  const list = shared?.listPageOperations;
  if (!list) return;
  const key = editorPageKey.value;
  const deadline = Date.now() + EDITOR_OPS_POLL_MAX;
  while (Date.now() < deadline) {
    const ops = list(key);
    if (ops.some((o) => o.name === 'get_editor_html')) return;
    await new Promise((r) => setTimeout(r, EDITOR_OPS_POLL_MS));
  }
  console.warn(
    '[DocumentEditor] waitForEditorPageOps timed out: platform editor ops (e.g. get_editor_html) not registered within',
    EDITOR_OPS_POLL_MAX,
    'ms. Document ops may be overwritten if platform registers later.',
  );
}

onBeforeUnmount(() => {
  cleanupContext?.();
  cleanupOps?.();
  if (saveTimer) clearTimeout(saveTimer);
  if (mountedEditor.value) {
    saveNow();
    mountedEditor.value.destroy();
  }
});

const saveStatusText = computed(() => {
  if (saving.value) return $t('plugin.novusdoc.doc.saving');
  if (saved.value) return $t('plugin.novusdoc.doc.saved');
  return '';
});
</script>

<template>
  <div class="flex flex-col h-full bg-background text-foreground">
    <!-- ── Header bar ── -->
    <header class="shrink-0 flex items-center gap-3 px-4 py-2 border-b border-border bg-card">
      <!-- Back -->
      <button
        class="w-8 h-8 flex items-center justify-center rounded hover:bg-accent text-muted-foreground"
        @click="goBack"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6" /></svg>
      </button>

      <!-- Title input -->
      <input
        v-model="title"
        class="flex-1 text-base font-medium bg-transparent border-none outline-none placeholder:text-muted-foreground"
        :placeholder="$t('plugin.novusdoc.doc.untitled')"
      />

      <!-- Word count -->
      <span class="text-xs text-muted-foreground whitespace-nowrap">
        {{ wordCount }} {{ $t('plugin.novusdoc.doc.wordCount') }}
      </span>

      <!-- Save status -->
      <span v-if="saveStatusText" class="text-xs" :class="saved ? 'text-green-600' : 'text-muted-foreground'">
        {{ saveStatusText }}
      </span>

      <!-- Status badge -->
      <button
        v-if="doc"
        class="inline-flex items-center px-2 py-1 rounded text-xs font-medium transition-colors"
        :class="doc.status === 'published' ? 'bg-green-100 text-green-700 hover:bg-green-200 dark:bg-green-900/30 dark:text-green-400' : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-400'"
        @click="toggleStatus"
      >
        {{ doc.status === 'published' ? $t('plugin.novusdoc.status.published') : $t('plugin.novusdoc.status.draft') }}
      </button>

      <!-- Export dropdown -->
      <div class="relative group">
        <button class="w-8 h-8 flex items-center justify-center rounded hover:bg-accent text-muted-foreground">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></svg>
        </button>
        <div class="absolute right-0 top-full mt-1 hidden group-hover:flex flex-col bg-popover border border-border rounded-md shadow-md py-1 min-w-[140px] z-10">
          <button class="px-3 py-1.5 text-sm text-left hover:bg-accent" @click="onExport('html')">
            {{ $t('plugin.novusdoc.doc.exportHTML') }}
          </button>
          <button class="px-3 py-1.5 text-sm text-left hover:bg-accent" @click="onExport('md')">
            {{ $t('plugin.novusdoc.doc.exportMarkdown') }}
          </button>
        </div>
      </div>
    </header>

    <!-- ── Editor area ── -->
    <div v-if="loading" class="flex-1 flex items-center justify-center text-muted-foreground">
      <svg class="animate-spin mr-2" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-6.219-8.56" /></svg>
      {{ $t('common.loading') }}
    </div>

    <div v-else-if="!doc" class="flex-1 flex items-center justify-center text-muted-foreground">
      {{ $t('common.noData') }}
    </div>

    <div v-else ref="editorContainer" class="flex-1 min-h-0 overflow-hidden" />
  </div>
</template>
