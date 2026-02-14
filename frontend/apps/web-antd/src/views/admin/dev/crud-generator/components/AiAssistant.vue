<script setup lang="ts">
import { onMounted } from 'vue';

import { Button, Drawer, Empty, Input, Spin, Tag, Tooltip } from 'ant-design-vue';

import { MarkdownRender } from '#/components/business/markdown-render';
import { $t } from '#/locales';

import type { UseCrudAiAssistantReturn } from '../composables/use-crud-ai-assistant';

const props = defineProps<{
  assistant: UseCrudAiAssistantReturn;
}>();

const T = 'admin.dev.crudGenerator.aiAssistant';

const {
  drawerOpen,
  close,
  agentReady,
  agentError,
  chatMessages,
  inputMessage,
  sending,
  streaming,
  sendMessage,
  stopGeneration,
  handleInputKeyDown,
  handleMessagesScroll,
  startNewConversation,
  sendQuickAction,
} = props.assistant;

onMounted(() => {
  // Drawer content is lazy — agent loads on open()
});
</script>

<template>
  <Drawer
    :closable="true"
    :mask-closable="true"
    :open="drawerOpen"
    :title="$t(`${T}.title`)"
    :width="480"
    placement="right"
    @close="close"
  >
    <template #extra>
      <Tooltip :title="$t(`${T}.newChat`)">
        <Button size="small" type="text" @click="startNewConversation">
          <template #icon>
            <span class="icon-[lucide--message-square-plus] size-4" />
          </template>
        </Button>
      </Tooltip>
    </template>

    <div class="flex h-full flex-col">
      <!-- Agent error -->
      <div v-if="agentError" class="flex-1">
        <Empty :description="$t(`${T}.agentNotFound`)" class="py-20">
          <template #image>
            <span class="icon-[lucide--bot-off] mx-auto block size-12 opacity-20" />
          </template>
        </Empty>
      </div>

      <!-- Agent loading -->
      <div v-else-if="!agentReady" class="flex flex-1 items-center justify-center">
        <Spin />
      </div>

      <!-- Chat area -->
      <template v-else>
        <!-- Messages -->
        <div
          ref="messagesContainer"
          class="flex-1 overflow-auto pb-4"
          @scroll="handleMessagesScroll"
        >
          <!-- Empty state -->
          <div v-if="chatMessages.length === 0" class="px-4 py-8">
            <div class="text-muted-foreground text-center text-sm">
              <span class="icon-[lucide--sparkles] mb-2 block size-8 opacity-30 mx-auto" />
              <p>{{ $t(`${T}.intentHint`) }}</p>
            </div>

            <!-- Quick actions -->
            <div class="mt-6">
              <p class="text-muted-foreground mb-2 text-xs font-medium">
                {{ $t(`${T}.quickActions`) }}
              </p>
              <div class="flex flex-wrap gap-2">
                <Button
                  size="small"
                  @click="sendQuickAction($t(`${T}.suggestFields`))"
                >
                  <template #icon>
                    <span class="icon-[lucide--list-plus] size-3.5" />
                  </template>
                  {{ $t(`${T}.suggestFields`) }}
                </Button>
                <Button
                  size="small"
                  @click="sendQuickAction($t(`${T}.translateLabels`))"
                >
                  <template #icon>
                    <span class="icon-[lucide--languages] size-3.5" />
                  </template>
                  {{ $t(`${T}.translateLabels`) }}
                </Button>
                <Button
                  size="small"
                  @click="sendQuickAction($t(`${T}.analyzeIntent`))"
                >
                  <template #icon>
                    <span class="icon-[lucide--brain] size-3.5" />
                  </template>
                  {{ $t(`${T}.analyzeIntent`) }}
                </Button>
              </div>
            </div>
          </div>

          <!-- Message list -->
          <div v-else class="space-y-3 px-2">
            <div
              v-for="(msg, idx) in chatMessages"
              :key="idx"
              :class="[
                'flex',
                msg.role === 'user' ? 'justify-end' : 'justify-start',
              ]"
            >
              <!-- User message -->
              <div
                v-if="msg.role === 'user'"
                class="bg-primary/10 max-w-[85%] rounded-xl px-3 py-2 text-sm"
              >
                {{ msg.content }}
              </div>

              <!-- Assistant message -->
              <div v-else class="max-w-[90%]">
                <!-- Tool calls -->
                <div v-if="msg.toolCalls && msg.toolCalls.length > 0" class="mb-2 space-y-1">
                  <div
                    v-for="(tc, tcIdx) in msg.toolCalls"
                    :key="tcIdx"
                    class="flex items-center gap-1.5 text-xs"
                  >
                    <Spin v-if="tc.status === 'running'" size="small" />
                    <span
                      v-else-if="tc.status === 'success'"
                      class="icon-[lucide--check-circle] size-3.5 text-green-500"
                    />
                    <span
                      v-else
                      class="icon-[lucide--x-circle] size-3.5 text-red-500"
                    />
                    <Tag :color="tc.status === 'running' ? 'processing' : tc.status === 'success' ? 'success' : 'error'" class="m-0">
                      {{ tc.name }}
                    </Tag>
                    <span v-if="tc.durationMs" class="text-muted-foreground">
                      {{ tc.durationMs }}ms
                    </span>
                  </div>
                </div>

                <!-- Content -->
                <div v-if="msg.content" class="bg-accent/50 rounded-xl px-3 py-2 text-sm">
                  <MarkdownRender :content="msg.content" />
                </div>

                <!-- Streaming indicator -->
                <div v-if="msg.streaming && !msg.content" class="text-muted-foreground flex items-center gap-2 px-3 py-2 text-sm">
                  <Spin size="small" />
                  {{ $t(`${T}.thinking`) }}
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Input area -->
        <div class="border-t p-3">
          <div class="flex items-end gap-2">
            <Input.TextArea
              v-model:value="inputMessage"
              :auto-size="{ minRows: 1, maxRows: 4 }"
              :disabled="sending"
              :placeholder="$t(`${T}.placeholder`)"
              @keydown="handleInputKeyDown"
            />
            <Button
              v-if="streaming"
              danger
              size="small"
              type="primary"
              @click="stopGeneration"
            >
              <template #icon>
                <span class="icon-[lucide--square] size-3.5" />
              </template>
            </Button>
            <Button
              v-else
              :disabled="!inputMessage.trim() || sending"
              size="small"
              type="primary"
              @click="sendMessage"
            >
              <template #icon>
                <span class="icon-[lucide--send] size-3.5" />
              </template>
            </Button>
          </div>
        </div>
      </template>
    </div>
  </Drawer>
</template>
