<script lang="ts" setup>
import type { AgentKBBindingInfo } from '#/api/tenant/agents';
import type { AgentKnowledgeBaseBindingDraftItem } from '#/components/business/agent-kb-binding-picker';

import { computed, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  Button,
  InputNumber,
  message,
  Popconfirm,
  Spin,
  Switch,
  Tag,
} from 'ant-design-vue';

import {
  batchBindKBsApi,
  getAgentKBsApi,
  suppressPlatformKbApi,
  unbindKBApi,
  unsuppressPlatformKbApi,
  updateAgentKBBindingApi,
} from '#/api/tenant/agents';
import { getTenantSelectableKBApi } from '#/api/tenant/knowledge-bases';
import {
  AgentKnowledgeBaseBindingPicker,
  bindingsToDrafts as kbBindingsToDrafts,
  draftsToBatchPayload as kbDraftsToBatchPayload,
} from '#/components/business/agent-kb-binding-picker';
import { $t } from '#/locales';
import { showRequestError } from '#/utils/error-helpers';

const props = defineProps<{
  active: boolean;
  agentId: number;
  canManageKnowledgeBases: boolean;
  isPlatformAssignedAgent: boolean;
  isTenantOwned: boolean;
}>();

const kbBindings = ref<AgentKBBindingInfo[]>([]);
const kbBindingsLoading = ref(false);
const kbPickerOpen = ref(false);
const kbPickerDrafts = ref<AgentKnowledgeBaseBindingDraftItem[]>([]);
const platformKbSuppressLoadingKbId = ref<null | number>(null);

const managedKbBindings = computed(() =>
  props.isTenantOwned
    ? kbBindings.value
    : kbBindings.value.filter((binding) => !isKbBindingReadonly(binding)),
);
const kbManagedScopeCount = computed(() => {
  const keys = new Set(
    managedKbBindings.value.map((binding) => binding.kb_scope || 'unknown'),
  );
  return keys.size;
});
const kbPickerExcludedIds = computed(() =>
  props.isTenantOwned
    ? []
    : kbBindings.value
        .filter((binding) => isKbBindingReadonly(binding))
        .map((binding) => binding.knowledge_base_id),
);

function isKbBindingReadonly(binding: AgentKBBindingInfo) {
  return binding.binding_scope === 'platform';
}

async function loadKBBindings() {
  kbBindingsLoading.value = true;
  try {
    kbBindings.value = await getAgentKBsApi(props.agentId);
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

function getKbOwnerText(binding: AgentKBBindingInfo): string {
  if (
    binding.kb_owner_tenant_id === null ||
    binding.kb_owner_tenant_id === undefined
  ) {
    return $t('tenant.ai.agent.detail.kbOwnerPlatform');
  }
  return binding.kb_owner_tenant_name || `#${binding.kb_owner_tenant_id}`;
}

function openKBBindingPicker() {
  kbPickerDrafts.value = kbBindingsToDrafts(managedKbBindings.value);
  kbPickerOpen.value = true;
}

async function onKBBindingPickerConfirm(
  drafts: AgentKnowledgeBaseBindingDraftItem[],
) {
  try {
    await batchBindKBsApi(
      props.agentId,
      kbDraftsToBatchPayload(drafts).knowledge_base_ids,
    );
    await loadKBBindings();
    message.success($t('tenant.ai.agent.detail.saveSuccess'));
  } catch (error) {
    showRequestError(error, 'common.saveFailed');
  }
}

async function unbindKB(knowledgeBaseId: number) {
  try {
    await unbindKBApi(props.agentId, knowledgeBaseId);
    await loadKBBindings();
    message.success($t('tenant.ai.agent.detail.saveSuccess'));
  } catch (error) {
    showRequestError(error, 'common.saveFailed');
  }
}

async function toggleKBEnabled(binding: AgentKBBindingInfo) {
  if (isKbBindingReadonly(binding)) return;
  try {
    await updateAgentKBBindingApi(props.agentId, binding.id, {
      enabled: !binding.enabled,
    });
    await loadKBBindings();
  } catch (error) {
    showRequestError(error, 'common.saveFailed');
  }
}

async function updateKBWeight(bindingId: number, weight: number) {
  const row = kbBindings.value.find((x) => x.id === bindingId);
  if (row && isKbBindingReadonly(row)) return;
  try {
    await updateAgentKBBindingApi(props.agentId, bindingId, { weight });
    await loadKBBindings();
    message.success($t('tenant.ai.agent.detail.saveSuccess'));
  } catch (error) {
    showRequestError(error, 'common.saveFailed');
  }
}

async function togglePlatformKbOptOut(
  binding: AgentKBBindingInfo,
  optOut: boolean,
) {
  if (!isKbBindingReadonly(binding)) return;
  platformKbSuppressLoadingKbId.value = binding.knowledge_base_id;
  try {
    await (optOut
      ? suppressPlatformKbApi(props.agentId, binding.knowledge_base_id)
      : unsuppressPlatformKbApi(props.agentId, binding.knowledge_base_id));
    await loadKBBindings();
    message.success($t('tenant.ai.agent.detail.saveSuccess'));
  } catch (error) {
    showRequestError(error, 'common.saveFailed');
  } finally {
    platformKbSuppressLoadingKbId.value = null;
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
      :excluded-ids="kbPickerExcludedIds"
      :fetch-candidates="getTenantSelectableKBApi"
      i18n-prefix="tenant.ai.agent.kbPicker"
      @confirm="onKBBindingPickerConfirm"
    />
    <Spin :spinning="kbBindingsLoading">
      <div class="flex flex-col gap-4">
        <p v-if="isPlatformAssignedAgent" class="text-xs text-muted-foreground">
          {{ $t('tenant.ai.agent.detail.kbTenantOverlayHint') }}
        </p>
        <div
          v-if="canManageKnowledgeBases"
          class="rounded-2xl border border-border/70 bg-muted/20 p-4"
        >
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-2">
                <span class="text-sm font-semibold text-foreground">
                  {{ $t('tenant.ai.agent.detail.knowledgeBases') }}
                </span>
                <Tag class="!mr-0 !rounded-full !px-2 !text-[11px]">
                  {{
                    $t('tenant.ai.agent.kbPicker.selectedCount', {
                      count: managedKbBindings.length,
                    })
                  }}
                </Tag>
                <Tag class="!mr-0 !rounded-full !px-2 !text-[11px]">
                  {{
                    $t('tenant.ai.agent.kbPicker.selectionSummary', {
                      count: managedKbBindings.length,
                      scopes: kbManagedScopeCount,
                    })
                  }}
                </Tag>
              </div>
              <p class="mt-1 text-xs leading-5 text-muted-foreground">
                {{ $t('tenant.ai.agent.detail.kbWeightFusionHint') }}
              </p>
            </div>
            <Button type="primary" @click="openKBBindingPicker">
              <IconifyIcon icon="lucide:settings-2" class="mr-1 size-4" />
              {{ $t('tenant.ai.agent.kbPicker.manageBindings') }}
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
                <div class="flex flex-wrap items-center gap-2">
                  <span class="text-sm font-medium">
                    {{ b.kb_name || `#${b.knowledge_base_id}` }}
                  </span>
                  <Tag
                    v-if="isKbBindingReadonly(b)"
                    color="orange"
                    class="!mr-0 !text-[10px]"
                  >
                    {{ $t('tenant.ai.agent.detail.kbPlatformBadge') }}
                  </Tag>
                  <Tag
                    v-if="b.kb_document_count != null"
                    class="!mr-0 !text-[10px]"
                  >
                    {{ b.kb_document_count }}
                    {{ $t('tenant.ai.agent.detail.kbDocCount') }}
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
                    {{ $t('tenant.ai.agent.detail.kbCreatorTenant') }}:
                    {{ getKbOwnerText(b) }}
                  </Tag>
                  <Tag
                    v-if="b.kb_embedding_model_name"
                    class="!mr-0 !text-[10px]"
                  >
                    {{ $t('tenant.ai.agent.detail.kbEmbeddingModel') }}:
                    {{ b.kb_embedding_model_name }}
                  </Tag>
                  <Tag
                    v-if="b.kb_embedding_dimensions != null"
                    class="!mr-0 !text-[10px]"
                  >
                    {{ $t('tenant.ai.agent.detail.kbEmbeddingDimensions') }}:
                    {{ b.kb_embedding_dimensions }}
                  </Tag>
                  <Tag v-if="b.kb_chunk_strategy" class="!mr-0 !text-[10px]">
                    {{ $t('tenant.ai.agent.detail.kbChunkStrategy') }}:
                    {{ getKbChunkStrategyText(b.kb_chunk_strategy) }}
                  </Tag>
                </div>
              </div>
            </div>
            <div class="flex items-center gap-3">
              <div class="flex items-center gap-1.5">
                <span class="text-xs text-muted-foreground">{{
                  $t('tenant.ai.agent.detail.kbWeight')
                }}</span>
                <InputNumber
                  :value="b.weight"
                  :min="0.1"
                  :max="2"
                  :step="0.1"
                  size="small"
                  :disabled="!canManageKnowledgeBases || isKbBindingReadonly(b)"
                  class="!w-20"
                  @change="
                    (val) => val != null && updateKBWeight(b.id, Number(val))
                  "
                />
              </div>
              <Switch
                :checked="b.enabled"
                size="small"
                :disabled="!canManageKnowledgeBases || isKbBindingReadonly(b)"
                :aria-label="`${$t('tenant.ai.agent.detail.kbEnabled')}: ${
                  b.kb_name ?? b.knowledge_base_id
                }`"
                @change="toggleKBEnabled(b)"
              />
              <div
                v-if="isKbBindingReadonly(b) && canManageKnowledgeBases"
                class="flex max-w-[11rem] flex-col gap-0.5"
              >
                <span class="text-[10px] text-muted-foreground">{{
                  $t('tenant.ai.agent.detail.kbPlatformOptOut')
                }}</span>
                <Switch
                  :checked="Boolean(b.platform_suppressed)"
                  size="small"
                  :loading="
                    platformKbSuppressLoadingKbId === b.knowledge_base_id
                  "
                  :aria-label="`${$t('tenant.ai.agent.detail.kbPlatformOptOut')}: ${
                    b.kb_name ?? b.knowledge_base_id
                  }`"
                  @change="(val) => togglePlatformKbOptOut(b, Boolean(val))"
                />
                <span class="text-[10px] leading-tight text-muted-foreground">{{
                  $t('tenant.ai.agent.detail.kbPlatformOptOutHint')
                }}</span>
              </div>
              <Popconfirm
                v-if="canManageKnowledgeBases && !isKbBindingReadonly(b)"
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
            {{ $t('tenant.ai.agent.kbPicker.emptySelected') }}
          </div>
          <div
            class="mx-auto mt-2 max-w-xl text-xs leading-6 text-muted-foreground"
          >
            {{ $t('tenant.ai.agent.kbPicker.detailEmptyHint') }}
          </div>
          <Button
            v-if="canManageKnowledgeBases"
            class="mt-5"
            type="primary"
            @click="openKBBindingPicker"
          >
            <IconifyIcon icon="lucide:sparkles" class="mr-1 size-4" />
            {{ $t('tenant.ai.agent.kbPicker.manageBindings') }}
          </Button>
        </div>
      </div>
    </Spin>
  </div>
</template>
