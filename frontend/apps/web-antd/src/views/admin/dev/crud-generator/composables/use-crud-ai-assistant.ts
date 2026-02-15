/**
 * CRUD Generator — AI 助手 composable
 *
 * 复用 useAIChat 基础设施，指定 agentName 为 crud_generator_assistant。
 * 监听 tool_call 事件，解析返回的 CrudConfig 片段并合并到 Wizard 状态。
 */

import type { Ref } from 'vue';

import { onMounted, onUnmounted, ref, watch } from 'vue';

import { useAIChat } from '#/components/business/ai-chat-panel';

import type { CrudConfig } from '../types';

import type { MergeSummary, TouchedPaths } from './use-config-merge';

import { mergeConfig } from './use-config-merge';

/** System CRUD Agent name (resolved by name, not hardcoded id) */
const CRUD_AGENT_NAME = 'CRUD 生成助手';

export interface UseCrudAiAssistantOptions {
  config: Ref<CrudConfig>;
  loadConfig: (data: CrudConfig) => void;
  snapshot: () => void;
  touchedPaths: TouchedPaths;
}

export function useCrudAiAssistant(options: UseCrudAiAssistantOptions) {
  const chat = useAIChat({
    apiPrefix: '/admin',
    uploadUrl: '/admin/ai/agent-chat/attachments',
  });

  const drawerOpen = ref(false);
  const agentReady = ref(false);
  const agentError = ref(false);
  const lastMergeSummary = ref<MergeSummary | null>(null);

  /** Load agents and auto-select the CRUD generator agent by name */
  async function initAgent() {
    await chat.loadAgents();

    const crudAgent = chat.agents.value.find(
      (a) => a.name === CRUD_AGENT_NAME,
    );

    if (crudAgent) {
      chat.selectAgent(crudAgent.id);
      agentReady.value = true;
    } else {
      agentError.value = true;
    }
  }

  /** Open the AI assistant drawer */
  function open() {
    drawerOpen.value = true;
    if (!agentReady.value && !agentError.value) {
      initAgent();
    }
  }

  /** Close the drawer */
  function close() {
    drawerOpen.value = false;
  }

  /**
   * Send a pre-composed message (used by quick action buttons).
   * Prepends current config context so the agent knows the state.
   */
  function sendQuickAction(action: string) {
    const configSummary = buildConfigContext(options.config.value);
    chat.inputMessage.value = `${action}\n\n当前配置摘要:\n${configSummary}`;
    chat.sendMessage();
  }

  /** Build a compact config summary for the agent with step context */
  function buildConfigContext(cfg: CrudConfig): string {
    const STEP_NAMES = ['基本信息', '字段定义', '列表配置', '表单配置', '代码预览'];
    const lines: string[] = [];

    lines.push(`当前步骤: Step ${currentStep} — ${STEP_NAMES[currentStep] ?? '未知'}`);
    if (cfg.module) lines.push(`module: ${cfg.module}`);
    if (cfg.table_name) lines.push(`table: ${cfg.table_name}`);
    if (cfg.display_name) lines.push(`display_name: ${cfg.display_name}`);
    lines.push(`scope: ${cfg.scope}`);

    if (cfg.fields.length > 0) {
      lines.push(
        `fields(${cfg.fields.length}): [${cfg.fields.map((f) => `${f.name}(${f.type})`).join(', ')}]`,
      );
      const listFields = cfg.fields.filter((f) => f.in_list).length;
      const formFields = cfg.fields.filter((f) => f.in_form).length;
      const searchFields = cfg.search_config?.fields?.length ?? 0;
      lines.push(`  列表字段: ${listFields}, 表单字段: ${formFields}, 搜索字段: ${searchFields}`);
    } else {
      lines.push('fields: (尚未定义字段)');
    }

    if (cfg.relations.length > 0) {
      lines.push(
        `relations: [${cfg.relations.map((r) => `${r.name}(${r.type})`).join(', ')}]`,
      );
    }

    if (cfg.enums && cfg.enums.length > 0) {
      lines.push(`enums: [${cfg.enums.map((e) => e.name).join(', ')}]`);
    }

    return lines.join('\n');
  }

  /** Current step ref for context building */
  let currentStep = 0;
  function setCurrentStep(step: number) {
    currentStep = step;
  }

  /**
   * Watch for completed tool calls that contain config updates.
   * Routes tool output to the appropriate handler based on tool name.
   */
  watch(
    () => chat.chatMessages.value,
    (messages) => {
      if (messages.length === 0) return;
      const last = messages.at(-1);
      if (!last || last.role !== 'assistant' || last.streaming) return;

      if (last.toolCalls) {
        for (const tc of last.toolCalls) {
          if (tc.status === 'success' && tc.output) {
            tryApplyToolOutput(tc.name, tc.output);
          }
        }
      }
    },
    { deep: true },
  );

  /**
   * Safely parse JSON with tolerance for trailing commas, comments, etc.
   */
  function safeJsonParse(text: string): Record<string, unknown> | null {
    try {
      return JSON.parse(text);
    } catch {
      // Try fixing common LLM JSON issues
      try {
        const cleaned = text
          .replace(/,\s*([}\]])/g, '$1')  // trailing commas
          .replace(/\/\/[^\n]*/g, '')      // single-line comments
          .replace(/\/\*[\s\S]*?\*\//g, ''); // block comments
        return JSON.parse(cleaned);
      } catch {
        // Try extracting JSON from markdown code blocks
        const match = text.match(/```(?:json)?\s*([\s\S]*?)```/);
        if (match?.[1]) {
          try {
            return JSON.parse(match[1].trim());
          } catch {
            return null;
          }
        }
        return null;
      }
    }
  }

  /**
   * Route tool output to the appropriate handler based on tool name.
   * - Config tools: merge into wizard config
   * - Preview/generate tools: informational only (displayed in chat)
   * - Suggest/translate tools: merge partial patches
   */
  function tryApplyToolOutput(toolName: string, output: string) {
    const parsed = safeJsonParse(output);
    if (!parsed || typeof parsed !== 'object') return;

    switch (toolName) {
      // Full config generation → replace/merge entire config
      case 'crud_generate_config': {
        applyFullConfig(parsed);
        break;
      }

      // Field suggestions → merge fields array
      case 'crud_suggest_fields': {
        applyFieldsPatch(parsed);
        break;
      }

      // Slot code → merge into custom_slots
      case 'crud_generate_slot': {
        applySlotPatch(parsed);
        break;
      }

      // Style recommendation → merge layout/style config
      case 'crud_recommend_style': {
        applyStylePatch(parsed);
        break;
      }

      // Intent analysis → informational, try to extract entity hints
      case 'crud_analyze_intent': {
        // Informational — displayed in chat, no config merge
        break;
      }

      // i18n translation → no config merge (displayed in chat)
      case 'crud_translate_i18n': {
        break;
      }

      // Preview/generate/batch tools → informational or confirmation flow
      case 'crud_preview_code':
      case 'crud_generate_files':
      case 'crud_batch_preview':
      case 'crud_batch_generate_files':
      case 'crud_batch_validate':
      case 'crud_batch_merge_patch':
      case 'crud_batch_generate_config': {
        // These are informational or require confirmation — displayed in chat
        break;
      }

      // Unknown tool → fallback to legacy heuristic merge
      default: {
        tryLegacyConfigPatch(parsed);
        break;
      }
    }
  }

  /** Apply a full CrudConfig (from crud_generate_config) */
  function applyFullConfig(parsed: Record<string, unknown>) {
    // The AI may return the config directly or wrapped in {config: ...}
    const configData = (parsed.config ?? parsed) as Partial<CrudConfig>;

    // Must have at least module or table_name to be a valid config
    if (!configData.module && !configData.table_name && !configData.fields) return;

    const { config: merged, summary } = mergeConfig(
      options.config.value,
      configData,
      options.touchedPaths,
    );

    lastMergeSummary.value = summary;

    if (summary.added > 0 || summary.updated > 0) {
      options.loadConfig(merged);
      options.snapshot();
    }
  }

  /** Apply fields suggestions (from crud_suggest_fields) */
  function applyFieldsPatch(parsed: Record<string, unknown>) {
    const fields = parsed.fields as CrudConfig['fields'] | undefined;
    if (!fields || !Array.isArray(fields)) return;

    const { config: merged, summary } = mergeConfig(
      options.config.value,
      { fields } as Partial<CrudConfig>,
      options.touchedPaths,
    );

    lastMergeSummary.value = summary;

    if (summary.added > 0 || summary.updated > 0) {
      options.loadConfig(merged);
      options.snapshot();
    }
  }

  /** Apply slot code (from crud_generate_slot) */
  function applySlotPatch(parsed: Record<string, unknown>) {
    const slots = parsed.custom_slots ?? parsed.slots;
    if (slots && Array.isArray(slots)) {
      const { config: merged, summary } = mergeConfig(
        options.config.value,
        { custom_slots: slots } as Partial<CrudConfig>,
        options.touchedPaths,
      );
      lastMergeSummary.value = summary;
      if (summary.added > 0 || summary.updated > 0) {
        options.loadConfig(merged);
        options.snapshot();
      }
    }
  }

  /** Apply style/layout recommendation (from crud_recommend_style) */
  function applyStylePatch(parsed: Record<string, unknown>) {
    const patch: Partial<CrudConfig> = {};
    if (parsed.layout_variant) {
      (patch as Record<string, unknown>).layout_variant = parsed.layout_variant;
    }
    if (parsed.page_style) {
      (patch as Record<string, unknown>).page_style = parsed.page_style;
    }
    if (Object.keys(patch).length > 0) {
      const { config: merged, summary } = mergeConfig(
        options.config.value,
        patch,
        options.touchedPaths,
      );
      lastMergeSummary.value = summary;
      if (summary.added > 0 || summary.updated > 0) {
        options.loadConfig(merged);
        options.snapshot();
      }
    }
  }

  /** Legacy fallback: heuristic config patch detection */
  function tryLegacyConfigPatch(parsed: Record<string, unknown>) {
    if (parsed.config || parsed.fields || parsed.module || parsed.table_name) {
      const patch = (parsed.config ?? parsed) as Partial<CrudConfig>;
      const { config: merged, summary } = mergeConfig(
        options.config.value,
        patch,
        options.touchedPaths,
      );
      lastMergeSummary.value = summary;
      if (summary.added > 0 || summary.updated > 0) {
        options.loadConfig(merged);
        options.snapshot();
      }
    }
  }

  onMounted(() => {
    // Lazy init — don't load agents until drawer is opened
  });

  onUnmounted(() => {
    chat.cleanup();
  });

  return {
    // Drawer state
    drawerOpen,
    open,
    close,
    agentReady,
    agentError,

    // Chat (forwarded)
    chatMessages: chat.chatMessages,
    inputMessage: chat.inputMessage,
    sending: chat.sending,
    streaming: chat.streaming,
    messagesContainer: chat.messagesContainer,
    sendMessage: chat.sendMessage,
    stopGeneration: chat.stopGeneration,
    handleInputKeyDown: chat.handleInputKeyDown,
    scrollToBottom: chat.scrollToBottom,
    handleMessagesScroll: chat.handleMessagesScroll,
    startNewConversation: chat.startNewConversation,
    selectedAgent: chat.selectedAgent,

    // Quick actions
    sendQuickAction,

    // Context
    setCurrentStep,

    // Merge
    lastMergeSummary,
  };
}

export type UseCrudAiAssistantReturn = ReturnType<typeof useCrudAiAssistant>;
