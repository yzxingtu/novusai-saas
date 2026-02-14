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
const CRUD_AGENT_NAME = 'crud_generator_assistant';

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

  /** Build a compact config summary for the agent */
  function buildConfigContext(cfg: CrudConfig): string {
    const lines: string[] = [];
    if (cfg.module) lines.push(`module: ${cfg.module}`);
    if (cfg.table_name) lines.push(`table: ${cfg.table_name}`);
    if (cfg.display_name) lines.push(`display_name: ${cfg.display_name}`);
    lines.push(`scope: ${cfg.scope}`);
    if (cfg.fields.length > 0) {
      lines.push(
        `fields: [${cfg.fields.map((f) => `${f.name}(${f.type})`).join(', ')}]`,
      );
    }
    if (cfg.relations.length > 0) {
      lines.push(
        `relations: [${cfg.relations.map((r) => `${r.name}(${r.type})`).join(', ')}]`,
      );
    }
    return lines.join('\n');
  }

  /**
   * Watch for completed tool calls that contain config updates.
   * The CRUD agent's tools return JSON with a `config` key containing
   * partial CrudConfig to merge.
   */
  watch(
    () => chat.chatMessages.value,
    (messages) => {
      if (messages.length === 0) return;
      const last = messages.at(-1);
      if (!last || last.role !== 'assistant' || last.streaming) return;

      // Check tool calls for config patches
      if (last.toolCalls) {
        for (const tc of last.toolCalls) {
          if (tc.status === 'success' && tc.output) {
            tryApplyConfigPatch(tc.output);
          }
        }
      }
    },
    { deep: true },
  );

  /** Attempt to parse tool output as a config patch and apply it via mergeConfig */
  function tryApplyConfigPatch(output: string) {
    try {
      const parsed = JSON.parse(output);
      if (parsed && typeof parsed === 'object' && (parsed.config || parsed.fields || parsed.module)) {
        const patch = parsed.config ?? parsed;

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
    } catch {
      // Not a JSON config patch, ignore
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

    // Merge
    lastMergeSummary,
  };
}

export type UseCrudAiAssistantReturn = ReturnType<typeof useCrudAiAssistant>;
