<script lang="ts" setup>
import type { AgentKnowledgeBaseBindingDraftItem } from './types';

/**
 * Agent knowledge base binding picker (search, scope filter, replace-mode drafts).
 * 智能体知识库绑定选择器（搜索、作用域筛选、替换模式草稿）。
 */
import { computed, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { useDebounceFn } from '@vueuse/core';
import {
  Button,
  Checkbox,
  Drawer,
  Empty,
  Input,
  message,
  Select,
  Spin,
  Tag,
} from 'ant-design-vue';

import { $t } from '#/locales';
import { getErrorMessage } from '#/utils/error-helpers';
import {
  getScopeColor,
  getScopeIcon,
  getScopeText,
} from '#/utils/scope-helpers';

import { selectableToDraft } from './types';

defineOptions({ name: 'AgentKnowledgeBaseBindingPicker' });

const props = withDefaults(
  defineProps<{
    confirmText?: string;
    excludedIds?: number[];
    fetchCandidates: () => Promise<SelectableKnowledgeBaseItem[]>;
    i18nPrefix?: string;
    title?: string;
  }>(),
  {
    confirmText: '',
    excludedIds: () => [],
    i18nPrefix: 'admin.ai.agent.kbPicker',
    title: '',
  },
);

const emit = defineEmits<{
  cancel: [];
  confirm: [AgentKnowledgeBaseBindingDraftItem[]];
}>();

interface SelectableKnowledgeBaseItem {
  description: null | string;
  id: number;
  name: string;
  owner_tenant_id: null | number;
  owner_tenant_name: null | string;
  scope: string;
}

const open = defineModel<boolean>('open', { default: false });
const modelValue = defineModel<AgentKnowledgeBaseBindingDraftItem[]>(
  'modelValue',
  {
    default: () => [],
  },
);

const drawerTitle = computed(() => props.title || tt('title'));
const primaryText = computed(() => props.confirmText || $t('common.confirm'));

const working = ref<AgentKnowledgeBaseBindingDraftItem[]>([]);
const searchInput = ref('');
const searchKeyword = ref('');
const filterScope = ref<string | undefined>(undefined);
const candidateItems = ref<SelectableKnowledgeBaseItem[]>([]);
const loading = ref(false);
const errorText = ref<null | string>(null);

function tt(key: string, params?: Record<string, unknown>): string {
  if (params) {
    return $t(`${props.i18nPrefix}.${key}`, params);
  }
  return $t(`${props.i18nPrefix}.${key}`);
}

function cloneDrafts(
  list: AgentKnowledgeBaseBindingDraftItem[],
): AgentKnowledgeBaseBindingDraftItem[] {
  return list.map((item) => ({ ...item }));
}

function getOwnerText(
  ownerTenantId: null | number | undefined,
  ownerTenantName: null | string | undefined,
): string {
  if (ownerTenantId === null || ownerTenantId === undefined) {
    return tt('platformOwner');
  }
  return ownerTenantName?.trim() || tt('ownerFallback', { id: ownerTenantId });
}

const debouncedApplySearch = useDebounceFn(() => {
  searchKeyword.value = searchInput.value.trim().toLowerCase();
}, 260);

function applySearchImmediate() {
  searchKeyword.value = searchInput.value.trim().toLowerCase();
}

watch(searchInput, () => {
  debouncedApplySearch();
});

watch(open, (value) => {
  if (!value) return;
  working.value = cloneDrafts(modelValue.value);
  searchInput.value = '';
  searchKeyword.value = '';
  filterScope.value = undefined;
  void fetchCandidateItems();
});

const excludedIdSet = computed(() => new Set(props.excludedIds));

const scopeOptions = computed(() => {
  const seen = new Set<string>();
  return candidateItems.value
    .map((item) => item.scope)
    .filter(Boolean)
    .filter((scope) => {
      if (seen.has(scope)) return false;
      seen.add(scope);
      return true;
    })
    .map((scope) => ({
      label: getScopeText(scope),
      value: scope,
    }));
});

const filteredCandidates = computed(() => {
  const keyword = searchKeyword.value;
  return candidateItems.value.filter((item) => {
    if (excludedIdSet.value.has(item.id)) {
      return false;
    }
    if (filterScope.value && item.scope !== filterScope.value) {
      return false;
    }
    if (!keyword) {
      return true;
    }
    const haystack = [
      item.name,
      item.description ?? '',
      item.owner_tenant_name ?? '',
      getOwnerText(item.owner_tenant_id, item.owner_tenant_name),
      item.scope ?? '',
      getScopeText(item.scope),
      String(item.id),
    ]
      .join(' ')
      .toLowerCase();
    return haystack.includes(keyword);
  });
});

const groupedCandidates = computed(() => {
  const map = new Map<
    string,
    {
      items: SelectableKnowledgeBaseItem[];
      scope: string;
    }
  >();
  for (const item of filteredCandidates.value) {
    const scope = item.scope || 'unknown';
    const group = map.get(scope);
    if (group) {
      group.items.push(item);
      continue;
    }
    map.set(scope, {
      scope,
      items: [item],
    });
  }
  return [...map.values()];
});

const selectedCount = computed(() => working.value.length);
const selectedScopeCount = computed(
  () => new Set(working.value.map((draft) => draft.kb_scope || 'unknown')).size,
);
const visibleScopeCount = computed(() => groupedCandidates.value.length);
const hasActiveFilters = computed(() =>
  Boolean(searchKeyword.value || filterScope.value),
);

function isSelected(knowledgeBaseId: number): boolean {
  return working.value.some(
    (draft) => draft.knowledge_base_id === knowledgeBaseId,
  );
}

function findWorkingIndex(knowledgeBaseId: number): number {
  return working.value.findIndex(
    (draft) => draft.knowledge_base_id === knowledgeBaseId,
  );
}

function toggleOption(item: SelectableKnowledgeBaseItem) {
  const index = findWorkingIndex(item.id);
  if (index >= 0) {
    working.value.splice(index, 1);
    return;
  }
  working.value.push(selectableToDraft(item));
}

function removeDraft(knowledgeBaseId: number) {
  const index = findWorkingIndex(knowledgeBaseId);
  if (index >= 0) {
    working.value.splice(index, 1);
  }
}

async function fetchCandidateItems() {
  loading.value = true;
  errorText.value = null;
  try {
    candidateItems.value = await props.fetchCandidates();
  } catch (error) {
    console.error('[AgentKnowledgeBaseBindingPicker]', error);
    candidateItems.value = [];
    errorText.value = getErrorMessage(error, 'common.loadFailed');
    message.error(errorText.value);
  } finally {
    loading.value = false;
  }
}

function refreshCandidates() {
  void fetchCandidateItems();
}

function onConfirm() {
  const next = cloneDrafts(working.value);
  modelValue.value = next;
  emit('confirm', next);
  open.value = false;
}

function onCancel() {
  emit('cancel');
  open.value = false;
}
</script>

<template>
  <Drawer
    v-model:open="open"
    :title="drawerTitle"
    width="min(1120px, 96vw)"
    :destroy-on-close="false"
    class="agent-kb-binding-picker"
  >
    <div class="flex max-h-[calc(100vh-120px)] flex-col gap-4">
      <div
        class="rounded-2xl border border-border/70 bg-gradient-to-br from-primary/5 via-background to-background p-4"
      >
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div class="min-w-0 flex-1">
            <p class="text-xs leading-5 text-muted-foreground">
              {{ tt('subtitle') }}
            </p>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <div
              class="rounded-full border border-primary/20 bg-background/90 px-3 py-1.5"
            >
              <div
                class="text-[11px] uppercase tracking-[0.12em] text-muted-foreground"
              >
                {{ tt('selected') }}
              </div>
              <div class="mt-0.5 text-sm font-semibold text-foreground">
                {{ selectedCount }}
              </div>
            </div>
            <div
              class="rounded-full border border-border/70 bg-background/90 px-3 py-1.5"
            >
              <div
                class="text-[11px] uppercase tracking-[0.12em] text-muted-foreground"
              >
                {{ tt('scopes') }}
              </div>
              <div class="mt-0.5 text-sm font-semibold text-foreground">
                {{ visibleScopeCount }}
              </div>
            </div>
            <div
              class="rounded-full border border-border/70 bg-background/90 px-3 py-1.5"
            >
              <div
                class="text-[11px] uppercase tracking-[0.12em] text-muted-foreground"
              >
                {{ tt('matches') }}
              </div>
              <div class="mt-0.5 text-sm font-semibold text-foreground">
                {{ filteredCandidates.length }}
              </div>
            </div>
          </div>
        </div>

        <div class="mt-4 grid gap-3 xl:grid-cols-[minmax(0,1fr)_240px_auto]">
          <Input.Search
            v-model:value="searchInput"
            allow-clear
            size="large"
            :placeholder="tt('searchPlaceholder')"
            @search="applySearchImmediate"
          />
          <Select
            v-model:value="filterScope"
            allow-clear
            size="large"
            :options="scopeOptions"
            :placeholder="tt('scopeFilter')"
          />
          <Button size="large" @click="refreshCandidates">
            <template #icon>
              <IconifyIcon icon="lucide:refresh-cw" class="size-4" />
            </template>
            {{ tt('refresh') }}
          </Button>
        </div>

        <div
          class="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground"
        >
          <span>
            {{
              tt('resultSummary', {
                count: filteredCandidates.length,
                scopes: visibleScopeCount,
              })
            }}
          </span>
          <Tag
            v-if="hasActiveFilters"
            color="blue"
            class="!m-0 !rounded-full !px-2 !text-[11px]"
          >
            {{ tt('filtered') }}
          </Tag>
          <Tag
            class="!m-0 !rounded-full !border-amber-200 !bg-amber-50 !px-2 !text-[11px] !text-amber-700"
          >
            {{ tt('replaceNotice') }}
          </Tag>
        </div>

        <div
          v-if="errorText"
          class="mt-3 rounded-xl border border-destructive/20 bg-destructive/5 px-3 py-2 text-sm text-destructive"
        >
          {{ errorText }}
        </div>
      </div>

      <div class="flex min-h-0 flex-1 gap-4 overflow-hidden max-lg:flex-col">
        <div
          class="flex min-w-0 flex-1 flex-col gap-3 overflow-hidden rounded-2xl border border-border/70 bg-card"
        >
          <div class="border-b border-border/70 px-4 py-3">
            <div class="flex flex-wrap items-center justify-between gap-2">
              <div>
                <div class="text-sm font-semibold text-foreground">
                  {{ tt('candidates') }}
                </div>
                <div class="mt-1 text-xs text-muted-foreground">
                  {{
                    tt('candidateHint', {
                      count: filteredCandidates.length,
                    })
                  }}
                </div>
              </div>
              <Tag class="!m-0 !rounded-full !px-2 !py-0.5 !text-[11px]">
                {{
                  tt('selectedCount', {
                    count: selectedCount,
                  })
                }}
              </Tag>
            </div>
          </div>
          <div class="min-h-0 flex-1 overflow-y-auto px-4 pb-4">
            <Spin :spinning="loading">
              <template v-if="!loading && groupedCandidates.length === 0">
                <div class="flex min-h-[320px] items-center justify-center">
                  <Empty :description="tt('emptyCandidates')" />
                </div>
              </template>
              <div v-else class="flex flex-col gap-4">
                <div
                  v-for="group in groupedCandidates"
                  :key="group.scope"
                  class="rounded-2xl border border-border/70 bg-muted/20 p-3"
                >
                  <div
                    class="mb-3 flex flex-wrap items-center justify-between gap-2"
                  >
                    <div class="min-w-0">
                      <div class="flex flex-wrap items-center gap-2">
                        <span
                          class="inline-flex items-center gap-1.5 text-sm font-semibold text-foreground"
                        >
                          <IconifyIcon
                            :icon="getScopeIcon(group.scope)"
                            class="size-4"
                          />
                          {{ getScopeText(group.scope) || group.scope }}
                        </span>
                        <Tag
                          :color="getScopeColor(group.scope)"
                          class="!m-0 !rounded-full !text-[11px]"
                        >
                          {{ group.items.length }}
                        </Tag>
                      </div>
                    </div>
                  </div>
                  <div class="flex flex-col gap-2.5">
                    <div
                      v-for="item in group.items"
                      :key="item.id"
                      class="cursor-pointer rounded-xl border px-3 py-3 transition-all"
                      :class="
                        isSelected(item.id)
                          ? 'border-primary/45 bg-primary/[0.05] shadow-sm'
                          : 'border-border/60 bg-background hover:border-primary/25 hover:bg-primary/[0.02]'
                      "
                      @click="toggleOption(item)"
                    >
                      <div class="flex items-start gap-3">
                        <Checkbox
                          :checked="isSelected(item.id)"
                          class="mt-0.5"
                          @click.stop
                          @change="() => toggleOption(item)"
                        />
                        <div class="min-w-0 flex-1">
                          <div
                            class="flex flex-wrap items-start justify-between gap-2"
                          >
                            <div class="min-w-0 flex-1">
                              <div class="flex flex-wrap items-center gap-2">
                                <span
                                  class="text-sm font-medium text-foreground"
                                >
                                  {{ item.name }}
                                </span>
                                <Tag
                                  v-if="isSelected(item.id)"
                                  color="blue"
                                  class="!m-0 !rounded-full !text-[11px]"
                                >
                                  {{ tt('selectedBadge') }}
                                </Tag>
                              </div>
                            </div>
                            <IconifyIcon
                              :icon="
                                isSelected(item.id)
                                  ? 'lucide:check-circle-2'
                                  : 'lucide:circle'
                              "
                              class="mt-0.5 size-4 shrink-0"
                              :class="
                                isSelected(item.id)
                                  ? 'text-primary'
                                  : 'text-muted-foreground/60'
                              "
                            />
                          </div>
                          <div
                            class="mt-1.5 flex flex-wrap items-center gap-1.5"
                          >
                            <Tag
                              :color="getScopeColor(item.scope)"
                              class="!m-0 !text-[11px]"
                            >
                              {{ getScopeText(item.scope) || item.scope }}
                            </Tag>
                            <Tag class="!m-0 !text-[11px]">
                              #{{ item.id }}
                            </Tag>
                            <Tag class="!m-0 !text-[11px]">
                              {{ tt('creatorLabel') }}:
                              {{
                                getOwnerText(
                                  item.owner_tenant_id,
                                  item.owner_tenant_name,
                                )
                              }}
                            </Tag>
                          </div>
                          <p
                            v-if="item.description"
                            class="mt-2 line-clamp-2 text-xs leading-5 text-muted-foreground"
                          >
                            {{ item.description }}
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </Spin>
          </div>
        </div>

        <div
          class="flex w-[min(100%,340px)] shrink-0 flex-col overflow-hidden rounded-2xl border border-border/70 bg-card"
        >
          <div class="border-b border-border/70 px-4 py-3">
            <div class="flex items-center justify-between gap-2">
              <div>
                <div class="text-sm font-semibold text-foreground">
                  {{ tt('selected') }}
                </div>
                <div class="mt-1 text-xs text-muted-foreground">
                  {{
                    tt('selectionSummary', {
                      count: selectedCount,
                      scopes: selectedScopeCount,
                    })
                  }}
                </div>
              </div>
              <div
                class="rounded-full border border-primary/20 bg-primary/5 px-3 py-1 text-sm font-semibold text-primary"
              >
                {{ selectedCount }}
              </div>
            </div>
          </div>
          <div class="min-h-0 flex-1 overflow-y-auto p-3">
            <div
              v-if="working.length === 0"
              class="flex min-h-[320px] flex-col items-center justify-center rounded-2xl border border-dashed border-border/70 bg-muted/20 px-6 text-center"
            >
              <div
                class="flex size-12 items-center justify-center rounded-full bg-primary/10 text-primary"
              >
                <IconifyIcon icon="lucide:library" class="size-6" />
              </div>
              <div class="mt-4 text-sm font-medium text-foreground">
                {{ tt('emptySelected') }}
              </div>
              <div
                class="mt-1 max-w-[240px] text-xs leading-5 text-muted-foreground"
              >
                {{ tt('selectionHint') }}
              </div>
            </div>
            <div v-else class="flex flex-col gap-2">
              <div
                v-for="(draft, index) in working"
                :key="draft.knowledge_base_id"
                class="rounded-2xl border border-border/70 bg-muted/15 p-3"
              >
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0 flex-1">
                    <div class="flex items-center gap-2">
                      <span
                        class="inline-flex size-6 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary"
                      >
                        {{ index + 1 }}
                      </span>
                      <div class="truncate text-sm font-medium text-foreground">
                        {{ draft.kb_name }}
                      </div>
                    </div>
                    <div class="mt-2 flex flex-wrap gap-1.5">
                      <Tag
                        :color="getScopeColor(draft.kb_scope || undefined)"
                        class="!m-0 !text-[11px]"
                      >
                        {{
                          getScopeText(draft.kb_scope || undefined) ||
                          draft.kb_scope ||
                          '-'
                        }}
                      </Tag>
                      <Tag class="!m-0 !text-[11px]">
                        #{{ draft.knowledge_base_id }}
                      </Tag>
                      <Tag class="!m-0 !text-[11px]">
                        {{ tt('creatorLabel') }}:
                        {{
                          getOwnerText(
                            draft.kb_owner_tenant_id,
                            draft.kb_owner_tenant_name,
                          )
                        }}
                      </Tag>
                    </div>
                    <div
                      v-if="draft.kb_description"
                      class="mt-2 line-clamp-2 text-xs leading-5 text-muted-foreground"
                    >
                      {{ draft.kb_description }}
                    </div>
                  </div>
                  <Button
                    type="link"
                    danger
                    size="small"
                    @click="removeDraft(draft.knowledge_base_id)"
                  >
                    {{ tt('remove') }}
                  </Button>
                </div>
              </div>
            </div>
          </div>
          <div
            class="border-t border-border/70 bg-muted/10 px-4 py-3 text-xs leading-5 text-muted-foreground"
          >
            {{ tt('replaceNotice') }}
          </div>
        </div>
      </div>

      <div class="flex justify-end gap-2 border-t border-border/70 pt-3">
        <Button @click="onCancel">{{ $t('common.cancel') }}</Button>
        <Button type="primary" @click="onConfirm">{{ primaryText }}</Button>
      </div>
    </div>
  </Drawer>
</template>
