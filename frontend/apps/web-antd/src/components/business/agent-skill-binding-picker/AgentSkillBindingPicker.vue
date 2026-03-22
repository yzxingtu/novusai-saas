<script lang="ts" setup>
/**
 * Admin agent skill binding picker (search, package filter, pagination, consent drafts).
 * 管理端智能体技能绑定选择器。
 */
import type { AdminSkillSelectOption } from '#/api/admin/skills';

import { computed, nextTick, ref, watch } from 'vue';
import { useDebounceFn } from '@vueuse/core';
import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Checkbox,
  Drawer,
  Empty,
  Input,
  message,
  Pagination,
  Select,
  Spin,
  Tag,
} from 'ant-design-vue';

import { getSkillBindingSelectApi } from '#/api/admin/skills';
import { getSkillPackageSelectApi } from '#/api/admin/skill-packages';
import { $t } from '#/locales';
import { getSkillTypeColor } from '#/utils/ai-helpers';

import {
  type AgentSkillBindingDraftItem,
  type ConsentMode,
  selectOptionToDraft,
} from './types';

defineOptions({ name: 'AgentSkillBindingPicker' });

const emit = defineEmits<{
  cancel: [];
  confirm: [AgentSkillBindingDraftItem[]];
}>();

const open = defineModel<boolean>('open', { default: false });
const modelValue = defineModel<AgentSkillBindingDraftItem[]>('modelValue', {
  default: () => [],
});

const props = withDefaults(
  defineProps<{
    confirmText?: string;
    title?: string;
  }>(),
  {
    confirmText: '',
    title: '',
  },
);

const drawerTitle = computed(
  () => props.title || $t('admin.ai.agent.skillPicker.title'),
);
const primaryText = computed(
  () => props.confirmText || $t('common.confirm'),
);

const working = ref<AgentSkillBindingDraftItem[]>([]);
const searchInput = ref('');
const searchKeyword = ref('');
const filterPackageId = ref<number | undefined>(undefined);
const onlyActive = ref(true);
const page = ref(1);
const pageSize = ref(20);
const total = ref(0);
const candidateItems = ref<AdminSkillSelectOption[]>([]);
const skillsLoading = ref(false);
const skillsError = ref<null | string>(null);

const packageOptions = ref<{ label: string; value: number }[]>([]);
const pkgLoading = ref(false);
const packageSearch = ref('');
const packagePage = ref(1);
const packageHasMore = ref(false);
const packageTotal = ref(0);

const consentOptions = computed(() => [
  { label: $t('admin.ai.agent.consentModeOptions.auto'), value: 'auto' },
  { label: $t('admin.ai.agent.consentModeOptions.ask'), value: 'ask' },
  { label: $t('admin.ai.agent.consentModeOptions.reject'), value: 'reject' },
]);
const selectedCount = computed(() => working.value.length);
const selectedPackageCount = computed(() => {
  const keys = new Set(
    working.value.map((item) => item.package_id ?? `pkg:${item.package_name ?? item.skill_id}`),
  );
  return keys.size;
});

function cloneDrafts(list: AgentSkillBindingDraftItem[]): AgentSkillBindingDraftItem[] {
  return list.map((d) => ({ ...d }));
}

const debouncedApplySearch = useDebounceFn(() => {
  searchKeyword.value = searchInput.value.trim();
  void fetchCandidates(true);
}, 320);

function applySearchImmediate() {
  searchKeyword.value = searchInput.value.trim();
  void fetchCandidates(true);
}

watch(open, (v) => {
  if (v) {
    working.value = cloneDrafts(modelValue.value);
    searchInput.value = '';
    searchKeyword.value = '';
    filterPackageId.value = undefined;
    onlyActive.value = true;
    page.value = 1;
    void nextTick(() => {
      void fetchCandidates(true);
      void resetPackages();
    });
  }
});

watch(searchInput, () => {
  debouncedApplySearch();
});

const debouncedPkgSearch = useDebounceFn((q: string) => {
  packageSearch.value = q.trim();
  void loadPackages(true);
}, 320);

function isSelected(skillId: number): boolean {
  return working.value.some((d) => d.skill_id === skillId);
}

function findWorkingIndex(skillId: number): number {
  return working.value.findIndex((d) => d.skill_id === skillId);
}

function toggleOption(opt: AdminSkillSelectOption) {
  const id = opt.value;
  const idx = findWorkingIndex(id);
  if (idx >= 0) {
    working.value.splice(idx, 1);
  } else {
    working.value.push(selectOptionToDraft(opt, 'auto'));
  }
}

function removeDraft(skillId: number) {
  const idx = findWorkingIndex(skillId);
  if (idx >= 0) {
    working.value.splice(idx, 1);
  }
}

function setConsent(skillId: number, mode: ConsentMode) {
  const idx = findWorkingIndex(skillId);
  if (idx >= 0) {
    const next = { ...working.value[idx]!, default_consent_mode: mode };
    working.value.splice(idx, 1, next);
  }
}

const groupedCandidates = computed(() => {
  const map = new Map<
    number,
    {
      is_system: boolean;
      options: AdminSkillSelectOption[];
      package_id: number;
      package_name: string;
      source_plugin: null | string;
    }
  >();
  for (const opt of candidateItems.value) {
    const pid = opt.extra?.package_id ?? 0;
    const pname = opt.extra?.package_name ?? '—';
    let g = map.get(pid);
    if (!g) {
      g = {
        package_id: pid,
        package_name: pname,
        options: [],
        source_plugin: opt.extra?.source_plugin ?? null,
        is_system: Boolean(opt.extra?.is_system),
      };
      map.set(pid, g);
    }
    g.options.push(opt);
  }
  return [...map.values()];
});
const visiblePackageCount = computed(() => groupedCandidates.value.length);
const hasActiveFilters = computed(
  () => Boolean(searchKeyword.value || filterPackageId.value != null || !onlyActive.value),
);

async function fetchCandidates(resetPage: boolean) {
  if (resetPage) {
    page.value = 1;
  }
  skillsLoading.value = true;
  skillsError.value = null;
  try {
    const res = await getSkillBindingSelectApi({
      include_system: true,
      only_active: onlyActive.value,
      package_id: filterPackageId.value ?? undefined,
      page: page.value,
      page_size: pageSize.value,
      search: searchKeyword.value || undefined,
    });
    candidateItems.value = Array.isArray(res.items) ? res.items : [];
    total.value = res.total ?? 0;
  } catch (error) {
    console.error('[AgentSkillBindingPicker]', error);
    skillsError.value = $t('common.loadFailed');
    candidateItems.value = [];
    total.value = 0;
    message.error($t('common.loadFailed'));
  } finally {
    skillsLoading.value = false;
  }
}

async function resetPackages() {
  packageOptions.value = [];
  packagePage.value = 1;
  packageSearch.value = '';
  packageHasMore.value = false;
  packageTotal.value = 0;
  await loadPackages(true);
}

async function loadPackages(reset: boolean) {
  if (reset) {
    packagePage.value = 1;
    packageOptions.value = [];
  }
  pkgLoading.value = true;
  try {
    const res = await getSkillPackageSelectApi({
      include_system: true,
      page: packagePage.value,
      page_size: 20,
      search: packageSearch.value || undefined,
    });
    const raw = res.items ?? [];
    const mapped = raw.map((p) => ({
      label: p.label,
      value: typeof p.value === 'number' ? p.value : Number(p.value),
    })).filter((p) => Number.isFinite(p.value));
    if (reset) {
      packageOptions.value = mapped;
    } else {
      const seen = new Set(packageOptions.value.map((o) => o.value));
      for (const m of mapped) {
        if (!seen.has(m.value)) {
          packageOptions.value.push(m);
          seen.add(m.value);
        }
      }
    }
    const t = res.total ?? 0;
    packageTotal.value = t;
    const ps = res.page_size ?? 20;
    const pg = res.page ?? 1;
    packageHasMore.value = Boolean(res.has_more ?? pg * ps < t);
  } catch (error) {
    console.error('[AgentSkillBindingPicker]', error);
    message.error($t('common.loadFailed'));
  } finally {
    pkgLoading.value = false;
  }
}

async function loadMorePackages() {
  if (!packageHasMore.value || pkgLoading.value) return;
  packagePage.value += 1;
  await loadPackages(false);
}

function refreshCandidates() {
  void fetchCandidates(true);
}

function onPackageDropdownOpen(opened: boolean) {
  if (opened && packageOptions.value.length === 0) {
    void loadPackages(true);
  }
}

function onPageChange() {
  void fetchCandidates(false);
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

function getSourceTagMeta(sourcePlugin: null | string, isSystem: boolean) {
  if (sourcePlugin) {
    return { color: 'purple', text: sourcePlugin };
  }
  if (isSystem) {
    return { color: 'red', text: $t('admin.ai.skillPackage.system') };
  }
  return null;
}

watch(onlyActive, () => {
  void fetchCandidates(true);
});

watch(filterPackageId, () => {
  void fetchCandidates(true);
});

watch(pageSize, () => {
  page.value = 1;
  void fetchCandidates(false);
});
</script>

<template>
  <Drawer
    v-model:open="open"
    :title="drawerTitle"
    width="min(1120px, 96vw)"
    :destroy-on-close="false"
    class="agent-skill-binding-picker"
  >
    <div class="flex max-h-[calc(100vh-120px)] flex-col gap-4">
      <div
        class="rounded-2xl border border-border/70 bg-gradient-to-br from-primary/5 via-background to-background p-4"
      >
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div class="min-w-0 flex-1">
            <p class="text-xs leading-5 text-muted-foreground">
              {{ $t('admin.ai.agent.skillPicker.subtitle') }}
            </p>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <div class="rounded-full border border-primary/20 bg-background/90 px-3 py-1.5">
              <div class="text-[11px] uppercase tracking-[0.12em] text-muted-foreground">
                {{ $t('admin.ai.agent.skillPicker.selected') }}
              </div>
              <div class="mt-0.5 text-sm font-semibold text-foreground">
                {{ selectedCount }}
              </div>
            </div>
            <div class="rounded-full border border-border/70 bg-background/90 px-3 py-1.5">
              <div class="text-[11px] uppercase tracking-[0.12em] text-muted-foreground">
                {{ $t('admin.ai.agent.skillPicker.packages') }}
              </div>
              <div class="mt-0.5 text-sm font-semibold text-foreground">
                {{ visiblePackageCount }}
              </div>
            </div>
            <div class="rounded-full border border-border/70 bg-background/90 px-3 py-1.5">
              <div class="text-[11px] uppercase tracking-[0.12em] text-muted-foreground">
                {{ $t('admin.ai.agent.skillPicker.matches') }}
              </div>
              <div class="mt-0.5 text-sm font-semibold text-foreground">
                {{ total }}
              </div>
            </div>
          </div>
        </div>

        <div class="mt-4 grid gap-3 xl:grid-cols-[minmax(0,1fr)_240px_auto_auto]">
          <Input.Search
            v-model:value="searchInput"
            allow-clear
            size="large"
            :placeholder="$t('admin.ai.agent.skillPicker.searchPlaceholder')"
            @search="applySearchImmediate"
          />
          <Select
            v-model:value="filterPackageId"
            allow-clear
            show-search
            size="large"
            :filter-option="false"
            :options="packageOptions"
            :loading="pkgLoading"
            :placeholder="$t('admin.ai.agent.skillPicker.packageFilter')"
            @search="debouncedPkgSearch"
            @dropdown-visible-change="onPackageDropdownOpen"
          >
            <template #dropdownRender="{ menuNode: menu }">
              <div>
                <component :is="menu" />
                <div
                  v-if="packageHasMore"
                  class="border-t border-border px-2 py-1.5"
                >
                  <Button
                    block
                    type="link"
                    size="small"
                    :loading="pkgLoading"
                    @click.stop="loadMorePackages"
                  >
                    {{ $t('admin.ai.agent.skillPicker.loadMorePackages') }}
                  </Button>
                </div>
              </div>
            </template>
          </Select>
          <label
            class="flex min-h-11 items-center justify-center rounded-xl border border-border/70 bg-background px-3 text-sm text-foreground"
          >
            <Checkbox v-model:checked="onlyActive">
              {{ $t('admin.ai.agent.skillPicker.onlyActive') }}
            </Checkbox>
          </label>
          <Button size="large" @click="refreshCandidates">
            <template #icon>
              <IconifyIcon icon="lucide:refresh-cw" class="size-4" />
            </template>
            {{ $t('admin.ai.agent.skillPicker.refresh') }}
          </Button>
        </div>

        <div class="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span>
            {{
              $t('admin.ai.agent.skillPicker.resultSummary', {
                skills: total,
                packages: visiblePackageCount,
              })
            }}
          </span>
          <Tag v-if="hasActiveFilters" color="blue" class="!m-0 !rounded-full !px-2 !text-[11px]">
            {{ $t('admin.ai.agent.skillPicker.filtered') }}
          </Tag>
          <Tag
            class="!m-0 !rounded-full !border-amber-200 !bg-amber-50 !px-2 !text-[11px] !text-amber-700"
          >
            {{ $t('admin.ai.agent.skillPicker.replaceNotice') }}
          </Tag>
        </div>

        <div v-if="skillsError" class="mt-3 rounded-xl border border-destructive/20 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          {{ skillsError }}
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
                  {{ $t('admin.ai.agent.skillPicker.candidates') }}
                </div>
                <div class="mt-1 text-xs text-muted-foreground">
                  {{
                    $t('admin.ai.agent.skillPicker.candidateHint', {
                      count: total,
                    })
                  }}
                </div>
              </div>
              <Tag class="!m-0 !rounded-full !px-2 !py-0.5 !text-[11px]">
                {{
                  $t('admin.ai.agent.skillPicker.selectedCount', {
                    count: selectedCount,
                  })
                }}
              </Tag>
            </div>
          </div>
          <div class="min-h-0 flex-1 overflow-y-auto px-4 pb-4">
            <Spin :spinning="skillsLoading">
              <template v-if="!skillsLoading && groupedCandidates.length === 0">
                <div class="flex min-h-[320px] items-center justify-center">
                  <Empty :description="$t('admin.ai.agent.skillPicker.emptyCandidates')" />
                </div>
              </template>
              <div v-else class="flex flex-col gap-4">
                <div
                  v-for="group in groupedCandidates"
                  :key="group.package_id"
                  class="rounded-2xl border border-border/70 bg-muted/20 p-3"
                >
                  <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
                    <div class="min-w-0">
                      <div class="flex flex-wrap items-center gap-2">
                        <span class="text-sm font-semibold text-foreground">{{
                          group.package_name
                        }}</span>
                        <Tag class="!m-0 !rounded-full !text-[11px]">
                          {{
                            $t('admin.ai.agent.skillPicker.packageMatches', {
                              count: group.options.length,
                            })
                          }}
                        </Tag>
                        <Tag
                          v-if="getSourceTagMeta(group.source_plugin, group.is_system)"
                          :color="getSourceTagMeta(group.source_plugin, group.is_system)!.color"
                          class="!m-0 !text-[11px]"
                        >
                          {{ getSourceTagMeta(group.source_plugin, group.is_system)!.text }}
                        </Tag>
                      </div>
                    </div>
                  </div>
                  <div class="flex flex-col gap-2.5">
                    <div
                      v-for="opt in group.options"
                      :key="opt.value"
                      class="cursor-pointer rounded-xl border px-3 py-3 transition-all"
                      :class="
                        isSelected(opt.value)
                          ? 'border-primary/45 bg-primary/[0.05] shadow-sm'
                          : 'border-border/60 bg-background hover:border-primary/25 hover:bg-primary/[0.02]'
                      "
                      @click="toggleOption(opt)"
                    >
                      <Checkbox
                        :checked="isSelected(opt.value)"
                        class="mt-0.5"
                        @click.stop
                        @change="() => toggleOption(opt)"
                      />
                      <div class="min-w-0 flex-1">
                        <div class="flex flex-wrap items-start justify-between gap-2">
                          <div class="min-w-0 flex-1">
                            <div class="flex flex-wrap items-center gap-2">
                              <span class="text-sm font-medium text-foreground">{{
                                opt.label
                              }}</span>
                              <Tag
                                v-if="isSelected(opt.value)"
                                color="blue"
                                class="!m-0 !rounded-full !text-[11px]"
                              >
                                {{ $t('admin.ai.agent.skillPicker.selectedBadge') }}
                              </Tag>
                            </div>
                          </div>
                          <IconifyIcon
                            :icon="isSelected(opt.value) ? 'lucide:check-circle-2' : 'lucide:circle'"
                            class="mt-0.5 size-4 shrink-0"
                            :class="isSelected(opt.value) ? 'text-primary' : 'text-muted-foreground/60'"
                          />
                        </div>
                        <div class="mt-1.5 flex flex-wrap items-center gap-1.5">
                          <Tag
                            v-if="opt.extra?.skill_type"
                            class="!m-0 !text-[11px]"
                            :color="getSkillTypeColor(opt.extra.skill_type)"
                          >
                            {{ opt.extra.skill_type }}
                          </Tag>
                          <Tag
                            v-if="getSourceTagMeta(opt.extra?.source_plugin ?? null, Boolean(opt.extra?.is_system))"
                            :color="
                              getSourceTagMeta(
                                opt.extra?.source_plugin ?? null,
                                Boolean(opt.extra?.is_system),
                              )!.color
                            "
                            class="!m-0 !text-[11px]"
                          >
                            {{
                              getSourceTagMeta(
                                opt.extra?.source_plugin ?? null,
                                Boolean(opt.extra?.is_system),
                              )!.text
                            }}
                          </Tag>
                        </div>
                        <p
                          v-if="opt.extra?.description"
                          class="mt-2 line-clamp-2 text-xs leading-5 text-muted-foreground"
                        >
                          {{ opt.extra.description }}
                        </p>
                        <p
                          v-if="opt.extra?.skill_key"
                          class="mt-1 font-mono text-[11px] text-muted-foreground"
                        >
                          {{ opt.extra.skill_key }}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </Spin>
          </div>
          <div class="border-t border-border/70 px-4 py-3">
            <Pagination
              v-model:current="page"
              v-model:page-size="pageSize"
              :total="total"
              :show-size-changer="true"
              :page-size-options="['10', '20', '50']"
              size="small"
              :show-total="
                (value) =>
                  $t('admin.ai.agent.skillPicker.paginationTotal', {
                    count: value,
                  })
              "
              @change="onPageChange"
            />
          </div>
        </div>

        <div
          class="flex w-[min(100%,340px)] shrink-0 flex-col overflow-hidden rounded-2xl border border-border/70 bg-card"
        >
          <div class="border-b border-border/70 px-4 py-3">
            <div class="flex items-center justify-between gap-2">
              <div>
                <div class="text-sm font-semibold text-foreground">
                  {{ $t('admin.ai.agent.skillPicker.selected') }}
                </div>
                <div class="mt-1 text-xs text-muted-foreground">
                  {{
                    $t('admin.ai.agent.skillPicker.selectionSummary', {
                      skills: selectedCount,
                      packages: selectedPackageCount,
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
                <IconifyIcon icon="lucide:list-checks" class="size-6" />
              </div>
              <div class="mt-4 text-sm font-medium text-foreground">
                {{ $t('admin.ai.agent.skillPicker.emptySelected') }}
              </div>
              <div class="mt-1 max-w-[240px] text-xs leading-5 text-muted-foreground">
                {{ $t('admin.ai.agent.skillPicker.selectionHint') }}
              </div>
            </div>
            <div v-else class="flex flex-col gap-2">
              <div
                v-for="d in working"
                :key="d.skill_id"
                class="rounded-2xl border border-border/70 bg-muted/15 p-3"
              >
                <div class="flex items-start justify-between gap-2">
                  <div class="min-w-0 flex-1">
                    <div class="truncate text-sm font-medium text-foreground">
                      {{ d.skill_name }}
                    </div>
                    <div
                      v-if="d.package_name"
                      class="mt-1 truncate text-xs text-muted-foreground"
                    >
                      {{ d.package_name }}
                    </div>
                    <div class="mt-2 flex flex-wrap gap-1.5">
                      <Tag
                        v-if="d.skill_type"
                        :color="getSkillTypeColor(d.skill_type)"
                        class="!m-0 !text-[11px]"
                      >
                        {{ d.skill_type }}
                      </Tag>
                      <Tag
                        v-if="getSourceTagMeta(d.source_plugin, d.is_system)"
                        :color="getSourceTagMeta(d.source_plugin, d.is_system)!.color"
                        class="!m-0 !text-[11px]"
                      >
                        {{ getSourceTagMeta(d.source_plugin, d.is_system)!.text }}
                      </Tag>
                    </div>
                  </div>
                  <Button type="link" danger size="small" @click="removeDraft(d.skill_id)">
                    {{ $t('admin.ai.agent.skillPicker.remove') }}
                  </Button>
                </div>
                <div class="mt-3 text-[11px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
                  {{ $t('admin.ai.agent.skillPicker.defaultConsentMode') }}
                </div>
                <Select
                  class="mt-1.5 w-full"
                  size="small"
                  :value="d.default_consent_mode"
                  :options="consentOptions"
                  @update:value="(v) => setConsent(d.skill_id, v as ConsentMode)"
                />
              </div>
            </div>
          </div>
          <div class="border-t border-border/70 bg-muted/10 px-4 py-3 text-xs leading-5 text-muted-foreground">
            {{ $t('admin.ai.agent.skillPicker.replaceNotice') }}
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
