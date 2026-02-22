/**
 * useEditorAI 组合式函数
 *
 * 封装编辑器 AI 功能与 AgentChatService 的通信层。
 * 通过 resolve 机制获取 agentId，不再从插件 config 读取。
 * 支持 SSE 流式调用、replace/insert/append 模式、loading 状态管理
 */
import { ref, type Ref } from 'vue';

import type { Editor } from '@tiptap/core';


/** AI 操作类型 */
export type AIAction =
  | 'continue_writing'
  | 'improve_writing'
  | 'fix_grammar'
  | 'translate'
  | 'summarize'
  | 'expand'
  | 'explain_code'
  | 'comment_code'
  | 'custom';

/** AI 插入模式 */
export type AIInsertMode = 'replace' | 'insert' | 'append';

/** AI 请求参数 */
export interface AIRequestParams {
  action: AIAction;
  content: string;
  context?: string;
  language?: string;
  customPrompt?: string;
  insertMode?: AIInsertMode;
}

/** AI 配置（由 resolve 机制填充） */
export interface EditorAIConfig {
  /** resolve 出的智能体 ID */
  agentId: number | null;
  /** AI 是否可用（config.ai_enabled && resolve.is_active） */
  enabled: boolean;
}

export function useEditorAI(
  editor: Ref<Editor | undefined>,
  config: Ref<EditorAIConfig>,
) {
  const isLoading = ref(false);
  const isStreaming = ref(false);
  const error = ref<string | null>(null);
  let abortController: AbortController | null = null;

  /** 获取选中文本 */
  function getSelection(): string {
    if (!editor.value) return '';
    const { from, to } = editor.value.state.selection;
    return editor.value.state.doc.textBetween(from, to, ' ');
  }

  /** 获取光标前上下文（最多 2000 字符）*/
  function getContextBefore(maxLength = 2000): string {
    if (!editor.value) return '';
    const { from } = editor.value.state.selection;
    const start = Math.max(0, from - maxLength);
    return editor.value.state.doc.textBetween(start, from, ' ');
  }

  /** 获取全文内容 */
  function getFullText(): string {
    if (!editor.value) return '';
    return editor.value.getText();
  }

  /** 构建 AI prompt */
  function buildPrompt(params: AIRequestParams): string {
    const { action, content, context, language, customPrompt } = params;

    const prompts: Record<AIAction, string> = {
      continue_writing: `Continue writing the following text naturally. Keep the same style and tone.\n\nContext:\n${context || ''}\n\nText to continue from:\n${content}`,
      improve_writing: `Improve the following text to make it more fluent and professional. Keep the original meaning.\n\nText:\n${content}`,
      fix_grammar: `Fix all grammar and spelling errors in the following text. Only return the corrected text.\n\nText:\n${content}`,
      translate: `Translate the following text to ${language || 'English'}. Only return the translated text.\n\nText:\n${content}`,
      summarize: `Generate a concise summary of the following text.\n\nText:\n${content}`,
      expand: `Expand the following text with more details and examples.\n\nText:\n${content}`,
      explain_code: `Explain the following code in natural language. Be clear and concise.\n\nCode:\n${content}`,
      comment_code: `Add inline comments to the following code to explain what each part does.\n\nCode:\n${content}`,
      custom: customPrompt || content,
    };

    return prompts[action] || content;
  }

  /** 发送 AI 请求（SSE 流式，调用 Agent Chat API）*/
  async function sendAIRequest(
    params: AIRequestParams,
    onChunk?: (text: string) => void,
  ): Promise<string> {
    if (!config.value.agentId || !config.value.enabled) {
      throw new Error('AI is not configured or disabled');
    }

    isLoading.value = true;
    isStreaming.value = false;
    error.value = null;
    abortController = new AbortController();

    const prompt = buildPrompt(params);
    let fullResponse = '';

    try {
      // 通过 resolve 获取的 agentId 调用 Agent Chat API
      const agentId = config.value.agentId;
      const response = await fetch(
        `/api/tenant/agent-chat/${agentId}/chat`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${getAuthToken()}`,
          },
          body: JSON.stringify({
            message: prompt,
            stream: true,
          }),
          signal: abortController.signal,
        },
      );

      if (!response.ok) {
        throw new Error(`AI request failed: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      isStreaming.value = true;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') continue;

            try {
              const parsed = JSON.parse(data);
              const text =
                parsed.choices?.[0]?.delta?.content ||
                parsed.content ||
                parsed.text ||
                '';
              if (text) {
                fullResponse += text;
                onChunk?.(text);
              }
            } catch {
              // skip unparseable chunks
            }
          }
        }
      }
    } catch (err: unknown) {
      if ((err as Error).name === 'AbortError') {
        // cancelled by user
      } else {
        error.value = (err as Error).message;
        throw err;
      }
    } finally {
      isLoading.value = false;
      isStreaming.value = false;
      abortController = null;
    }

    return fullResponse;
  }

  /** 获取认证 token（租户端） */
  function getAuthToken(): string {
    return localStorage.getItem('tenant_access_token') || '';
  }

  /** 执行 AI 操作并插入编辑器 */
  async function executeAI(params: AIRequestParams): Promise<void> {
    if (!editor.value) return;

    const mode = params.insertMode || 'insert';

    if (mode === 'replace') {
      // 替换选中文本 - 先删除选中内容
      editor.value.chain().focus().deleteSelection().run();
    } else if (mode === 'append') {
      // 末尾追加
      editor.value.commands.focus('end');
    }

    // 流式插入：每次插入后从编辑器状态获取最新光标位置
    await sendAIRequest(params, (chunk) => {
      if (!editor.value) return;
      // 获取当前光标位置（由上次插入后自动更新）
      const pos = editor.value.state.selection.from;
      editor.value
        .chain()
        .insertContentAt(pos, chunk)
        .focus()
        .run();
    });
  }

  /** 取消当前 AI 请求 */
  function cancelAI() {
    abortController?.abort();
    isLoading.value = false;
    isStreaming.value = false;
  }

  // ==================== 快捷操作 ====================

  /** AI 续写 */
  async function continueWriting() {
    const context = getContextBefore();
    const content = getSelection() || context.slice(-500);
    await executeAI({
      action: 'continue_writing',
      content,
      context,
      insertMode: 'insert',
    });
  }

  /** AI 优化 */
  async function improveWriting() {
    const content = getSelection();
    if (!content) return;
    await executeAI({
      action: 'improve_writing',
      content,
      insertMode: 'replace',
    });
  }

  /** AI 校对 */
  async function fixGrammar() {
    const content = getSelection();
    if (!content) return;
    await executeAI({
      action: 'fix_grammar',
      content,
      insertMode: 'replace',
    });
  }

  /** AI 翻译 */
  async function translate(language: string) {
    const content = getSelection();
    if (!content) return;
    await executeAI({
      action: 'translate',
      content,
      language,
      insertMode: 'replace',
    });
  }

  /** AI 摘要 */
  async function summarize() {
    const content = getSelection() || getFullText();
    if (!content) return;
    await executeAI({
      action: 'summarize',
      content,
      insertMode: 'append',
    });
  }

  /** AI 扩写 */
  async function expand() {
    const content = getSelection();
    if (!content) return;
    await executeAI({
      action: 'expand',
      content,
      insertMode: 'replace',
    });
  }

  /** AI 代码解释 */
  async function explainCode() {
    const content = getSelection();
    if (!content) return;
    await executeAI({
      action: 'explain_code',
      content,
      insertMode: 'append',
    });
  }

  /** AI 代码注释 */
  async function commentCode() {
    const content = getSelection();
    if (!content) return;
    await executeAI({
      action: 'comment_code',
      content,
      insertMode: 'replace',
    });
  }

  /** 自定义 AI 操作 */
  async function customAI(prompt: string, insertMode: AIInsertMode = 'insert') {
    const content = getSelection() || getContextBefore(1000);
    await executeAI({
      action: 'custom',
      content,
      customPrompt: prompt.replace('{selection}', getSelection()).replace('{context}', getContextBefore()),
      insertMode,
    });
  }

  return {
    // 状态
    isLoading,
    isStreaming,
    error,
    // 操作
    continueWriting,
    improveWriting,
    fixGrammar,
    translate,
    summarize,
    expand,
    explainCode,
    commentCode,
    customAI,
    cancelAI,
    // 底层
    executeAI,
    sendAIRequest,
    getSelection,
    getContextBefore,
    getFullText,
  };
}
