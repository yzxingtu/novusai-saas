import type { Ref } from 'vue';

import type { ConversationItem } from '#/types/ai-chat';

import { computed, ref } from 'vue';

import { Modal } from 'ant-design-vue';

import { $t } from '#/locales';

interface ConversationGroup {
  label: string;
  items: ConversationItem[];
}

interface UsePanelHistoryOptions {
  conversations: Ref<ConversationItem[]>;
  deleteConversation: (convId: number) => Promise<unknown> | unknown;
  loadConversationMessages: (convId: number) => Promise<unknown> | unknown;
  startNewConversation: (forceReset?: boolean) => void;
  updateConversationTitle: (convId: number, title: string) => void;
  clearRoutingIntent: () => void;
  clearResolvedPageOps?: () => void;
  showHistory: Ref<boolean>;
  showMemoryPanel: Ref<boolean>;
}

export function usePanelHistory(options: UsePanelHistoryOptions) {
  const conversationSearch = ref('');
  const editingConversationId = ref<null | number>(null);
  const editingTitle = ref('');

  const filteredConversations = computed(() => {
    const keyword = conversationSearch.value.trim().toLowerCase();
    if (!keyword) return options.conversations.value;
    return options.conversations.value.filter((conv) =>
      (conv.title || '').toLowerCase().includes(keyword),
    );
  });

  const groupedConversations = computed<ConversationGroup[]>(() => {
    const list = filteredConversations.value;
    if (list.length === 0) return [];

    const now = new Date();
    const todayStart = new Date(
      now.getFullYear(),
      now.getMonth(),
      now.getDate(),
    ).getTime();
    const yesterdayStart = todayStart - 86_400_000;

    const today: ConversationItem[] = [];
    const yesterday: ConversationItem[] = [];
    const earlier: ConversationItem[] = [];

    for (const conv of list) {
      const timestamp = new Date(conv.created_at).getTime();
      if (timestamp >= todayStart) {
        today.push(conv);
      } else if (timestamp >= yesterdayStart) {
        yesterday.push(conv);
      } else {
        earlier.push(conv);
      }
    }

    const groups: ConversationGroup[] = [];
    if (today.length > 0) {
      groups.push({ label: $t('common.globalAiChat.today'), items: today });
    }
    if (yesterday.length > 0) {
      groups.push({
        label: $t('common.globalAiChat.yesterday'),
        items: yesterday,
      });
    }
    if (earlier.length > 0) {
      groups.push({ label: $t('common.globalAiChat.earlier'), items: earlier });
    }
    return groups;
  });

  function toggleHistory() {
    options.showHistory.value = !options.showHistory.value;
    if (!options.showHistory.value) {
      conversationSearch.value = '';
    }
  }

  function onSelectConversation(convId: number) {
    options.clearRoutingIntent();
    options.clearResolvedPageOps?.();
    options.loadConversationMessages(convId);
    options.showHistory.value = false;
    options.showMemoryPanel.value = false;
    conversationSearch.value = '';
  }

  function onDeleteConversation(convId: number) {
    Modal.confirm({
      title: $t('common.globalAiChat.confirmDelete'),
      onOk: () => options.deleteConversation(convId),
    });
  }

  function startEditTitle(conv: { id: number; title?: null | string }) {
    editingConversationId.value = conv.id;
    editingTitle.value = conv.title || '';
  }

  function commitEditTitle() {
    const id = editingConversationId.value;
    if (id === null) return;
    const title = editingTitle.value.trim().slice(0, 200);
    editingConversationId.value = null;
    editingTitle.value = '';
    options.updateConversationTitle(id, title);
  }

  function cancelEditTitle() {
    editingConversationId.value = null;
    editingTitle.value = '';
  }

  function onStartNewChat() {
    options.clearRoutingIntent();
    options.clearResolvedPageOps?.();
    options.startNewConversation();
    options.showHistory.value = false;
    options.showMemoryPanel.value = false;
  }

  return {
    cancelEditTitle,
    commitEditTitle,
    conversationSearch,
    editingConversationId,
    editingTitle,
    filteredConversations,
    groupedConversations,
    onDeleteConversation,
    onSelectConversation,
    onStartNewChat,
    startEditTitle,
    toggleHistory,
  };
}
