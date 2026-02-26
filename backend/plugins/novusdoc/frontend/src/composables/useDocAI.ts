/**
 * NovusDoc AI composable
 *
 * Manages AI feature calls, ghost text preview, and streaming state.
 */

import { ref, shallowRef } from 'vue';
import type { Editor } from '@tiptap/core';
import { streamAIFeature } from '../api/ai';
import type { AIFeature, AIRequestBody } from '../api/ai';

// 替换类功能：采纳时替换选中文字或全文（而非追加）
const REPLACE_FEATURES = new Set([
  'optimize', 'proofread', 'translate', 'rewrite', 'summarize', 'expand', 'custom',
]);

/**
 * 将 AI 返回的文本（可能包含 markdown 格式）转为 Tiptap 可识别的 HTML。
 * 处理：段落、粗体、无序列表、有序列表、行内代码、混合内容块。
 */
function markdownToHtml(text: string): string {
  if (!text) return '';

  const htmlParts: string[] = [];
  const lines = text.split('\n');
  let i = 0;

  while (i < lines.length) {
    const line = lines[i]!.trimEnd();

    // 跳过空行
    if (!line.trim()) { i++; continue; }

    // 无序列表块（连续 - 或 * 开头的行）
    if (/^[-*]\s/.test(line.trim())) {
      const items: string[] = [];
      while (i < lines.length && /^[-*]\s/.test(lines[i]!.trim())) {
        items.push(`<li>${inlineFormat(lines[i]!.trim().replace(/^[-*]\s+/, ''))}</li>`);
        i++;
      }
      htmlParts.push(`<ul>${items.join('')}</ul>`);
      continue;
    }

    // 有序列表块（连续 1. 2. 开头的行）
    if (/^\d+\.\s/.test(line.trim())) {
      const items: string[] = [];
      while (i < lines.length && /^\d+\.\s/.test(lines[i]!.trim())) {
        items.push(`<li>${inlineFormat(lines[i]!.trim().replace(/^\d+\.\s+/, ''))}</li>`);
        i++;
      }
      htmlParts.push(`<ol>${items.join('')}</ol>`);
      continue;
    }

    // 普通段落：收集连续非空非列表行
    const paraLines: string[] = [];
    while (i < lines.length) {
      const cur = lines[i]!.trimEnd();
      // 遇到空行或列表行则段落结束
      if (!cur.trim() || /^[-*]\s/.test(cur.trim()) || /^\d+\.\s/.test(cur.trim())) break;
      paraLines.push(inlineFormat(cur));
      i++;
    }
    if (paraLines.length > 0) {
      htmlParts.push(`<p>${paraLines.join('<br>')}</p>`);
    }
  }

  return htmlParts.join('');
}

/** 行内格式：**粗体**、`代码` */
function inlineFormat(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`(.+?)`/g, '<code>$1</code>');
}

export function useDocAI(docId: () => number, editor: () => Editor | undefined) {
  const loading = ref(false);
  const ghostText = ref('');
  const error = ref('');
  const lastFeature = ref('');
  const abortController = shallowRef<AbortController | null>(null);
  // 记录调用 AI 时的选区范围，采纳时用于替换
  const savedSelection = ref<{ from: number; to: number } | null>(null);

  function getEditorContext(): AIRequestBody {
    const ed = editor();
    if (!ed) return {};

    const { from } = ed.state.selection;
    const doc = ed.state.doc;

    const beforeText = doc.textBetween(0, Math.min(from, doc.content.size), '\n');
    const afterText = doc.textBetween(
      Math.min(from, doc.content.size),
      doc.content.size,
      '\n',
    );

    const { from: selFrom, to: selTo } = ed.state.selection;
    const selectedText =
      selFrom !== selTo ? doc.textBetween(selFrom, selTo, '\n') : '';

    return {
      selected_text: selectedText,
      before_text: beforeText,
      after_text: afterText,
    };
  }

  async function runAIFeature(
    feature: AIFeature,
    extra?: Partial<AIRequestBody>,
  ): Promise<string> {
    if (loading.value) return '';

    // Abort any previous in-flight request
    abortController.value?.abort();

    const ctrl = new AbortController();
    abortController.value = ctrl;

    loading.value = true;
    ghostText.value = '';
    error.value = '';
    lastFeature.value = feature;

    // 记录当前选区（采纳时用于替换）
    const ed = editor();
    if (ed) {
      const { from, to } = ed.state.selection;
      savedSelection.value = from !== to ? { from, to } : null;
    }

    const body: AIRequestBody = {
      ...getEditorContext(),
      ...extra,
    };

    let fullText = '';

    try {
      for await (const delta of streamAIFeature(docId(), feature, body, ctrl.signal)) {
        if (ctrl.signal.aborted) break;
        fullText += delta;
        ghostText.value = fullText;
      }
    } catch (e: unknown) {
      if (ctrl.signal.aborted) {
        // User cancelled — not an error
      } else {
        const msg = e instanceof Error ? e.message : String(e);
        error.value = msg;
        console.warn('[novusdoc] AI error:', msg);
      }
    } finally {
      loading.value = false;
      if (abortController.value === ctrl) {
        abortController.value = null;
      }
    }

    return fullText;
  }

  async function aiContinue(): Promise<string> {
    return runAIFeature('continue');
  }

  async function aiOptimize(): Promise<string> {
    return runAIFeature('optimize');
  }

  async function aiProofread(): Promise<string> {
    return runAIFeature('proofread');
  }

  async function aiTranslate(targetLang: string = 'English'): Promise<string> {
    return runAIFeature('translate', { target_lang: targetLang });
  }

  async function aiSummarize(): Promise<string> {
    return runAIFeature('summarize');
  }

  async function aiExpand(): Promise<string> {
    return runAIFeature('expand');
  }

  async function aiRewrite(): Promise<string> {
    return runAIFeature('rewrite');
  }

  async function aiCustom(instruction: string): Promise<string> {
    return runAIFeature('custom', { instruction });
  }

  async function aiChat(
    instruction: string,
    history?: Array<{ role: string; content: string }>,
  ): Promise<string> {
    return runAIFeature('chat', { instruction, history });
  }

  function acceptGhostText() {
    const ed = editor();
    if (!ed || !ghostText.value) return;

    const isReplaceFeature = REPLACE_FEATURES.has(lastFeature.value);
    const sel = savedSelection.value;

    // 将 AI 返回的 markdown 文本转为 HTML（保留段落/粗体/列表等格式）
    const html = markdownToHtml(ghostText.value);

    if (sel && sel.from !== sel.to) {
      // 有选区 → 替换选中的文字
      ed.chain().focus().deleteRange(sel).insertContentAt(sel.from, html, { parseOptions: { preserveWhitespace: false } }).run();
    } else if (isReplaceFeature) {
      // 替换类功能（优化/校对/翻译等）+ 无选区 → 替换全文
      ed.chain().focus().selectAll().deleteSelection().insertContent(html, { parseOptions: { preserveWhitespace: false } }).run();
    } else {
      // 续写类功能（continue）→ 追加到光标位置
      ed.chain().focus().insertContent(html, { parseOptions: { preserveWhitespace: false } }).run();
    }

    ghostText.value = '';
    savedSelection.value = null;
    lastFeature.value = '';
  }

  function dismissGhostText() {
    ghostText.value = '';
    savedSelection.value = null;
    lastFeature.value = '';
  }

  function cancel() {
    abortController.value?.abort();
    loading.value = false;
    ghostText.value = '';
    savedSelection.value = null;
    lastFeature.value = '';
  }

  return {
    loading,
    ghostText,
    error,
    runAIFeature,
    aiContinue,
    aiOptimize,
    aiProofread,
    aiTranslate,
    aiSummarize,
    aiExpand,
    aiRewrite,
    aiCustom,
    aiChat,
    acceptGhostText,
    dismissGhostText,
    cancel,
  };
}
