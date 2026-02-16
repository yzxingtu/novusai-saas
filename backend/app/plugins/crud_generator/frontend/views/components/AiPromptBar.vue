<script setup lang="ts">
/**
 * AiPromptBar — Inline AI input bar for CRUD Generator
 *
 * Sends prompts to the CRUD Generator Agent via SSE streaming.
 * Tool calls with __crud_form_fill__ are handled by useCrudFormBridge.
 */
import { nextTick, ref } from 'vue';

import { Button, Input, Spin, Tag } from 'ant-design-vue';

import { $t } from '#/locales';
import { requestClient } from '#/utils/request';

const T = 'admin.dev.crudGenerator.aiPrompt';

const props = defineProps<{
  agentId: number;
  collapsed: boolean;
}>();

const emit = defineEmits<{
  'update:collapsed': [value: boolean];
  toolCall: [toolName: string, output: string];
}>();

const inputText = ref('');
const thinking = ref(false);
const statusMessage = ref('');
const conversationId = ref<string | null>(null);

let abortController: AbortController | null = null;

const presetTags = [
  { key: 'order', labelKey: 'presetOrder' },
  { key: 'content', labelKey: 'presetContent' },
  { key: 'user', labelKey: 'presetUser' },
  { key: 'config', labelKey: 'presetConfig' },
];

function onPresetClick(key: string) {
  inputText.value = $t(`${T}.${key}Prompt`);
  nextTick(() => send());
}

function onKeyDown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    send();
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

async function send() {
  const text = inputText.value.trim();
  if (!text || thinking.value || !props.agentId) return;

  inputText.value = '';
  thinking.value = true;
  statusMessage.value = $t(`${T}.thinking`);

  abortController = new AbortController();
  const sseBuffer = { value: '' };
  let resultContent = '';

  try {
    await requestClient.postSSE(
      `/admin/ai/agent-chat/${props.agentId}/chat/stream`,
      {
        message: text,
        conversation_id: conversationId.value,
      },
      {
        abortController,
        onMessage(rawChunk: string) {
          parseSSEEvents(rawChunk, sseBuffer, (data) => {
            if (data === '[DONE]') return;
            try {
              const event = JSON.parse(data);

              if (event.event === 'tool_call' && event.success) {
                emit('toolCall', event.name, event.output ?? '');
              } else if (event.event === 'message' && event.delta) {
                resultContent += event.delta;
              } else if (event.event === 'done') {
                if (event.conversation_id) {
                  conversationId.value = event.conversation_id;
                }
              }
            } catch {
              // ignore
            }
          });
        },
        onEnd() {
          thinking.value = false;
          if (resultContent) {
            statusMessage.value = resultContent.slice(0, 120);
          } else {
            statusMessage.value = '';
          }
        },
      },
    );
  } catch {
    thinking.value = false;
    statusMessage.value = $t(`${T}.error`);
  }
}

function abort() {
  abortController?.abort();
  thinking.value = false;
  statusMessage.value = '';
}
</script>

<template>
  <div
    class="border-border bg-card/50 border-b transition-all duration-150"
    :class="{ 'py-0': collapsed, 'px-4 py-2': !collapsed }"
  >
    <!-- Collapsed toggle -->
    <div
      v-if="collapsed"
      class="flex cursor-pointer items-center gap-2 px-4 py-1"
      @click="emit('update:collapsed', false)"
    >
      <span class="icon-[lucide--sparkles] text-primary size-3.5" />
      <span class="text-muted-foreground text-xs">
        {{ $t(`${T}.expand`) }}
      </span>
    </div>

    <!-- Expanded content -->
    <template v-else>
      <div class="flex items-center gap-2">
        <span class="icon-[lucide--sparkles] text-primary size-4 shrink-0" />

        <Input
          v-model:value="inputText"
          :placeholder="$t(`${T}.placeholder`)"
          :disabled="thinking"
          class="flex-1"
          size="small"
          @keydown="onKeyDown"
        />

        <Button
          v-if="thinking"
          size="small"
          danger
          @click="abort"
        >
          <template #icon>
            <span class="icon-[lucide--square] size-3.5" />
          </template>
        </Button>
        <Button
          v-else
          type="primary"
          size="small"
          :disabled="!inputText.trim()"
          @click="send"
        >
          <template #icon>
            <span class="icon-[lucide--send] size-3.5" />
          </template>
        </Button>

        <Button
          type="text"
          size="small"
          @click="emit('update:collapsed', true)"
        >
          <template #icon>
            <span class="icon-[lucide--chevron-up] size-3.5" />
          </template>
        </Button>
      </div>

      <!-- Preset tags -->
      <div class="mt-1.5 flex flex-wrap items-center gap-1">
        <span class="text-muted-foreground mr-1 text-xs">
          <span class="icon-[lucide--lightbulb] mr-0.5 inline-block size-3" />
        </span>
        <Tag
          v-for="tag in presetTags"
          :key="tag.key"
          class="cursor-pointer"
          color="blue"
          @click="onPresetClick(tag.key)"
        >
          {{ $t(`${T}.${tag.labelKey}`) }}
        </Tag>
      </div>

      <!-- Status line -->
      <div
        v-if="thinking || statusMessage"
        class="text-muted-foreground mt-1.5 flex items-center gap-1.5 text-xs"
      >
        <Spin v-if="thinking" size="small" />
        <span
          v-else
          class="icon-[lucide--check-circle] text-success size-3.5"
        />
        <span class="line-clamp-1">{{ statusMessage }}</span>
      </div>
    </template>
  </div>
</template>
