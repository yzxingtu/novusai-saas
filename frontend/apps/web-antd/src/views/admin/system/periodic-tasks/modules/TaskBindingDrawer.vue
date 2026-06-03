<script lang="ts" setup>
import type { TaskBindingOverrideDraft } from './binding-overrides';

import type {
  PeriodicTaskBindingInfo,
  PeriodicTaskBindingSyncItemPayload,
} from '#/api/admin/periodic-task';
import type { TenantSelectOption } from '#/api/admin/tenant';

import { computed, ref, watch } from 'vue';

import { useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Alert, Button, message, Spin, Tag } from 'ant-design-vue';

import {
  getPeriodicTaskBindingsApi,
  syncPeriodicTaskBindingsApi,
  updatePeriodicTaskBindingApi,
} from '#/api/admin/periodic-task';
import { getTenantSelectApi } from '#/api/admin/tenant';
import { ApiSelect } from '#/components/business/api-select';
import { $t } from '#/locales';
import {
  getAdminScopeOptions,
  getScopeColor,
  getScopeIcon,
  getScopeText,
} from '#/utils/scope-helpers';

import {
  getAdminSurfaceSummary,
  getDistributionHeadline,
  getGovernanceSummary,
  getTenantSurfaceSummary,
  normalizeScopeValue,
  scopeNeedsExplicitBindings,
} from '../data';
import {
  reconcileBindingOverrideDrafts,
  toBindingOverridePayload,
} from './binding-overrides';
import TaskBindingOverridesPanel from './TaskBindingOverridesPanel.vue';

defineOptions({ name: 'TaskBindingDrawer' });

const emit = defineEmits<{ success: [] }>();

type BindingScope =
  | 'admin_and_selected_tenants'
  | 'admin_only'
  | 'all_tenants'
  | 'global_shared'
  | 'selected_tenants';

type ApiSelectValue = Array<number | string> | number | string | undefined;

type TenantOption = {
  extra?: null | Record<string, unknown>;
  label: string;
  value: number | string;
};

type TenantOptionResponse = {
  [key: string]: unknown;
  items: TenantOption[];
};

const emitSuccess = () => emit('success');

const taskId = ref<null | number>(null);
const taskName = ref('');
const originalScope = ref<BindingScope>('admin_only');
const bindingScope = ref<BindingScope>('admin_only');
const selectedTenantIds = ref<number[]>([]);
const cachedTenantOptions = ref<TenantOption[]>([]);
const loadedBindings = ref<PeriodicTaskBindingInfo[]>([]);
const bindingDrafts = ref<TaskBindingOverrideDraft[]>([]);
const loading = ref(false);
const saving = ref(false);
const savingTenantId = ref<null | number>(null);
const tenantSelectParams = Object.freeze({ is_active: 'true' });

function toBindingScope(scope: null | string | undefined): BindingScope {
  const normalizedScope = normalizeScopeValue(scope);
  switch (normalizedScope) {
    case 'admin_and_selected_tenants':
    case 'admin_only':
    case 'all_tenants':
    case 'global_shared':
    case 'selected_tenants': {
      return normalizedScope;
    }
    default: {
      return 'admin_only';
    }
  }
}

function normalizeTenantId(value: number | string): null | number {
  const normalized = Number(value);
  return Number.isFinite(normalized) ? normalized : null;
}

function mergeTenantOptions(...groups: TenantOption[][]): TenantOption[] {
  const tenantMap = new Map<number, TenantOption>();

  for (const group of groups) {
    for (const option of group) {
      const tenantId = normalizeTenantId(option.value);
      if (tenantId === null) {
        continue;
      }
      tenantMap.set(tenantId, {
        ...option,
        value: tenantId,
      });
    }
  }

  return [...tenantMap.values()];
}

function toTenantOption(option: TenantSelectOption): TenantOption {
  return {
    ...option,
    extra: option.extra ? { ...option.extra } : option.extra,
  };
}

async function loadTenantSelectOptions(
  params: Record<string, unknown>,
): Promise<TenantOptionResponse> {
  const response = await getTenantSelectApi(params);
  return {
    ...response,
    items: response.items.map((item) => toTenantOption(item)),
  };
}

function buildTenantOptions(
  ids: number[] | undefined,
  names: Array<null | string> | undefined,
): TenantOption[] {
  if (!ids?.length || !names?.length) {
    return [];
  }

  const options: TenantOption[] = [];
  for (const [index, tenantId] of ids.entries()) {
    const label = names[index];
    if (!label) {
      continue;
    }
    options.push({
      label,
      value: tenantId,
    });
  }

  return options;
}

const scopeOptions = computed(() => {
  return getAdminScopeOptions().map((item) => ({
    color: getScopeColor(item.value),
    headline: getDistributionHeadline(item.value),
    icon: getScopeIcon(item.value),
    label: item.label,
    summary: getGovernanceSummary(item.value),
    value: item.value as BindingScope,
  }));
});

const requiresExplicitBindings = computed(() => {
  return scopeNeedsExplicitBindings(bindingScope.value);
});

const selectedBindingCount = computed(() => selectedTenantIds.value.length);

const hasPendingBindings = computed(() => {
  return requiresExplicitBindings.value && selectedBindingCount.value === 0;
});

const bindingStatusText = computed(() => {
  if (!requiresExplicitBindings.value) {
    return '';
  }
  if (hasPendingBindings.value) {
    return $t('admin.system.periodicTask.bindingSummary.pending');
  }
  return $t('admin.system.periodicTask.bindingSummary.selectedCount', {
    count: selectedBindingCount.value,
  });
});

const currentScopeHeadline = computed(() => {
  return getDistributionHeadline(bindingScope.value);
});

const governanceSummary = computed(() => {
  return getGovernanceSummary(bindingScope.value);
});

const adminSurfaceSummary = computed(() => {
  return getAdminSurfaceSummary(bindingScope.value);
});

const tenantSurfaceSummary = computed(() => {
  if (hasPendingBindings.value) {
    return $t('admin.system.periodicTask.tenantSurface.pending');
  }
  return getTenantSurfaceSummary(
    bindingScope.value,
    selectedBindingCount.value,
  );
});

const tenantSectionHelp = computed(() => {
  if (bindingScope.value === 'all_tenants') {
    return $t('admin.system.periodicTask.bindingTenantHelpAllTenantsOptOut');
  }
  return requiresExplicitBindings.value
    ? $t('admin.system.periodicTask.bindingTenantHelpSelected')
    : $t('admin.system.periodicTask.bindingTenantHelpGlobal');
});

const shouldShowOverrides = computed(() => {
  return (
    (requiresExplicitBindings.value || bindingScope.value === 'all_tenants') &&
    selectedTenantIds.value.length > 0
  );
});

const bindingOverrideDefaultEnabled = computed(() => {
  return bindingScope.value !== 'all_tenants';
});

const tenantSelectionValue = computed<ApiSelectValue>({
  get: () => selectedTenantIds.value,
  set: (value) => {
    if (!Array.isArray(value)) {
      selectedTenantIds.value = [];
      return;
    }

    selectedTenantIds.value = value
      .map((item) => normalizeTenantId(item))
      .filter((item): item is number => item !== null);
  },
});

const [Drawer, drawerApi] = useVbenDrawer({
  async onOpenChange(isOpen: boolean) {
    if (!isOpen) return;

    const data = drawerApi.getData<{
      assignedTenantIds?: number[];
      assignedTenantNames?: string[];
      id: number;
      name: string;
      scope?: null | string;
    }>();
    if (!data) return;

    const normalizedScope = toBindingScope(data.scope);
    taskId.value = data.id;
    taskName.value = data.name;
    originalScope.value = normalizedScope;
    bindingScope.value = normalizedScope;
    selectedTenantIds.value = scopeNeedsExplicitBindings(normalizedScope)
      ? [...(data.assignedTenantIds ?? [])]
      : [];
    cachedTenantOptions.value = buildTenantOptions(
      data.assignedTenantIds,
      data.assignedTenantNames,
    );
    loadedBindings.value = [];
    bindingDrafts.value = [];

    await loadData();
  },
});

watch([selectedTenantIds, cachedTenantOptions], () => {
  syncBindingDrafts();
});

async function loadData() {
  if (!taskId.value) return;

  loading.value = true;
  try {
    const bindingItems = await getPeriodicTaskBindingsApi(taskId.value);
    loadedBindings.value = bindingItems;

    cachedTenantOptions.value = mergeTenantOptions(
      cachedTenantOptions.value,
      bindingItems.map((item) => ({
        label: item.tenantName || `#${item.tenantId}`,
        value: item.tenantId,
      })),
    );

    if (
      scopeNeedsExplicitBindings(originalScope.value) ||
      originalScope.value === 'all_tenants'
    ) {
      selectedTenantIds.value = bindingItems.map((item) => item.tenantId);
    }
    syncBindingDrafts();
  } finally {
    loading.value = false;
  }
}

function handleTenantOptionsLoaded(options: TenantOption[]) {
  cachedTenantOptions.value = mergeTenantOptions(
    cachedTenantOptions.value,
    options,
  );
}

function syncBindingDrafts() {
  if (!requiresExplicitBindings.value && bindingScope.value !== 'all_tenants') {
    bindingDrafts.value = [];
    return;
  }
  bindingDrafts.value = reconcileBindingOverrideDrafts(
    bindingDrafts.value,
    selectedTenantIds.value,
    cachedTenantOptions.value,
    loadedBindings.value,
    bindingOverrideDefaultEnabled.value,
  );
}

function updateBindingDraft(
  tenantId: number,
  patch: Partial<TaskBindingOverrideDraft>,
) {
  bindingDrafts.value = bindingDrafts.value.map((draft) =>
    draft.tenantId === tenantId ? { ...draft, ...patch } : draft,
  );
}

function resolveBindingPayloads() {
  const payloads: PeriodicTaskBindingSyncItemPayload[] = [];
  const errorFields = new Set<'config' | 'kwargs'>();
  for (const draft of bindingDrafts.value) {
    const result = toBindingOverridePayload(draft);
    payloads.push(result.payload);
    for (const error of result.errors) {
      errorFields.add(error);
    }
  }
  return { errorFields, payloads };
}

function showJsonError(errorFields: Set<'config' | 'kwargs'>): boolean {
  if (errorFields.size === 0) {
    return false;
  }
  const field = errorFields.has('kwargs')
    ? $t('admin.system.periodicTask.bindingOverride.kwargsOverride')
    : $t('admin.system.periodicTask.bindingOverride.configOverride');
  message.error(
    $t('admin.system.periodicTask.messages.bindingJsonInvalid', { field }),
  );
  return true;
}

async function onSaveTenant(draft: TaskBindingOverrideDraft) {
  if (!taskId.value) return;

  const result = toBindingOverridePayload(draft);
  if (showJsonError(new Set(result.errors))) {
    return;
  }

  savingTenantId.value = draft.tenantId;
  try {
    const updated = await updatePeriodicTaskBindingApi(
      taskId.value,
      draft.tenantId,
      result.payload,
    );
    loadedBindings.value = [
      ...loadedBindings.value.filter(
        (item) => item.tenantId !== draft.tenantId,
      ),
      updated,
    ];
    syncBindingDrafts();
    message.success(
      $t('admin.system.periodicTask.messages.bindingTenantSaveSuccess'),
    );
  } finally {
    savingTenantId.value = null;
  }
}

async function onSave() {
  if (!taskId.value) return;
  if (requiresExplicitBindings.value && selectedTenantIds.value.length === 0) {
    message.warning($t('admin.system.periodicTask.messages.bindingMissing'));
    return;
  }

  const { errorFields, payloads } = resolveBindingPayloads();
  if (showJsonError(errorFields)) {
    return;
  }

  saving.value = true;
  try {
    await syncPeriodicTaskBindingsApi(taskId.value, {
      scope: bindingScope.value,
      tenant_ids: selectedTenantIds.value,
      bindings: shouldShowOverrides.value ? payloads : [],
    });
    message.success(
      $t('admin.system.periodicTask.messages.bindingSaveSuccess'),
    );
    emitSuccess();
    drawerApi.close();
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <Drawer
    :title="
      $t('admin.system.periodicTask.bindingTitle', {
        name: taskName,
      })
    "
    class="w-[720px]"
  >
    <Spin :spinning="loading">
      <div class="flex flex-col gap-4">
        <section
          class="rounded-2xl border border-slate-200 bg-gradient-to-br from-slate-50 via-white to-cyan-50 px-5 py-5"
        >
          <div
            class="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400"
          >
            {{ $t('admin.system.periodicTask.bindingEyebrow') }}
          </div>
          <div class="mt-3 flex flex-wrap items-center gap-2">
            <Tag :color="getScopeColor(bindingScope)">
              <div class="flex items-center gap-1">
                <IconifyIcon
                  :icon="getScopeIcon(bindingScope)"
                  class="size-3"
                />
                {{ getScopeText(bindingScope) }}
              </div>
            </Tag>
            <Tag
              v-if="requiresExplicitBindings"
              :color="hasPendingBindings ? 'gold' : 'blue'"
            >
              {{ bindingStatusText }}
            </Tag>
          </div>
          <div class="mt-3 text-base font-semibold text-slate-900">
            {{ currentScopeHeadline }}
          </div>
          <div class="mt-2 text-sm leading-6 text-slate-600">
            {{ $t('admin.system.periodicTask.bindingDescription') }}
          </div>
        </section>

        <Alert
          :message="
            hasPendingBindings
              ? $t('admin.system.periodicTask.bindingWarning')
              : $t('admin.system.periodicTask.bindingAlertTitle')
          "
          :description="
            requiresExplicitBindings
              ? $t('admin.system.periodicTask.bindingAlertSelected')
              : $t('admin.system.periodicTask.bindingAlertGlobal')
          "
          :type="hasPendingBindings ? 'warning' : 'info'"
          show-icon
        />

        <section class="rounded-2xl border border-slate-200 bg-white px-4 py-4">
          <div class="text-sm font-semibold text-slate-900">
            {{ $t('admin.system.periodicTask.bindingModeTitle') }}
          </div>
          <div class="mt-1 text-xs leading-5 text-slate-500">
            {{ governanceSummary }}
          </div>

          <div class="mt-4 grid gap-3">
            <button
              v-for="option in scopeOptions"
              :key="option.value"
              type="button"
              class="rounded-2xl border px-4 py-4 text-left transition"
              :class="
                bindingScope === option.value
                  ? 'border-sky-500 bg-sky-50 shadow-[0_0_0_1px_rgba(14,165,233,0.18)]'
                  : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50'
              "
              @click="bindingScope = option.value"
            >
              <div class="flex items-start gap-3">
                <div
                  class="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-xl bg-slate-100"
                >
                  <IconifyIcon
                    :icon="option.icon"
                    class="size-4"
                    :class="
                      bindingScope === option.value
                        ? 'text-sky-600'
                        : 'text-slate-500'
                    "
                  />
                </div>
                <div class="min-w-0 flex-1">
                  <div class="flex flex-wrap items-center gap-2">
                    <span class="text-sm font-semibold text-slate-900">
                      {{ option.label }}
                    </span>
                    <Tag
                      :color="option.color"
                      class="!m-0 !px-1 !text-[10px] !leading-4"
                    >
                      {{ option.headline }}
                    </Tag>
                  </div>
                  <div class="mt-2 text-xs leading-5 text-slate-500">
                    {{ option.summary }}
                  </div>
                </div>
              </div>
            </button>
          </div>
        </section>

        <section class="rounded-2xl border border-slate-200 bg-white px-4 py-4">
          <div class="text-sm font-semibold text-slate-900">
            {{ $t('admin.system.periodicTask.distributionGovernanceTitle') }}
          </div>
          <div class="mt-4 grid gap-3 md:grid-cols-3">
            <div class="rounded-2xl bg-slate-50 px-4 py-3">
              <div class="text-xs font-medium text-slate-500">
                {{ $t('admin.system.periodicTask.bindingCard.currentScope') }}
              </div>
              <div class="mt-2 text-sm font-semibold text-slate-900">
                {{ getScopeText(bindingScope) }}
              </div>
              <div class="mt-2 text-xs leading-5 text-slate-500">
                {{ governanceSummary }}
              </div>
            </div>

            <div class="rounded-2xl bg-slate-50 px-4 py-3">
              <div class="text-xs font-medium text-slate-500">
                {{ $t('admin.system.periodicTask.bindingCard.adminSurface') }}
              </div>
              <div class="mt-2 text-sm font-semibold text-slate-900">
                {{ adminSurfaceSummary }}
              </div>
            </div>

            <div class="rounded-2xl bg-slate-50 px-4 py-3">
              <div class="text-xs font-medium text-slate-500">
                {{ $t('admin.system.periodicTask.bindingCard.tenantSurface') }}
              </div>
              <div class="mt-2 text-sm font-semibold text-slate-900">
                {{ tenantSurfaceSummary }}
              </div>
            </div>
          </div>
        </section>

        <section class="rounded-2xl border border-slate-200 bg-white px-4 py-4">
          <div class="text-sm font-semibold text-slate-900">
            {{ $t('admin.system.periodicTask.bindingTenantTitle') }}
          </div>
          <div class="mt-1 text-xs leading-5 text-slate-500">
            {{ tenantSectionHelp }}
          </div>

          <ApiSelect
            v-model:value="tenantSelectionValue"
            class="mt-4 w-full"
            mode="multiple"
            :options="cachedTenantOptions"
            :api="loadTenantSelectOptions"
            :params="tenantSelectParams"
            result-field="items"
            option-right-field="extra.code"
            :pagination="true"
            :click-pagination="true"
            :page-size="20"
            :disabled="
              !(requiresExplicitBindings || bindingScope === 'all_tenants')
            "
            max-tag-count="responsive"
            :placeholder="
              $t('admin.system.periodicTask.placeholder.selectTenant')
            "
            @options-loaded="handleTenantOptionsLoaded"
          />

          <div
            v-if="!requiresExplicitBindings && bindingScope !== 'all_tenants'"
            class="mt-3 text-xs leading-5 text-slate-500"
          >
            {{ $t('admin.system.periodicTask.bindingGlobalNote') }}
          </div>
        </section>

        <TaskBindingOverridesPanel
          v-if="shouldShowOverrides"
          :drafts="bindingDrafts"
          :disabled="saving"
          :deny-only="bindingScope === 'all_tenants'"
          :saving-tenant-id="savingTenantId"
          @update-draft="updateBindingDraft"
          @save-tenant="onSaveTenant"
        />

        <div class="flex justify-end gap-3">
          <Button @click="drawerApi.close()">
            {{ $t('common.cancel') }}
          </Button>
          <Button type="primary" :loading="saving" @click="onSave">
            {{ $t('common.save') }}
          </Button>
        </div>
      </div>
    </Spin>
  </Drawer>
</template>
