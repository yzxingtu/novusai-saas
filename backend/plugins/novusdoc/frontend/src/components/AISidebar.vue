<script lang="ts" setup>
/**
 * AI 侧边对话面板
 *
 * 右侧面板，支持多轮对话。通过 useDocAI.aiChat() 调用。
 * 聊天气泡布局：用户右对齐，AI 左对齐+头像。
 */
import { ref, nextTick, watch } from 'vue';
import { Button, Input } from 'ant-design-vue';
import { IconifyIcon, $t } from '@novus/plugin-shared';

const props = defineProps<{
  loading: boolean;
  error?: string;
}>();

const emit = defineEmits<{
  send: [message: string, history: Array<{ role: string; content: string }>];
  action: [feature: string, extra?: Record<string, string>];
  close: [];
}>();

interface ChatMessage {
  role: 'user' | 'assistant' | 'error';
  content: string;
}

const messages = ref<ChatMessage[]>([]);
const inputText = ref('');
const chatContainer = ref<HTMLElement | null>(null);

function scrollToBottom() {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight;
    }
  });
}

function handleSend() {
  const text = inputText.value.trim();
  if (!text || props.loading) return;

  messages.value.push({ role: 'user', content: text });
  inputText.value = '';
  scrollToBottom();

  emit('send', text, messages.value.map(m => ({
    role: m.role === 'error' ? 'assistant' : m.role,
    content: m.content,
  })));
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    handleSend();
  }
}

function addAssistantMessage(content: string) {
  messages.value.push({ role: 'assistant', content });
  scrollToBottom();
}

function clearChat() {
  messages.value = [];
}

watch(() => props.error, (err) => {
  if (err) {
    messages.value.push({ role: 'error', content: err });
    scrollToBottom();
  }
});

defineExpose({ addAssistantMessage, clearChat });
</script>

<template>
  <div class="nd-ai-sidebar">
    <!-- Header -->
    <div class="nd-ai-sidebar-header">
      <div class="flex items-center gap-2">
        <div class="nd-ai-avatar-sm">
          <IconifyIcon icon="lucide:sparkles" class="size-3.5" />
        </div>
        <span class="font-semibold text-sm text-foreground">{{ $t('plugin.novusdoc.ai.assistant') }}</span>
      </div>
      <div class="flex items-center gap-1">
        <Button size="small" type="text" @click="clearChat" :title="$t('plugin.novusdoc.ai.clearChat')">
          <IconifyIcon icon="lucide:trash-2" class="size-3.5 text-muted-foreground" />
        </Button>
        <Button size="small" type="text" @click="emit('close')">
          <IconifyIcon icon="lucide:x" class="size-3.5 text-muted-foreground" />
        </Button>
      </div>
    </div>

    <!-- Messages -->
    <div ref="chatContainer" class="nd-ai-sidebar-messages">
      <!-- Empty state -->
      <div v-if="messages.length === 0 && !loading" class="nd-ai-sidebar-empty">
        <div class="nd-ai-empty-icon">
          <IconifyIcon icon="lucide:sparkles" class="size-8" />
        </div>
        <p class="text-sm font-medium text-foreground mt-3">{{ $t('plugin.novusdoc.ai.assistant') }}</p>
        <p class="text-xs text-muted-foreground mt-1 text-center leading-relaxed">{{ $t('plugin.novusdoc.ai.emptyChat') }}</p>
      </div>

      <!-- Chat messages -->
      <template v-for="(msg, idx) in messages" :key="idx">
        <!-- User message -->
        <div v-if="msg.role === 'user'" class="nd-ai-msg nd-ai-msg-user">
          <div class="nd-ai-bubble nd-ai-bubble-user">
            {{ msg.content }}
          </div>
        </div>

        <!-- AI message -->
        <div v-else-if="msg.role === 'assistant'" class="nd-ai-msg nd-ai-msg-ai">
          <div class="nd-ai-avatar-sm nd-ai-avatar-ai">
            <IconifyIcon icon="lucide:sparkles" class="size-3" />
          </div>
          <div class="nd-ai-bubble nd-ai-bubble-ai">
            {{ msg.content }}
          </div>
        </div>

        <!-- Error message -->
        <div v-else-if="msg.role === 'error'" class="nd-ai-msg nd-ai-msg-error">
          <div class="nd-ai-error-card">
            <IconifyIcon icon="lucide:alert-circle" class="size-4 shrink-0" />
            <span>{{ msg.content }}</span>
          </div>
        </div>
      </template>

      <!-- Loading indicator -->
      <div v-if="loading" class="nd-ai-msg nd-ai-msg-ai">
        <div class="nd-ai-avatar-sm nd-ai-avatar-ai">
          <IconifyIcon icon="lucide:sparkles" class="size-3" />
        </div>
        <div class="nd-ai-bubble nd-ai-bubble-ai">
          <span class="nd-ai-typing">
            <span class="nd-ai-dot"></span>
            <span class="nd-ai-dot"></span>
            <span class="nd-ai-dot"></span>
          </span>
        </div>
      </div>
    </div>

    <!-- Quick AI actions (全功能，不需要选中文字) -->
    <div class="nd-ai-sidebar-actions">
      <button class="nd-ai-quick-btn" @click="emit('action', 'continue')" :disabled="loading">
        <IconifyIcon icon="lucide:sparkles" class="size-3" />
        <span>{{ $t('plugin.novusdoc.ai.optimize') }}</span>
      </button>
      <button class="nd-ai-quick-btn" @click="emit('action', 'optimize')" :disabled="loading">
        <IconifyIcon icon="lucide:wand-2" class="size-3" />
        <span>{{ $t('plugin.novusdoc.ai.optimize') }}</span>
      </button>
      <button class="nd-ai-quick-btn" @click="emit('action', 'translate', { target_lang: 'English' })" :disabled="loading">
        <IconifyIcon icon="lucide:languages" class="size-3" />
        <span>{{ $t('plugin.novusdoc.ai.translate') }}</span>
      </button>
      <button class="nd-ai-quick-btn" @click="emit('action', 'expand')" :disabled="loading">
        <IconifyIcon icon="lucide:expand" class="size-3" />
        <span>{{ $t('plugin.novusdoc.ai.expand') }}</span>
      </button>
    </div>

    <!-- Input -->
    <div class="nd-ai-sidebar-input">
      <div class="nd-ai-input-wrapper">
        <Input
          v-model:value="inputText"
          :placeholder="$t('plugin.novusdoc.ai.askPlaceholder')"
          :disabled="loading"
          @keydown="handleKeydown"
          class="nd-ai-input"
        />
        <Button
          type="primary"
          size="small"
          :disabled="!inputText.trim() || loading"
          @click="handleSend"
          class="nd-ai-send-btn"
        >
          <IconifyIcon icon="lucide:send" class="size-3.5" />
        </Button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.nd-ai-sidebar {
  display: flex;
  flex-direction: column;
  width: 320px;
  min-width: 280px;
  max-width: 400px;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  border-left: 1px solid hsl(var(--border));
  background: hsl(var(--background));
}

.nd-ai-sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid hsl(var(--border));
}

.nd-ai-sidebar-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.nd-ai-sidebar-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px 16px;
  opacity: 0.7;
}

.nd-ai-empty-icon {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: hsl(var(--primary) / 0.1);
  color: hsl(var(--primary));
  display: flex;
  align-items: center;
  justify-content: center;
}

.nd-ai-avatar-sm {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: hsl(var(--primary) / 0.1);
  color: hsl(var(--primary));
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.nd-ai-avatar-ai {
  margin-top: 2px;
}

.nd-ai-msg {
  display: flex;
  gap: 8px;
  animation: nd-fade-in var(--nd-transition-normal, 200ms ease);
}

.nd-ai-msg-user {
  justify-content: flex-end;
}

.nd-ai-msg-ai {
  justify-content: flex-start;
  align-items: flex-start;
}

.nd-ai-msg-error {
  justify-content: center;
}

.nd-ai-bubble {
  max-width: 85%;
  padding: 8px 12px;
  border-radius: var(--nd-radius-md, 10px);
  font-size: 13px;
  line-height: 1.5;
  word-break: break-word;
  white-space: pre-wrap;
}

.nd-ai-bubble-user {
  background: hsl(var(--primary));
  color: hsl(var(--primary-foreground));
  border-bottom-right-radius: 4px;
}

.nd-ai-bubble-ai {
  background: hsl(var(--muted));
  color: hsl(var(--foreground));
  border-bottom-left-radius: 4px;
}

.nd-ai-error-card {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 12px;
  border-radius: var(--nd-radius-sm, 6px);
  background: hsl(var(--destructive) / 0.08);
  color: hsl(var(--destructive));
  font-size: 12px;
  line-height: 1.4;
  max-width: 90%;
}

/* Typing animation */
.nd-ai-typing {
  display: flex;
  gap: 4px;
  padding: 4px 0;
}

.nd-ai-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: hsl(var(--muted-foreground));
  animation: nd-typing 1.4s infinite ease-in-out;
}

.nd-ai-dot:nth-child(2) { animation-delay: 0.2s; }
.nd-ai-dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes nd-typing {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

@keyframes nd-fade-in {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Input area */
.nd-ai-sidebar-input {
  padding: 12px 16px;
  border-top: 1px solid hsl(var(--border));
}

.nd-ai-input-wrapper {
  display: flex;
  gap: 8px;
  align-items: center;
}

.nd-ai-input {
  flex: 1;
}

/* Quick AI actions */
.nd-ai-sidebar-actions {
  display: flex;
  gap: 6px;
  padding: 8px 16px;
  border-top: 1px solid hsl(var(--border));
  flex-wrap: wrap;
  flex-shrink: 0;
}

.nd-ai-quick-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 6px;
  border: 1px solid hsl(var(--border));
  background: hsl(var(--background));
  color: hsl(var(--foreground));
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}
.nd-ai-quick-btn:hover {
  background: hsl(var(--accent));
  border-color: hsl(var(--primary) / 0.3);
}
.nd-ai-quick-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.nd-ai-send-btn {
  flex-shrink: 0;
  border-radius: 50%;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
}
</style>
