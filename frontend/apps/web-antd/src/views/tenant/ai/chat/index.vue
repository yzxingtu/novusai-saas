<script lang="ts" setup>
/**
 * 租户端智能体对话页面
 *
 * 左侧: 智能体选择 + 历史对话列表
 * 右侧: 聊天界面（Markdown 渲染 + SSE 流式输出）
 */
import type { AgentInfo, AgentListItem } from '#/api/tenant/agents';

defineOptions({ name: 'TenantAIChat' });

import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Button, Card, Input, Modal, Spin, Tooltip, message } from 'ant-design-vue';

import { MarkdownRender } from '#/components/business/markdown-render';
import { getAgentDetailApi, getAgentListApi } from '#/api/tenant/agents';
import { $t } from '#/locales';
import { requestClient } from '#/utils/request';

// ============ 智能体列表 ============

const agents = ref<AgentListItem[]>([]);
const agentsLoading = ref(false);
const selectedAgentId = ref<number | null>(null);

/** 当前选中智能体的详情（含 welcome_message / suggested_questions） */
const agentDetail = ref<AgentInfo | null>(null);

const selectedAgent = computed(() =>
  agents.value.find((a) => a.id === selectedAgentId.value) ?? null,
);

async function loadAgents() {
  agentsLoading.value = true;
  try {
    const res = await getAgentListApi({
      'filter[status][eq]': 'published',
      'page[size]': 100,
    });
    agents.value = res.items;
    if (res.items.length > 0 && !selectedAgentId.value) {
      selectedAgentId.value = res.items[0]!.id;
    }
  } catch {
    // handled by interceptor
  } finally {
    agentsLoading.value = false;
  }
}

/** 选中智能体后加载详情 + 对话列表 */
watch(selectedAgentId, async (id) => {
  if (!id) {
    agentDetail.value = null;
    return;
  }
  try {
    agentDetail.value = await getAgentDetailApi(id);
  } catch {
    agentDetail.value = null;
  }
  await loadConversations();
});

// ============ 对话列表 ============

interface ConversationItem {
  id: number;
  title: string | null;
  status: string;
  created_at: string;
}

const conversations = ref<ConversationItem[]>([]);
const conversationsLoading = ref(false);
const activeConversationId = ref<number | null>(null);

async function loadConversations() {
  if (!selectedAgentId.value) return;
  conversationsLoading.value = true;
  try {
    const res = await requestClient.get<{
      items: ConversationItem[];
      total: number;
    }>(`/tenant/ai/agent-chat/${selectedAgentId.value}/conversations`, {
      params: { 'page[size]': 50, sort: '-created_at' },
    });
    conversations.value = res.items;
  } catch {
    // handled by interceptor
  } finally {
    conversationsLoading.value = false;
  }
}

function selectAgent(agentId: number) {
  if (selectedAgentId.value === agentId) return;
  selectedAgentId.value = agentId;
  activeConversationId.value = null;
  chatMessages.value = [];
}

function startNewConversation() {
  activeConversationId.value = null;
  chatMessages.value = [];
}

/** 删除对话 */
function deleteConversation(conv: ConversationItem) {
  Modal.confirm({
    title: $t('tenant.ai.chat.confirmDelete'),
    onOk: async () => {
      try {
        await requestClient.delete(
          `/tenant/ai/agent-chat/${selectedAgentId.value}/conversations/${conv.id}`,
        );
        if (activeConversationId.value === conv.id) {
          activeConversationId.value = null;
          chatMessages.value = [];
        }
        await loadConversations();
      } catch {
        // handled by interceptor
      }
    },
  });
}

// ============ 聊天（SSE 流式 + Markdown） ============

interface ChatMessage {
  role: 'assistant' | 'user';
  content: string;
  streaming?: boolean;
  tokenUsage?: number;
  durationMs?: number;
}

const chatMessages = ref<ChatMessage[]>([]);
const inputMessage = ref('');
const sending = ref(false);
const streaming = ref(false);
const messagesContainer = ref<HTMLElement | null>(null);

let streamAbortController: AbortController | null = null;

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
    }
  });
}

/** 复制消息内容 */
async function copyMessage(content: string) {
  try {
    await navigator.clipboard.writeText(content);
    message.success($t('tenant.ai.chat.copySuccess'));
  } catch {
    message.error($t('common.requestFailed'));
  }
}

/** 点击建议问题 */
function askSuggested(question: string) {
  inputMessage.value = question;
  sendMessage();
}

/** 处理输入框键盘事件（跳过 IME 组合态的 Enter） */
function handleInputKeyDown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    sendMessage();
  }
}

function parseSSEEvents(
  rawChunk: string,
  buffer: { value: string },
  handler: (data: string) => void,
) {
  buffer.value += rawChunk;
  const lines = buffer.value.split('\n');
  buffer.value = lines.pop() ?? '';
  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith('data: ')) {
      handler(trimmed.slice(6));
    }
  }
}

async function sendMessage() {
  if (!inputMessage.value.trim() || !selectedAgentId.value || sending.value)
    return;

  const userMsg = inputMessage.value.trim();

  // 立即显示用户消息（视觉反馈）
  chatMessages.value.push({ role: 'user', content: userMsg });
  chatMessages.value.push({ role: 'assistant', content: '', streaming: true });
  scrollToBottom();

  // 先清空输入框并刷新 DOM，再设置 disabled —— 避免同批次更新导致清空失效
  inputMessage.value = '';
  await nextTick();

  sending.value = true;
  streaming.value = true;
  const sseBuffer = { value: '' };
  streamAbortController = new AbortController();
  const assistantIdx = chatMessages.value.length - 1;

  try {
    await requestClient.postSSE(
      `/tenant/ai/agent-chat/${selectedAgentId.value}/chat/stream`,
      {
        message: userMsg,
        conversation_id: activeConversationId.value,
      },
      {
        abortController: streamAbortController,
        onMessage(rawChunk: string) {
          parseSSEEvents(rawChunk, sseBuffer, (data) => {
            if (data === '[DONE]') return;
            try {
              const event = JSON.parse(data);
              const msg = chatMessages.value[assistantIdx];
              if (!msg) return;

              if (event.event === 'message' && event.delta) {
                msg.content += event.delta;
                scrollToBottom();
              } else if (event.event === 'done') {
                msg.tokenUsage = event.total_tokens || 0;
                msg.durationMs = event.duration_ms || 0;
                if (event.conversation_id) {
                  activeConversationId.value = event.conversation_id;
                }
              } else if (event.error) {
                msg.content =
                  '⚠️ ' + (event.message || $t('common.requestFailed'));
              }
            } catch {
              // 忽略无法解析的行
            }
          });
        },
        onEnd() {
          const msg = chatMessages.value[assistantIdx];
          if (msg) msg.streaming = false;
          loadConversations();
        },
        onError(error: Error) {
          if (error.name === 'AbortError') return;
          const msg = chatMessages.value[assistantIdx];
          if (msg) {
            if (!msg.content) msg.content = '⚠️ ' + $t('common.requestFailed');
            msg.streaming = false;
          }
        },
      },
    );
  } catch {
    // postSSE 内部已通过 onError 处理
  } finally {
    sending.value = false;
    streaming.value = false;
    streamAbortController = null;
    const msg = chatMessages.value[assistantIdx];
    if (msg) msg.streaming = false;
    scrollToBottom();
  }
}

function stopGeneration() {
  if (streamAbortController) {
    streamAbortController.abort();
    streamAbortController = null;
  }
  sending.value = false;
  streaming.value = false;
  const last = chatMessages.value.at(-1);
  if (last?.streaming) last.streaming = false;
}

async function loadConversationMessages(convId: number) {
  activeConversationId.value = convId;
  try {
    const res = await requestClient.get<{
      message_list: Array<{ role: string; content: string | null }>;
    }>(`/tenant/ai/agent-chat/${selectedAgentId.value}/conversations/${convId}`);

    chatMessages.value = (res.message_list ?? [])
      .filter((m) => m.role === 'user' || m.role === 'assistant')
      .map((m) => ({
        role: m.role as 'assistant' | 'user',
        content: m.content ?? '',
      }));
    scrollToBottom();
  } catch {
    // handled by interceptor
  }
}

/** 建议问题列表 */
const suggestedQuestions = computed<string[]>(() => {
  const raw = agentDetail.value?.suggested_questions;
  if (!Array.isArray(raw)) return [];
  return raw.filter((q): q is string => typeof q === 'string' && q.trim() !== '');
});

onMounted(loadAgents);

onUnmounted(() => {
  if (streamAbortController) {
    streamAbortController.abort();
  }
});
</script>

<template>
  <Page auto-content-height content-class="flex gap-4 h-full">
    <!-- 左侧面板: 智能体 + 对话历史 -->
    <Card class="w-72 shrink-0 overflow-y-auto" :body-style="{ padding: '12px' }">
      <!-- 智能体选择 -->
      <div class="mb-3 text-sm font-medium text-foreground">
        {{ $t('tenant.ai.chat.selectAgent') }}
      </div>

      <Spin :spinning="agentsLoading">
        <div v-if="agents.length === 0 && !agentsLoading" class="py-4 text-center text-sm text-muted-foreground">
          {{ $t('tenant.ai.chat.noAgents') }}
        </div>
        <div class="space-y-1.5">
          <div
            v-for="agent in agents"
            :key="agent.id"
            class="flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors"
            :class="selectedAgentId === agent.id ? 'bg-primary/10 text-primary' : 'hover:bg-accent text-foreground'"
            @click="selectAgent(agent.id)"
          >
            <IconifyIcon icon="lucide:bot" class="size-4 shrink-0" />
            <span class="truncate">{{ agent.name }}</span>
          </div>
        </div>
      </Spin>

      <!-- 分割线 -->
      <div class="my-3 border-t border-border" />

      <!-- 对话历史 -->
      <div class="mb-2 flex items-center justify-between">
        <span class="text-sm font-medium text-foreground">{{ $t('tenant.ai.chat.history') }}</span>
        <Button size="small" type="text" @click="startNewConversation">
          <template #icon><IconifyIcon icon="lucide:plus" class="size-3.5" /></template>
          {{ $t('tenant.ai.chat.newConversation') }}
        </Button>
      </div>

      <Spin :spinning="conversationsLoading">
        <div v-if="conversations.length === 0 && !conversationsLoading" class="py-4 text-center text-sm text-muted-foreground">
          {{ $t('tenant.ai.chat.noHistory') }}
        </div>
        <div class="space-y-1">
          <div
            v-for="conv in conversations"
            :key="conv.id"
            class="group flex cursor-pointer items-center justify-between rounded-md px-3 py-2 text-sm transition-colors"
            :class="activeConversationId === conv.id ? 'bg-accent text-foreground font-medium' : 'text-muted-foreground hover:bg-accent/50'"
            @click="loadConversationMessages(conv.id)"
          >
            <span class="truncate">{{ conv.title || `#${conv.id}` }}</span>
            <Tooltip :title="$t('tenant.ai.chat.deleteConversation')">
              <IconifyIcon
                icon="lucide:trash-2"
                class="size-3.5 shrink-0 text-muted-foreground opacity-0 transition-opacity hover:text-destructive group-hover:opacity-100"
                @click.stop="deleteConversation(conv)"
              />
            </Tooltip>
          </div>
        </div>
      </Spin>
    </Card>

    <!-- 右侧聊天区域 -->
    <Card class="flex flex-1 flex-col overflow-hidden" :body-style="{ padding: '0', display: 'flex', flexDirection: 'column', height: '100%' }">
      <!-- 顶部: 当前智能体信息 -->
      <div v-if="selectedAgent" class="flex items-center gap-3 border-b border-border px-4 py-3">
        <div class="flex size-8 items-center justify-center rounded-lg bg-primary/10">
          <IconifyIcon icon="lucide:bot" class="size-4 text-primary" />
        </div>
        <div>
          <div class="text-sm font-medium text-foreground">{{ selectedAgent.name }}</div>
          <div v-if="selectedAgent.description" class="max-w-md truncate text-xs text-muted-foreground">
            {{ selectedAgent.description }}
          </div>
        </div>
      </div>

      <!-- 消息列表 -->
      <div ref="messagesContainer" class="flex-1 overflow-y-auto px-4 py-4">
        <!-- 空状态: 欢迎消息 + 建议问题 -->
        <div v-if="chatMessages.length === 0 && !sending" class="flex h-full items-center justify-center">
          <div class="max-w-md text-center">
            <div class="mx-auto mb-4 flex size-14 items-center justify-center rounded-2xl bg-primary/10">
              <IconifyIcon icon="lucide:bot" class="size-7 text-primary" />
            </div>
            <div class="text-base font-medium text-foreground">
              {{ agentDetail?.welcome_message || $t('tenant.ai.chat.welcomeTitle') }}
            </div>
            <div v-if="!agentDetail?.welcome_message" class="mt-1 text-sm text-muted-foreground">
              {{ $t('tenant.ai.chat.welcomeDesc') }}
            </div>
            <!-- 建议问题 -->
            <div v-if="suggestedQuestions.length > 0" class="mt-5 flex flex-wrap justify-center gap-2">
              <Button
                v-for="(q, qi) in suggestedQuestions"
                :key="qi"
                size="small"
                class="max-w-[220px] truncate"
                @click="askSuggested(q)"
              >
                {{ q }}
              </Button>
            </div>
          </div>
        </div>

        <!-- 消息列表 -->
        <div class="space-y-4">
          <div
            v-for="(msg, idx) in chatMessages"
            :key="idx"
            class="flex gap-3"
            :class="msg.role === 'user' ? 'justify-end' : 'justify-start'"
          >
            <!-- 助手消息 -->
            <div v-if="msg.role === 'assistant'" class="group flex max-w-[80%] gap-2">
              <div class="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                <IconifyIcon icon="lucide:bot" class="size-3.5 text-primary" />
              </div>
              <div class="min-w-0">
                <!-- 思考中 -->
                <div v-if="msg.streaming && !msg.content" class="flex items-center gap-2 rounded-lg bg-accent px-3 py-2 text-sm text-muted-foreground">
                  <Spin size="small" />
                  <span>{{ $t('tenant.ai.chat.thinking') }}</span>
                </div>
                <!-- Markdown 内容 -->
                <div v-if="msg.content" class="rounded-lg border border-border bg-accent/30 px-4 py-2.5">
                  <MarkdownRender :content="msg.content" :streaming="!!msg.streaming" />
                  <span v-if="msg.streaming" class="streaming-cursor" />
                </div>
                <!-- 统计 + 复制 -->
                <div v-if="msg.content && !msg.streaming" class="mt-1 flex items-center gap-3 text-xs text-muted-foreground">
                  <span v-if="msg.tokenUsage">{{ msg.tokenUsage }} tokens</span>
                  <span v-if="msg.durationMs">{{ (msg.durationMs / 1000).toFixed(1) }}s</span>
                  <Tooltip :title="$t('tenant.ai.chat.copySuccess')">
                    <IconifyIcon
                      icon="lucide:copy"
                      class="size-3.5 cursor-pointer opacity-0 transition-opacity hover:text-foreground group-hover:opacity-100"
                      @click="copyMessage(msg.content)"
                    />
                  </Tooltip>
                </div>
              </div>
            </div>

            <!-- 用户消息 -->
            <div v-else class="max-w-[75%]">
              <div class="rounded-lg bg-primary px-3 py-2 text-sm text-primary-foreground whitespace-pre-wrap">
                {{ msg.content }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 输入区域 -->
      <div class="border-t border-border px-4 py-3">
        <!-- 停止按钮 -->
        <div v-if="streaming" class="mb-2 flex justify-center">
          <Button size="small" danger @click="stopGeneration">
            <template #icon>
              <IconifyIcon icon="lucide:square" class="size-3.5" />
            </template>
            {{ $t('tenant.ai.chat.stopGeneration') }}
          </Button>
        </div>
        <div class="flex gap-2">
          <Input.TextArea
            v-model:value="inputMessage"
            :placeholder="$t('tenant.ai.chat.inputPlaceholder')"
            :auto-size="{ minRows: 1, maxRows: 4 }"
            :disabled="!selectedAgentId || sending"
            class="flex-1"
            @keydown="handleInputKeyDown"
          />
          <Button
            type="primary"
            :disabled="!inputMessage.trim() || !selectedAgentId || sending"
            :loading="sending"
            @click="sendMessage"
          >
            <template #icon>
              <IconifyIcon icon="lucide:send" class="size-3.5" />
            </template>
          </Button>
        </div>
      </div>
    </Card>
  </Page>
</template>

<style scoped>
.streaming-cursor::after {
  content: '▍';
  display: inline;
  animation: blink 0.8s step-end infinite;
  color: hsl(var(--primary));
  font-weight: bold;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}
</style>
