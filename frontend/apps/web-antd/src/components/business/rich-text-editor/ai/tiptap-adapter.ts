import type { Editor, Extensions, JSONContent } from '@tiptap/core';

import type {
  EditorAIAdapter,
  EditorAIApplyResult,
  EditorAIDraftContent,
  EditorAIDraftVariant,
  EditorAIOperation,
  EditorAIPreviewResult,
  EditorAISelectionRange,
} from './editor-ai-adapter';

import type { RichTextAITask } from '#/types/ai-chat';

import { $t } from '@vben/locales';

import { generateHTML, generateJSON, generateText } from '@tiptap/core';
import DOMPurify from 'dompurify';
import MarkdownIt from 'markdown-it';

import { resolveEditorAIFeatureLabelKey } from './editor-ai-adapter';
import { normalizeRuntimePageKey } from './page-key';

interface RequestDraftResult {
  content: string;
  conversationId: null | number;
}

type PreparedPreview = Partial<EditorAIPreviewResult> &
  Pick<EditorAIPreviewResult, 'draft' | 'mode' | 'selection' | 'target'>;

interface TiptapEditorAIAdapterOptions {
  contextTitle?: string;
  editor: Editor;
  editorInstanceId: string;
  getRevision: () => number;
  pageKey: string;
}

const markdown = new MarkdownIt({
  breaks: true,
  html: false,
  linkify: true,
  typographer: false,
});

const FEATURE_INSTRUCTIONS: Record<string, string> = {
  continue:
    'Continue the selected passage naturally. Return only the continuation without commentary.',
  expand:
    'Expand the selected passage with useful detail while preserving tone and intent. Return only the rewritten content.',
  optimize:
    'Improve clarity, structure, and wording while preserving meaning. Return only the optimized content.',
  proofread:
    'Correct grammar, spelling, punctuation, and awkward phrasing while preserving meaning. Return only the corrected content.',
  rewrite:
    'Rewrite the selected passage with fresh wording while preserving meaning. Return only the rewritten content.',
  summarize:
    'Summarize the selected passage concisely. Return only the summary.',
  translate:
    'Translate the selected passage. If the source text is primarily Chinese, translate to English. Otherwise translate to Simplified Chinese. Return only the translated content.',
};

const FEATURE_TARGETS: Record<
  string,
  'insert_after_selection' | 'replace_selection'
> = {
  continue: 'insert_after_selection',
  expand: 'replace_selection',
  optimize: 'replace_selection',
  proofread: 'replace_selection',
  rewrite: 'replace_selection',
  summarize: 'replace_selection',
  translate: 'replace_selection',
};

function resolveApiPrefix(): '/admin' | '/tenant' {
  return window.location.pathname.startsWith('/admin') ? '/admin' : '/tenant';
}

function stripCodeFence(raw: string): string {
  const trimmed = raw.trim();
  if (!trimmed.startsWith('```')) {
    return trimmed;
  }

  const lines = trimmed.split('\n');
  const lastLine = lines.at(-1)?.trim();
  if (lines.length < 2 || lastLine !== '```') {
    return trimmed;
  }

  return lines.slice(1, -1).join('\n').trim();
}

function escapeHtml(raw: string): string {
  return raw
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function renderPlainTextHtml(raw: string): string {
  const paragraphs = raw
    .split(/\n{2,}/)
    .map((part) => part.trim())
    .filter(Boolean);

  if (paragraphs.length === 0) {
    return '<p></p>';
  }

  return paragraphs
    .map((part) => `<p>${escapeHtml(part).replaceAll('\n', '<br />')}</p>`)
    .join('');
}

function sanitizeHtml(html: string): string {
  return DOMPurify.sanitize(html, {
    ALLOWED_ATTR: ['class', 'colspan', 'href', 'rel', 'rowspan', 'target'],
  });
}

function normalizeDraftRaw(raw: string): string {
  return stripCodeFence(raw).trim();
}

function parseSseDataLines(
  chunk: string,
  buffer: { value: string },
  onData: (data: string) => void,
) {
  buffer.value += chunk;
  const lines = buffer.value.split('\n');
  buffer.value = lines.pop() ?? '';

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed.startsWith('data: ')) {
      continue;
    }
    onData(trimmed.slice(6));
  }
}

function buildSelectionSnapshot(
  editor: Editor,
  revision: number,
): EditorAISelectionRange | null {
  const { from, to } = editor.state.selection;
  if (from >= to) {
    return null;
  }

  const docSize = editor.state.doc.content.size;
  const safeFrom = Math.max(0, Math.min(from, docSize));
  const safeTo = Math.max(safeFrom, Math.min(to, docSize));
  const selectedText = editor.state.doc.textBetween(safeFrom, safeTo, '\n');

  if (!selectedText.trim()) {
    return null;
  }

  const beforeFrom = Math.max(0, safeFrom - 2000);
  const afterTo = Math.min(docSize, safeTo + 500);

  return {
    afterTextExcerpt: editor.state.doc.textBetween(safeTo, afterTo, '\n'),
    beforeTextExcerpt: editor.state.doc.textBetween(beforeFrom, safeFrom, '\n'),
    editorRevision: revision,
    from: safeFrom,
    selectedContent: editor.state.doc
      .cut(safeFrom, safeTo)
      .toJSON() as JSONContent,
    selectedText,
    to: safeTo,
  };
}

function buildTaskMessage(
  feature: string,
  selection: EditorAISelectionRange,
  contextTitle?: string,
): string {
  const actionTitle = $t(resolveEditorAIFeatureLabelKey(feature));
  const instruction =
    FEATURE_INSTRUCTIONS[feature] ??
    'Rewrite the selected content. Return only the updated content without commentary.';

  return [
    `Rich text task: ${actionTitle}`,
    contextTitle ? `Document title: ${contextTitle}` : '',
    `Instruction: ${instruction}`,
    'Selected text:',
    selection.selectedText,
    selection.beforeTextExcerpt
      ? ['Context before selection:', selection.beforeTextExcerpt].join('\n')
      : '',
    selection.afterTextExcerpt
      ? ['Context after selection:', selection.afterTextExcerpt].join('\n')
      : '',
    'Output rules:',
    '- Return only the rewritten content.',
    '- Do not add explanations, bullet labels, or markdown fences.',
    '- Preserve formatting intent when the content naturally contains lists or headings.',
  ]
    .filter(Boolean)
    .join('\n\n');
}

function toRichTextTask(
  input: {
    agentId: number;
    content: string;
    conversationId: null | number;
    feature: string;
    selection: EditorAISelectionRange;
  },
  options: TiptapEditorAIAdapterOptions,
): RichTextAITask {
  const now = Date.now();

  return {
    agentId: input.agentId,
    availableModes: ['plain', 'formatted'],
    contextTitle: options.contextTitle,
    conversationId: input.conversationId,
    createdAt: now,
    draft: {
      markdown: input.content,
      plainText: input.content,
    },
    editorInstanceId: options.editorInstanceId,
    feature: input.feature,
    message: input.content,
    pageKey: options.pageKey,
    preferredApplyMode: 'formatted',
    selectionLabel: input.selection.selectedText.slice(0, 120),
    selectionSnapshot: {
      afterTextExcerpt: input.selection.afterTextExcerpt,
      beforeTextExcerpt: input.selection.beforeTextExcerpt,
      editorInstanceId: options.editorInstanceId,
      editorRevision: input.selection.editorRevision,
      from: input.selection.from,
      pageKey: options.pageKey,
      selectedText: input.selection.selectedText,
      to: input.selection.to,
    },
    state: 'ready',
    taskId: `editor-ai-preview-${now}`,
    title: $t(resolveEditorAIFeatureLabelKey(input.feature)),
    updatedAt: now,
  };
}

function createDraftVariant(
  raw: string,
  extensions: Extensions,
  mode: 'formatted' | 'plain',
): EditorAIDraftVariant {
  const htmlSource =
    mode === 'formatted'
      ? sanitizeHtml(markdown.render(raw))
      : sanitizeHtml(renderPlainTextHtml(raw));
  const json = generateJSON(htmlSource, extensions);
  const html = sanitizeHtml(generateHTML(json, extensions));
  const text = generateText(json, extensions).trim();

  return {
    html,
    json,
    text,
  };
}

function extractInsertableContent(
  json: JSONContent,
): JSONContent | JSONContent[] {
  if (json.type === 'doc' && Array.isArray(json.content)) {
    return json.content;
  }
  return json;
}

export class TiptapEditorAIAdapter implements EditorAIAdapter {
  private readonly contextTitle?: string;

  private lastAppliedRevision: null | number = null;

  private lastPreview: EditorAIPreviewResult | null = null;

  private readonly normalizedPageKey: string;

  constructor(private readonly options: TiptapEditorAIAdapterOptions) {
    this.contextTitle = options.contextTitle;
    this.normalizedPageKey = normalizeRuntimePageKey(options.pageKey);
  }

  async applyOperation(
    operation: EditorAIOperation,
  ): Promise<EditorAIApplyResult> {
    const editor = this.options.editor;
    if (!editor?.isEditable) {
      return {
        applied: false,
        reason: 'editor_unavailable',
      };
    }

    let preview: null | PreparedPreview = null;

    if (operation.draft && operation.selection) {
      preview = {
        draft: operation.draft,
        mode: operation.mode ?? 'formatted',
        selection: operation.selection,
        target:
          operation.target ??
          FEATURE_TARGETS[operation.feature] ??
          'replace_selection',
      };
    } else if (
      this.lastPreview &&
      this.lastPreview.feature === operation.feature &&
      this.lastPreview.selection.editorRevision ===
        (operation.selection?.editorRevision ??
          this.lastPreview.selection.editorRevision)
    ) {
      preview = this.lastPreview;
    }

    if (!preview) {
      return {
        applied: false,
        reason: 'missing_preview',
      };
    }

    const currentRevision = this.options.getRevision();
    if (
      preview.target !== 'append_to_end' &&
      currentRevision !== preview.selection.editorRevision
    ) {
      return {
        applied: false,
        reason: 'selection_changed',
      };
    }

    const variant =
      preview.draft[operation.mode ?? preview.mode ?? 'formatted'];
    const insertableContent = extractInsertableContent(variant.json);
    const chain = editor.chain().focus();

    switch (preview.target) {
      case 'append_to_end': {
        const endPosition = editor.state.doc.content.size;
        chain.insertContentAt(endPosition, insertableContent);
        break;
      }
      case 'insert_after_selection': {
        chain.insertContentAt(preview.selection.to, insertableContent);
        break;
      }
      case 'replace_selection': {
        chain.insertContentAt(
          { from: preview.selection.from, to: preview.selection.to },
          insertableContent,
        );
        break;
      }
    }

    const applied = chain.run();
    if (!applied) {
      return {
        applied: false,
        reason: 'editor_unavailable',
      };
    }

    this.lastAppliedRevision = this.options.getRevision();
    return { applied: true };
  }

  canUndoLastOperation(): boolean {
    return (
      this.lastAppliedRevision !== null &&
      this.lastAppliedRevision === this.options.getRevision()
    );
  }

  getDocumentModel(): JSONContent | null {
    return this.options.editor.getJSON();
  }

  getSelection(): EditorAISelectionRange | null {
    return buildSelectionSnapshot(
      this.options.editor,
      this.options.getRevision(),
    );
  }

  async previewOperation(
    operation: EditorAIOperation,
  ): Promise<EditorAIPreviewResult> {
    const selection = operation.selection ?? this.getSelection();
    if (!selection) {
      throw new Error('empty_selection');
    }

    const [{ resolveAgentAssignmentApi }, { useAIPanelStore }] =
      await Promise.all([
        import('#/api/shared/agent-assignments'),
        import('#/store/shared/ai-panel'),
      ]);
    const prefix = resolveApiPrefix();
    const assignment = await resolveAgentAssignmentApi(
      prefix,
      'system.ai_writing',
    );
    if (!assignment.agent_id || !assignment.is_active) {
      throw new Error('agent_unavailable');
    }

    const aiPanelStore = useAIPanelStore();
    const binding = aiPanelStore.getRichTextConversationBinding(
      this.normalizedPageKey,
      this.options.editorInstanceId,
      assignment.agent_id,
    );

    const result = await this.requestDraft({
      agentId: assignment.agent_id,
      conversationId:
        operation.conversationId ?? binding?.conversationId ?? null,
      message: buildTaskMessage(
        operation.feature,
        selection,
        operation.contextTitle ?? this.contextTitle,
      ),
      prefix,
    });
    const normalizedRaw = normalizeDraftRaw(result.content);

    if (!normalizedRaw) {
      throw new Error('empty_response');
    }

    const extensions = this.options.editor.extensionManager.extensions;
    const draft: EditorAIDraftContent = {
      formatted: createDraftVariant(normalizedRaw, extensions, 'formatted'),
      plain: createDraftVariant(normalizedRaw, extensions, 'plain'),
      raw: normalizedRaw,
    };

    const preview: EditorAIPreviewResult = {
      agentId: assignment.agent_id,
      contextTitle: operation.contextTitle ?? this.contextTitle,
      conversationId: result.conversationId,
      draft,
      feature: operation.feature,
      mode: operation.mode ?? 'formatted',
      selection,
      target:
        operation.target ??
        FEATURE_TARGETS[operation.feature] ??
        'replace_selection',
    };

    if (
      typeof result.conversationId === 'number' &&
      Number.isFinite(result.conversationId)
    ) {
      aiPanelStore.bindRichTextConversation({
        agentId: assignment.agent_id,
        conversationId: result.conversationId,
        editorInstanceId: this.options.editorInstanceId,
        pageKey: this.normalizedPageKey,
        task: toRichTextTask(
          {
            agentId: assignment.agent_id,
            content: normalizedRaw,
            conversationId: result.conversationId,
            feature: operation.feature,
            selection,
          },
          {
            ...this.options,
            contextTitle: operation.contextTitle ?? this.contextTitle,
            pageKey: this.normalizedPageKey,
          },
        ),
      });
    }

    this.lastPreview = preview;
    return preview;
  }

  undoLastAIOperation(): boolean {
    if (!this.canUndoLastOperation()) {
      return false;
    }

    const undone = this.options.editor.chain().focus().undo().run();
    if (undone) {
      this.lastAppliedRevision = null;
    }
    return undone;
  }

  private async requestDraft(input: {
    agentId: number;
    conversationId: null | number;
    message: string;
    prefix: '/admin' | '/tenant';
  }): Promise<RequestDraftResult> {
    const { sendChatStreamApi } = await import('#/api/shared/ai-chat');
    const abortController = new AbortController();
    const buffer = { value: '' };
    let assistantContent = '';
    let conversationId = input.conversationId;
    let streamError: null | string = null;
    const handleData = (data: string) => {
      if (data === '[DONE]') {
        return;
      }

      const parsed = JSON.parse(data) as {
        content?: string;
        conversation_id?: number;
        delta?: string;
        error?: string;
        event?: string;
        message?: string;
      };

      if (
        typeof parsed.conversation_id === 'number' &&
        Number.isFinite(parsed.conversation_id)
      ) {
        conversationId = parsed.conversation_id;
      }

      if (parsed.event === 'message' && typeof parsed.delta === 'string') {
        assistantContent += parsed.delta;
        return;
      }

      if (parsed.event === 'done' && typeof parsed.content === 'string') {
        assistantContent = parsed.content;
        return;
      }

      if (parsed.error) {
        streamError = parsed.message || parsed.error;
      }
    };

    await sendChatStreamApi(
      input.prefix,
      input.agentId,
      {
        conversation_id: input.conversationId,
        message: input.message,
        route_source: 'rich_text_ai',
      },
      {
        abortController,
        onEnd: () => {},
        onError: (error) => {
          streamError = error.message || 'stream_error';
        },
        onMessage: async (rawChunk) => {
          parseSseDataLines(rawChunk, buffer, handleData);
        },
      },
    );

    parseSseDataLines('\n', buffer, handleData);

    if (streamError) {
      throw new Error(streamError);
    }

    return {
      content: assistantContent,
      conversationId,
    };
  }
}

export function createTiptapEditorAIAdapter(
  options: TiptapEditorAIAdapterOptions,
): EditorAIAdapter {
  return new TiptapEditorAIAdapter({
    ...options,
    pageKey: normalizeRuntimePageKey(options.pageKey),
  });
}

export function getEditorAIErrorMessage(error: unknown): string {
  const messageKeyMap: Record<string, string> = {
    agent_unavailable: 'common.pleaseRetry',
    empty_response: 'common.pleaseRetry',
    empty_selection: 'common.richTextDraftSelectionChanged',
  };

  const code = error instanceof Error ? error.message : String(error ?? '');
  return $t(messageKeyMap[code] ?? 'common.pleaseRetry');
}
