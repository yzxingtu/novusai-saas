/**
 * Editor AI composable -- calls platform-level AI writing endpoints via SSE.
 */

import type { Editor } from '@tiptap/core';
import type { ShallowRef } from 'vue';

import { ref, unref } from 'vue';

import MarkdownIt from 'markdown-it';

import { requestClient } from '#/utils/request';

const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
  // Ensure headings and lists produce proper block-level HTML for TipTap
  typographer: false,
});

function getAIWritingPath(feature: string): string {
  const isAdmin = window.location.pathname.startsWith('/admin');
  const prefix = isAdmin ? '/admin/ai/writing' : '/tenant/ai/writing';
  return `${prefix}/${feature}`;
}

export function useEditorAI(editorRef: ShallowRef<Editor | undefined>) {
  const aiLoading = ref(false);
  const aiResult = ref('');

  let abortController: AbortController | null = null;

  function getEditorContext() {
    const editor = unref(editorRef);
    if (!editor) return { selected_text: '', before_text: '', after_text: '' };

    const { from, to } = editor.state.selection;
    const selectedText = editor.state.doc.textBetween(from, to, '\n');
    const fullText = editor.getText();

    return {
      selected_text: selectedText,
      before_text: fullText.slice(0, from).slice(-2000),
      after_text: fullText.slice(to, to + 500),
    };
  }

  async function streamAI(
    feature: string,
    extra: Record<string, unknown> = {},
  ) {
    if (aiLoading.value) return;

    aiLoading.value = true;
    aiResult.value = '';
    abortController = new AbortController();

    const context = getEditorContext();
    const body: Record<string, unknown> = { ...context, ...extra };

    if (extra.withFormat) {
      body.format_instruction =
        '请使用 Markdown 格式输出（如标题用 #、列表用 -、重点用 **粗体**、代码用 `反引号` 等）。';
    }

    let sseBuffer = '';

    try {
      await requestClient.postSSE(getAIWritingPath(feature), body, {
        abortController,
        onMessage(chunk: string) {
          sseBuffer += chunk;
          const lines = sseBuffer.split('\n');
          sseBuffer = lines.pop() || '';

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed.startsWith('data: ')) continue;
            const payload = trimmed.slice(6);
            if (payload === '[DONE]') return;

            try {
              const event = JSON.parse(payload);
              if (event.error) return;
              if (event.event === 'message' && event.delta) {
                aiResult.value += event.delta;
              }
            } catch {
              // skip unparseable lines / 跳过无法解析的行
            }
          }
        },
        onError(err: Error) {
          console.error('AI stream error:', err);
        },
      });
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        console.error('AI stream error:', err);
      }
    } finally {
      aiLoading.value = false;
      abortController = null;
    }
  }

  function cancelAI() {
    abortController?.abort();
    aiLoading.value = false;
  }

  function acceptResult(withFormat: boolean = false) {
    const editor = unref(editorRef);
    if (!editor || !aiResult.value) return;

    const { from, to } = editor.state.selection;
    const hasSelection = from !== to;

    let content: string;
    if (withFormat) {
      const rawHtml = md.render(aiResult.value);
      // Remove newlines between tags so TipTap does not create extra blank paragraphs
      content = rawHtml.replace(/>\s+</g, '><').trim();
    } else {
      content = aiResult.value;
    }

    if (hasSelection) {
      editor
        .chain()
        .focus()
        .deleteRange({ from, to })
        .insertContent(content, { parseOptions: { preserveWhitespace: false } })
        .run();
    } else {
      editor
        .chain()
        .focus()
        .insertContent(content, { parseOptions: { preserveWhitespace: false } })
        .run();
    }

    aiResult.value = '';
  }

  function discardResult() {
    aiResult.value = '';
  }

  return {
    aiLoading,
    aiResult,
    streamAI,
    cancelAI,
    acceptResult,
    discardResult,
  };
}
