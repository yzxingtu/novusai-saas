<script lang="ts" setup>
import type { AIAgentInfo, AIAgentKBBindingInfo } from '#/api/admin/ai-agents';
import type { AgentKnowledgeBaseBindingDraftItem } from '#/components/business/agent-kb-binding-picker';

import { computed, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  Alert,
  Button,
  InputNumber,
  message,
  Popconfirm,
  Spin,
  Switch,
  Tag,
} from 'ant-design-vue';

import {
  batchBindAIAgentKBsApi,
  getAIAgentKBsApi,
  unbindAIAgentKBApi,
  updateAIAgentKBBindingApi,
} from '#/api/admin/ai-agents';
import { getAdminSelectableKBApi } from '#/api/admin/knowledge-bases';
import {
  AgentKnowledgeBaseBindingPicker,
  bindingsToDrafts as kbBindingsToDrafts,
  draftsToBatchPayload as kbDraftsToBatchPayload,
} from '#/components/business/agent-kb-binding-picker';
import { $t } from '#/locales';
import { showRequestError } from '#/utils/error-helpers';

const props = defineProps<{
  active: boolean;
  agent: AIAgentInfo;
  agentId: number;
}>();

const kbBindings = ref<AIAgentKBBindingInfo[]>([]);
const kbBindingsLoading = ref(false);
const kbPickerOpen = ref(false);
const kbPickerDrafts = ref<AgentKnowledgeBaseBindingDraftItem[]>([]);
const kbBindingScopeCount = computed(() => {
  const keys = new Set(
    kbBindings.value.map((binding) => binding.kb_scope || 'unknown'),
  );
  return keys.size;
});

async function loadKBBindings() {
  kbBindingsLoading.value = true;
  try {
    kbBindings.value = await getAIAgentKBsApi(props.agentId);
  } catch (error) {
    kbBindings.value = [];
    showRequestError(error, 'common.loadFailed');
  } finally {
    kbBindingsLoading.value = false;
  }
}

function getKbChunkStrategyText(strategy: null | string | undefined): string {
  switch (strategy) {
    case 'paragraph': {
      return $t('tenant.knowledgeBase.field.chunkStrategyParagraph');
    }
    case 'recursive': {
      return $t('tenant.knowledgeBase.field.chunkStrategyRecursive');
    }
    case 'semantic': {
      return $t('tenant.knowledgeBase.field.chunkStrategySemantic');
    }
    case 'sentence': {
      return $t('tenant.knowledgeBase.field.chunkStrategySentence');
    }
    default: {
      return strategy || '-';
    }
  }
}

function getKbOwnerText(binding: AIAgentKBBindingInfo): string {
  if (
    binding.kb_owner_tenant_id === null ||
    binding.kb_owner_tenant_id === undefined
  ) {
    return $t('admin.ai.agent.detail.kbOwnerPlatform');
  }
  return binding.kb_owner_tenant_name || `#${binding.kb_owner_tenant_id}`;
}

function openKBBindingPicker() {
  kbPickerDrafts.value = kbBindingsToDrafts(kbBindings.value);
  kbPickerOpen.value = true;
}

async function onKBBindingPickerConfirm(
  drafts: AgentKnowledgeBaseBindingDraftItem[],
) {
  try {
    await batchBindAIAgentKBsApi(props.agentId, kbDraftsToBatchPayload(drafts));
    message.success($t('admin.ai.agent.detail.saveSuccess'));
    await loadKBBindings();
  } catch (error) {
    showRequestError(error, 'common.saveFailed');
  }
}

async function unbindKB(knowledgeBaseId: number) {
  try {
    await unbindAIAgentKBApi(props.agentId, knowledgeBaseId);
    await loadKBBindings();
    message.success($t('admin.ai.agent.detail.saveSuccess'));
  } catch (error) {
    showRequestError(error, 'common.saveFailed');
  }
}

async function toggleKBEnabled(binding: AIAgentKBBindingInfo) {
  try {
    await updateAIAgentKBBindingApi(props.agentId, binding.id, {
      enabled: !binding.enabled,
    });
    await loadKBBindings();
  } catch (error) {
    showRequestError(error, 'common.saveFailed');
  }
}

async function updateKBWeight(bindingId: number, weight: number) {
  try {
    await updateAIAgentKBBindingApi(props.agentId, bindingId, { weight });
    await loadKBBindings();
    message.success($t('admin.ai.agent.detail.saveSuccess'));
  } catch (error) {
    showRequestError(error, 'common.saveFailed');
  }
}

watch(
  () => props.active,
  (active) => {
    if (active) {
      void loadKBBindings();
    }
  },
  { immediate: true },
);

watch(
  () => props.agentId,
  () => {
    if (props.active) {
      void loadKBBindings();
    }
  },
);
</script>

<template>
  <div class="p-5 pt-3">
    <AgentKnowledgeBaseBindingPicker
      v-model:open="kbPickerOpen"
      v-model="kbPickerDrafts"
      :fetch-candidates="() => getAdminSelectableKBApi({ agent_id: agentId })"
      @confirm="onKBBindingPickerConfirm"
    />
    <Spin :spinning="kbBindingsLoading">
      <div class="flex flex-col gap-4">
        <Alert
          v-if="agent.owner_type === 'platform'"
          type="info"
          show-icon
          class="text-sm"
          :message="$t('admin.ai.agent.detail.knowledgeBasesGlobalHint')"
        />
        <div class="rounded-2xl border border-border/70 bg-muted/20 p-4">
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-2">
                <span class="text-sm font-semibold text-foreground">
                  {{ $t('admin.ai.agent.detail.knowledgeBases') }}
                </span>
                <Tag class="!mr-0 !rounded-full !px-2 !text-[11px]">
                  {{
                    $t('admin.ai.agent.kbPicker.selectedCount', {
                      count: kbBindings.length,
                    })
                  }}
                </Tag>
                <Tag class="!mr-0 !rounded-full !px-2 !text-[11px]">
                  {{
                    $t('admin.ai.agent.kbPicker.selectionSummary', {
                      count: kbBindings.length,
                      scopes: kbBindingScopeCount,
                    })
                  }}
                </Tag>
              </div>
              <p class="mt-1 text-xs leading-5 text-muted-foreground">
                {{ $t('admin.ai.agent.detail.kbWeightFusionHint') }}
              </p>
            </div>
            <Button type="primary" @click="openKBBindingPicker">
              <IconifyIcon icon="lucide:settings-2" class="mr-1 size-4" />
              {{ $t('admin.ai.agent.kbPicker.manageBindings') }}
            </Button>
          </div>
        </div>

        <div v-if="kbBindings.length > 0" class="flex flex-col gap-2">
          <div
            v-for="b in kbBindings"
            :key="b.id"
            class="flex items-center justify-between rounded-xl border bg-background px-4 py-3 transition-colors"
          >
            <div class="flex items-center gap-3">
              <div
                class="flex size-8 shrink-0 items-center justify-center rounded-lg bg-blue-500/10"
              >
                <IconifyIcon
                  icon="lucide:book-open"
                  class="size-4 text-blue-500"
                />
              </div>
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-2">
                  <span class="text-sm font-medium">
                    {{ b.kb_name || `#${b.knowledge_base_id}` }}
                  </span>
                  <Tag
                    v-if="b.kb_document_count != null"
                    class="!mr-0 !text-[10px]"
                  >
                    {{ b.kb_document_count }}
                    {{ $t('admin.ai.agent.detail.kbDocCount') }}
                  </Tag>
                </div>
                <p
                  v-if="b.kb_description"
                  class="mt-0.5 truncate text-xs text-muted-foreground"
                >
                  {{ b.kb_description }}
                </p>
                <div class="mt-1 flex flex-wrap gap-1.5">
                  <Tag class="!mr-0 !text-[10px]">
                    {{ $t('admin.ai.agent.detail.kbCreatorTenant') }}:
                    {{ getKbOwnerText(b) }}
                  </Tag>
                  <Tag
                    v-if="b.kb_embedding_model_name"
                    class="!mr-0 !text-[10px]"
                  >
                    {{ $t('admin.ai.agent.detail.kbEmbeddingModel') }}:
                    {{ b.kb_embedding_model_name }}
                  </Tag>
                  <Tag
                    v-if="b.kb_embedding_dimensions != null"
                    class="!mr-0 !text-[10px]"
                  >
                    {{ $t('admin.ai.agent.detail.kbEmbeddingDimensions') }}:
                    {{ b.kb_embedding_dimensions }}
                  </Tag>
                  <Tag v-if="b.kb_chunk_strategy" class="!mr-0 !text-[10px]">
                    {{ $t('admin.ai.agent.detail.kbChunkStrategy') }}:
                    {{ getKbChunkStrategyText(b.kb_chunk_strategy) }}
                  </Tag>
                </div>
              </div>
            </div>
            <div class="flex items-center gap-3">
              <div class="flex items-center gap-1.5">
                <span class="text-xs text-muted-foreground">{{
                  $t('admin.ai.agent.detail.kbWeight')
                }}</span>
                <InputNumber
                  :value="b.weight"
                  :min="0.1"
                  :max="2"
                  :step="0.1"
                  size="small"
                  class="!w-20"
                  @change="
                    (val) => val != null && updateKBWeight(b.id, Number(val))
                  "
                />
              </div>
              <Switch
                :checked="b.enabled"
                size="small"
                :aria-label="`${$t('admin.ai.agent.detail.kbEnabled')}: ${
                  b.kb_name ?? b.knowledge_base_id
                }`"
                @change="toggleKBEnabled(b)"
              />
              <Popconfirm
                :title="$t('common.confirmDelete')"
                @confirm="unbindKB(b.knowledge_base_id)"
              >
                <Button size="small" danger type="text">
                  <IconifyIcon icon="lucide:unlink" class="size-3.5" />
                </Button>
              </Popconfirm>
            </div>
          </div>
        </div>

        <div
          v-if="kbBindings.length === 0 && !kbBindingsLoading"
          class="rounded-2xl border border-dashed border-border/70 bg-background px-6 py-10 text-center"
        >
          <div
            class="mx-auto flex size-12 items-center justify-center rounded-full bg-primary/10 text-primary"
          >
            <IconifyIcon icon="lucide:library-big" class="size-6" />
          </div>
          <div class="mt-4 text-sm font-semibold text-foreground">
            {{ $t('admin.ai.agent.kbPicker.emptySelected') }}
          </div>
          <div
            class="mx-auto mt-2 max-w-xl text-xs leading-6 text-muted-foreground"
          >
            {{ $t('admin.ai.agent.kbPicker.detailEmptyHint') }}
          </div>
          <Button class="mt-5" type="primary" @click="openKBBindingPicker">
            <IconifyIcon icon="lucide:sparkles" class="mr-1 size-4" />
            {{ $t('admin.ai.agent.kbPicker.manageBindings') }}
          </Button>
        </div>
      </div>
    </Spin>
  </div>
</template>
