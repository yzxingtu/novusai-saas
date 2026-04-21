import type { Ref } from 'vue';

import type { AgentItem, ChatAttachment, ChatMessage } from './types';

import { $t } from '#/locales';

import { getToolCallsForDisplay } from './chat-message-turn-flow';
import {
  formatDurationSeconds,
  formatToolStatusLabel,
} from './display-formatters';

interface UseAIChatExportDeps {
  activeConversationId: Ref<null | number>;
  chatMessages: Ref<ChatMessage[]>;
  selectedAgent: Ref<AgentItem | null>;
}

export function useAIChatExport(deps: UseAIChatExportDeps) {
  const { activeConversationId, chatMessages, selectedAgent } = deps;

  function getExportAttachmentTypeLabel(type: ChatAttachment['type']): string {
    switch (type) {
      case 'file': {
        return $t('common.globalAiChat.file');
      }
      case 'image': {
        return $t('common.image');
      }
      default: {
        return type;
      }
    }
  }

  function buildExportAttachmentLines(
    attachments?: ChatAttachment[],
    format: 'markdown' | 'text' = 'markdown',
  ): string[] {
    if (!attachments?.length) return [];

    const lines = [
      format === 'markdown'
        ? `**${$t('common.globalAiChat.attachments')}:**`
        : `${$t('common.globalAiChat.attachments')}:`,
    ];

    for (const attachment of attachments) {
      const typeLabel = getExportAttachmentTypeLabel(attachment.type);
      const attachmentLabel =
        attachment.name || attachment.url || $t('common.notSet');
      lines.push(`- ${typeLabel}: ${attachmentLabel}`);
      if (attachment.attachment_id) {
        lines.push(
          `  ${$t('common.globalAiChat.attachmentId')}: ${attachment.attachment_id}`,
        );
      }
      if (attachment.url) {
        lines.push(
          `  ${$t('common.globalAiChat.exportUrl')}: ${attachment.url}`,
        );
      }
    }

    lines.push('');
    return lines;
  }

  function exportAsMarkdown() {
    if (chatMessages.value.length === 0) return;
    const agentName =
      selectedAgent.value?.name || $t('common.globalAiChat.assistant');
    const userLabel = $t('common.globalAiChat.user');
    const lines: string[] = [
      `# ${agentName} - ${$t('common.globalAiChat.history')}`,
      '',
    ];
    for (const msg of chatMessages.value) {
      const role =
        msg.role === 'user' ? `**${userLabel}**` : `**${agentName}**`;
      lines.push(`### ${role}`, '');
      if (msg.content) lines.push(msg.content);
      lines.push(...buildExportAttachmentLines(msg.attachments, 'markdown'));
      const toolCalls = getToolCallsForDisplay(msg);
      if (toolCalls?.length) {
        lines.push('');
        for (const tc of toolCalls) {
          const duration = tc.durationMs
            ? ` (${formatDurationSeconds(tc.durationMs)})`
            : '';
          const skill = tc.skillName ? `${tc.skillName} › ` : '';
          lines.push(
            `> 🔧 ${skill}${tc.displayName || tc.name} — ${formatToolStatusLabel(tc.status)}${duration}`,
          );
          if (tc.arguments && Object.keys(tc.arguments).length > 0) {
            lines.push(
              `> **${$t('common.globalAiChat.exportArgs')}:** \`${JSON.stringify(tc.arguments)}\``,
            );
          }
          if (tc.output) {
            lines.push(
              `> **${$t('common.globalAiChat.exportOutput')}:** ${tc.output.slice(0, 500)}${tc.output.length > 500 ? '...' : ''}`,
            );
          }
          if (tc.error) {
            lines.push(
              `> **${$t('common.globalAiChat.exportError')}:** ${tc.error}`,
            );
          }
        }
      }
      lines.push('');
    }
    const blob = new Blob([lines.join('\n')], {
      type: 'text/markdown;charset=utf-8',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `chat-${activeConversationId.value || 'new'}-${Date.now()}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function exportAsPlainText() {
    if (chatMessages.value.length === 0) return;
    const agentName =
      selectedAgent.value?.name || $t('common.globalAiChat.assistant');
    const lines: string[] = [];
    for (const msg of chatMessages.value) {
      const label =
        msg.role === 'user' ? $t('common.globalAiChat.user') : agentName;
      lines.push(`${label}:`);
      if (msg.content) lines.push(msg.content);
      lines.push(...buildExportAttachmentLines(msg.attachments, 'text'), '');
    }
    const blob = new Blob([lines.join('\n')], {
      type: 'text/plain;charset=utf-8',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `chat-${activeConversationId.value || 'new'}-${Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return {
    exportAsMarkdown,
    exportAsPlainText,
  };
}
