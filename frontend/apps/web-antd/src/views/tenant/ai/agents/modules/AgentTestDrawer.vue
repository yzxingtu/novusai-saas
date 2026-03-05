<script setup lang="ts">
/**
 * 智能体测试对话抽屉
 *
 * 功能：SSE 流式对话、消息列表、工具调用展示、停止生成
 */
import { computed, nextTick, ref } from 'vue';

import { useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Collapse,
  CollapsePanel,
  Input,
  message,
  Spin,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import { MarkdownRender } from '#/components/business/markdown-render';
import { $t } from '#/locales';
import { requestClient } from '#/utils/request';

defineOptions({ name: 'AgentTestDrawer' });

/** 聊天消息 */
interface ChatMessage {
  id: string;
  role: 'assistant' | 'user';
  content: string;
  conversationId?: number;
  durationMs?: number;
  streaming?: boolean;
  tokenUsage?: number;
  toolCalls?: { name: string; success: boolean }[];
}

const agentId = ref(0);
const agentName = ref('');
const agentStatus = ref('');
const messages = ref<ChatMessage[]>([]);
const inputText = ref('');
const streaming = ref(false);
const conversationId = ref<null | number>(null);
const abortController = ref<AbortController | null>(null);

const messageListRef = ref<HTMLElement>();

const isPublished = computed(() => agentStatus.value === 'published');

const [Drawer, drawerApi] = useVbenDrawer({
  onOpenChange: (isOpen) => {
    if (isOpen) {
      const data = drawerApi.getData<{
        id: number;
        name: string;
        status: string;
      }>();
      if (data) {
        // 切换智能体时重置对话
        if (data.id !== agentId.value) {
          messages.value = [];
          conversationId.value = null;
        }
        agentId.value = data.id;
        agentName.value = data.name;
        agentStatus.value = data.status;
      }
    } else {
      onStop();
    }
  },
});

const title = computed(
  () => `${$t('tenant.ai.agent.test.title')} - ${agentName.value}`,
);

function genMsgId(): string {
  return `msg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

async function scrollToBottom() {
  await nextTick();
  if (messageListRef.value) {
    messageListRef.value.scrollTop = messageListRef.value.scrollHeight;
  }
}

/** SSE 文本缓冲区 */
let sseBuffer = '';

/** 解析 SSE 缓冲区，返回完整事件列表 */
function flushSseBuffer(raw: string): Record<string, unknown>[] {
  sseBuffer += raw;
  const parts = sseBuffer.split('\n\n');
  sseBuffer = parts.pop() || '';

  const events: Record<string, unknown>[] = [];
  for (const part of parts) {
    const line = part.trim();
    if (!line.startsWith('data:')) continue;
    const payload = line.slice(5).trim();
    if (payload === '[DONE]') continue;
    try {
      events.push(JSON.parse(payload));
    } catch {
      // skip malformed
    }
  }
  return events;
}

/** 发送消息 */
async function onSend() {
  const text = inputText.value.trim();
  if (!text || streaming.value) return;

  if (!isPublished.value) {
    message.warning($t('tenant.ai.agent.test.notPublished'));
    return;
  }

  // 用户消息
  messages.value.push({ id: genMsgId(), role: 'user', content: text });
  inputText.value = '';
  await scrollToBottom();

  // 助手占位
  messages.value.push({
    id: genMsgId(),
    role: 'assistant',
    content: '',
    toolCalls: [],
    streaming: true,
  });
  const assistantIdx = messages.value.length - 1;

  // SSE 流式请求
  streaming.value = true;
  sseBuffer = '';
  const ctrl = new AbortController();
  abortController.value = ctrl;

  try {
    await requestClient.postSSE(
      `/tenant/ai/agent-chat/${agentId.value}/chat/stream`,
      { message: text, conversation_id: conversationId.value },
      {
        abortController: ctrl,
        onMessage: (chunk: string) => {
          const evts = flushSseBuffer(chunk);
          const msg = messages.value[assistantIdx];
          if (!msg) return;

          for (const evt of evts) {
            if (evt.error) {
              msg.content += `\n\n**Error:** ${evt.message}`;
              continue;
            }
            switch (evt.event) {
              case 'done': {
                msg.tokenUsage = (evt.total_tokens as number) || 0;
                msg.durationMs = (evt.duration_ms as number) || 0;
                if (evt.conversation_id) {
                  conversationId.value = evt.conversation_id as number;
                }
                break;
              }
              case 'message': {
                msg.content += (evt.delta as string) || '';
                break;
              }
              case 'tool_call': {
                if (!msg.toolCalls) msg.toolCalls = [];
                msg.toolCalls.push({
                  name: evt.name as string,
                  success: evt.success as boolean,
                });
                break;
              }
            }
          }
          scrollToBottom();
        },
        onEnd: () => {
          const msg = messages.value[assistantIdx];
          if (msg) msg.streaming = false;
          streaming.value = false;
          abortController.value = null;
          scrollToBottom();
        },
        onError: (err: Error) => {
          if (err.name === 'AbortError') return;
          const msg = messages.value[assistantIdx];
          if (msg) {
            msg.content += `\n\n**${$t('tenant.ai.agent.test.streamError')}**`;
            msg.streaming = false;
          }
          streaming.value = false;
          abortController.value = null;
        },
      },
    );
  } catch (error: unknown) {
    if (error instanceof Error && error.name === 'AbortError') return;
    const msg = messages.value[assistantIdx];
    if (msg) {
      msg.content += `\n\n**${$t('tenant.ai.agent.test.streamError')}**`;
      msg.streaming = false;
    }
    streaming.value = false;
    abortController.value = null;
  }
}

/** 停止生成 */
function onStop() {
  if (abortController.value) {
    abortController.value.abort();
    abortController.value = null;
  }
  streaming.value = false;
  const last = messages.value.at(-1);
  if (last?.streaming) last.streaming = false;
}

/** 清空对话 */
function onClear() {
  onStop();
  messages.value = [];
  conversationId.value = null;
}

/** 回车发送（Shift+Enter 换行） */
function onKeyDown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    onSend();
  }
}
</script>

<template>
  <Drawer :title="title" class="w-[700px]">
    <div class="flex h-[calc(100vh-120px)] flex-col">
      <!-- 顶部操作栏 -->
      <div
        class="flex items-center justify-between border-b border-border pb-3"
      >
        <div class="flex items-center gap-2 text-sm text-muted-foreground">
          <Tag v-if="conversationId" color="processing">
            {{
              $t('tenant.ai.agent.test.conversationId', {
                id: conversationId,
              })
            }}
          </Tag>
        </div>
        <Button
          size="small"
          :disabled="streaming || messages.length === 0"
          @click="onClear"
        >
          <template #icon>
            <IconifyIcon icon="lucide:trash-2" />
          </template>
          {{ $t('tenant.ai.agent.test.clear') }}
        </Button>
      </div>

      <!-- 消息列表 -->
      <div ref="messageListRef" class="min-h-0 flex-1 overflow-y-auto py-3">
        <!-- 空状态 -->
        <div
          v-if="messages.length === 0"
          class="flex h-full items-center justify-center text-muted-foreground"
        >
          <div class="text-center">
            <IconifyIcon
              icon="lucide:message-circle"
              class="mx-auto mb-2 size-12 opacity-30"
            />
            <p>{{ $t('tenant.ai.agent.test.placeholder') }}</p>
          </div>
        </div>

        <!-- 消息 -->
        <div
          v-for="msg in messages"
          :key="msg.id"
          class="mb-4"
          :class="
            msg.role === 'user' ? 'flex justify-end' : 'flex justify-start'
          "
        >
          <!-- 用户消息 -->
          <div
            v-if="msg.role === 'user'"
            class="max-w-[80%] rounded-lg bg-primary/10 px-4 py-2.5"
          >
            <div class="whitespace-pre-wrap text-sm">{{ msg.content }}</div>
          </div>

          <!-- 助手消息 -->
          <div v-else class="max-w-[85%]">
            <!-- 工具调用 -->
            <Collapse
              v-if="msg.toolCalls && msg.toolCalls.length > 0"
              class="mb-2"
              size="small"
            >
              <CollapsePanel
                v-for="(tc, idx) in msg.toolCalls"
                :key="idx"
                :header="
                  $t('tenant.ai.agent.test.toolCalling', { name: tc.name })
                "
              >
                <Tag :color="tc.success ? 'success' : 'error'">
                  {{
                    tc.success
                      ? $t('tenant.ai.agent.test.toolSuccess')
                      : $t('tenant.ai.agent.test.toolFailed')
                  }}
                </Tag>
              </CollapsePanel>
            </Collapse>

            <!-- 思考中 -->
            <div
              v-if="msg.streaming && !msg.content"
              class="flex items-center gap-2 text-sm text-muted-foreground"
            >
              <Spin size="small" />
              <span>{{ $t('tenant.ai.agent.test.thinking') }}</span>
            </div>

            <!-- Markdown 内容 -->
            <div
              v-if="msg.content"
              class="rounded-lg border border-border bg-accent/20 px-4 py-2.5"
            >
              <MarkdownRender
                :content="msg.content"
                :streaming="msg.streaming"
              />
            </div>

            <!-- 统计信息 -->
            <div
              v-if="!msg.streaming && (msg.tokenUsage || msg.durationMs)"
              class="mt-1 flex gap-3 text-xs text-muted-foreground"
            >
              <span v-if="msg.tokenUsage">
                {{
                  $t('tenant.ai.agent.test.tokenUsage', {
                    count: msg.tokenUsage,
                  })
                }}
              </span>
              <span v-if="msg.durationMs">
                {{
                  $t('tenant.ai.agent.test.duration', { ms: msg.durationMs })
                }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- 输入区 -->
      <div class="border-t border-border pt-3">
        <!-- 停止按钮 -->
        <div v-if="streaming" class="mb-2 flex justify-center">
          <Button size="small" danger @click="onStop">
            <template #icon>
              <IconifyIcon icon="lucide:square" />
            </template>
            {{ $t('tenant.ai.agent.test.stop') }}
          </Button>
        </div>

        <div class="flex gap-2">
          <Input.TextArea
            v-model:value="inputText"
            :placeholder="$t('tenant.ai.agent.test.placeholder')"
            :auto-size="{ minRows: 1, maxRows: 4 }"
            :disabled="streaming || !isPublished"
            @keydown="onKeyDown"
          />
          <Tooltip
            :title="
              isPublished ? undefined : $t('tenant.ai.agent.test.notPublished')
            "
          >
            <Button
              type="primary"
              :disabled="!inputText.trim() || streaming || !isPublished"
              @click="onSend"
            >
              <template #icon>
                <IconifyIcon icon="lucide:send" />
              </template>
            </Button>
          </Tooltip>
        </div>
      </div>
    </div>
  </Drawer>
</template>
