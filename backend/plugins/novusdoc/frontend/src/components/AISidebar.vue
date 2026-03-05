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
  <div class="flex h-full min-h-0 w-80 min-w-[280px] max-w-[400px] flex-col overflow-hidden border-l border-border bg-background max-lg:w-[280px] max-lg:min-w-[240px] max-md:fixed max-md:inset-y-0 max-md:right-0 max-md:z-[100] max-md:w-full max-md:max-w-full max-md:shadow-lg">
    <!-- Header -->
    <div class="flex items-center justify-between border-b border-border px-4 py-3">
      <div class="flex items-center gap-2">
        <div class="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
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
    <div ref="chatContainer" class="flex flex-1 flex-col gap-3 overflow-y-auto p-4">
      <!-- Empty state -->
      <div v-if="messages.length === 0 && !loading" class="flex flex-1 flex-col items-center justify-center px-4 py-8 opacity-70">
        <div class="flex size-12 items-center justify-center rounded-full bg-primary/10 text-primary">
          <IconifyIcon icon="lucide:sparkles" class="size-8" />
        </div>
        <p class="text-sm font-medium text-foreground mt-3">{{ $t('plugin.novusdoc.ai.assistant') }}</p>
        <p class="text-xs text-muted-foreground mt-1 text-center leading-relaxed">{{ $t('plugin.novusdoc.ai.emptyChat') }}</p>
      </div>

      <!-- Chat messages -->
      <template v-for="(msg, idx) in messages" :key="idx">
        <!-- User message -->
        <div v-if="msg.role === 'user'" class="nd-ai-msg flex justify-end gap-2">
          <div class="max-w-[85%] whitespace-pre-wrap break-words rounded-[10px] rounded-br-[4px] bg-primary px-3 py-2 text-[13px] leading-normal text-primary-foreground">
            {{ msg.content }}
          </div>
        </div>

        <!-- AI message -->
        <div v-else-if="msg.role === 'assistant'" class="nd-ai-msg flex items-start justify-start gap-2">
          <div class="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
            <IconifyIcon icon="lucide:sparkles" class="size-3" />
          </div>
          <div class="max-w-[85%] whitespace-pre-wrap break-words rounded-[10px] rounded-bl-[4px] bg-muted px-3 py-2 text-[13px] leading-normal text-foreground">
            {{ msg.content }}
          </div>
        </div>

        <!-- Error message -->
        <div v-else-if="msg.role === 'error'" class="nd-ai-msg flex justify-center gap-2">
          <div class="flex max-w-[90%] items-start gap-2 rounded-md bg-destructive/[0.08] px-3 py-2 text-xs leading-snug text-destructive">
            <IconifyIcon icon="lucide:alert-circle" class="size-4 shrink-0" />
            <span>{{ msg.content }}</span>
          </div>
        </div>
      </template>

      <!-- Loading indicator -->
      <div v-if="loading" class="nd-ai-msg flex items-start justify-start gap-2">
        <div class="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
          <IconifyIcon icon="lucide:sparkles" class="size-3" />
        </div>
        <div class="max-w-[85%] whitespace-pre-wrap break-words rounded-[10px] rounded-bl-[4px] bg-muted px-3 py-2 text-[13px] leading-normal text-foreground">
          <span class="flex gap-1 py-1">
            <span class="nd-ai-dot size-1.5 rounded-full bg-muted-foreground"></span>
            <span class="nd-ai-dot size-1.5 rounded-full bg-muted-foreground"></span>
            <span class="nd-ai-dot size-1.5 rounded-full bg-muted-foreground"></span>
          </span>
        </div>
      </div>
    </div>

    <!-- Quick AI actions (全功能，不需要选中文字) -->
    <div class="flex shrink-0 flex-wrap gap-1.5 border-t border-border px-4 py-2">
      <button class="flex cursor-pointer items-center gap-1 rounded-md border border-border bg-background px-2.5 py-1 text-xs text-foreground transition-all hover:border-primary/30 hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50" @click="emit('action', 'continue')" :disabled="loading">
        <IconifyIcon icon="lucide:pen-line" class="size-3" />
        <span>{{ $t('plugin.novusdoc.ai.continue') }}</span>
      </button>
      <button class="flex cursor-pointer items-center gap-1 rounded-md border border-border bg-background px-2.5 py-1 text-xs text-foreground transition-all hover:border-primary/30 hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50" @click="emit('action', 'optimize')" :disabled="loading">
        <IconifyIcon icon="lucide:wand-2" class="size-3" />
        <span>{{ $t('plugin.novusdoc.ai.optimize') }}</span>
      </button>
      <button class="flex cursor-pointer items-center gap-1 rounded-md border border-border bg-background px-2.5 py-1 text-xs text-foreground transition-all hover:border-primary/30 hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50" @click="emit('action', 'translate', { target_lang: 'English' })" :disabled="loading">
        <IconifyIcon icon="lucide:languages" class="size-3" />
        <span>{{ $t('plugin.novusdoc.ai.translate') }}</span>
      </button>
      <button class="flex cursor-pointer items-center gap-1 rounded-md border border-border bg-background px-2.5 py-1 text-xs text-foreground transition-all hover:border-primary/30 hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50" @click="emit('action', 'expand')" :disabled="loading">
        <IconifyIcon icon="lucide:expand" class="size-3" />
        <span>{{ $t('plugin.novusdoc.ai.expand') }}</span>
      </button>
    </div>

    <!-- Input -->
    <div class="border-t border-border px-4 py-3">
      <div class="flex items-center gap-2">
        <Input
          v-model:value="inputText"
          :placeholder="$t('plugin.novusdoc.ai.askPlaceholder')"
          :disabled="loading"
          @keydown="handleKeydown"
          class="flex-1"
        />
        <Button
          type="primary"
          size="small"
          :disabled="!inputText.trim() || loading"
          @click="handleSend"
          class="flex size-8 shrink-0 items-center justify-center rounded-full p-0"
        >
          <IconifyIcon icon="lucide:send" class="size-3.5" />
        </Button>
      </div>
    </div>
  </div>
</template>
