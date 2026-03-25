<script lang="ts" setup>
import { computed, ref } from 'vue';

import { useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Alert, Button, Spin, Tag, message } from 'ant-design-vue';

import {
  getPeriodicTaskBindingsApi,
  syncPeriodicTaskBindingsApi,
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
  extra?: null | Record<string, any>;
  label: string;
  value: number | string;
};

const emitSuccess = () => emit('success');

const taskId = ref<number | null>(null);
const taskName = ref('');
const originalScope = ref<BindingScope>('admin_only');
const bindingScope = ref<BindingScope>('admin_only');
const selectedTenantIds = ref<number[]>([]);
const cachedTenantOptions = ref<TenantOption[]>([]);
const loading = ref(false);
const saving = ref(false);
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

function normalizeTenantId(value: number | string): number | null {
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
  return requiresExplicitBindings.value
    ? $t('admin.system.periodicTask.bindingTenantHelpSelected')
    : $t('admin.system.periodicTask.bindingTenantHelpGlobal');
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

    await loadData();
  },
});

async function loadData() {
  if (!taskId.value) return;

  loading.value = true;
  try {
    const bindingItems = await getPeriodicTaskBindingsApi(taskId.value);
    const activeBindings = bindingItems.filter((item) => item.is_enabled);

    cachedTenantOptions.value = mergeTenantOptions(
      cachedTenantOptions.value,
      activeBindings.map((item) => ({
        label: item.tenant_name || `#${item.tenant_id}`,
        value: item.tenant_id,
      })),
    );

    if (scopeNeedsExplicitBindings(originalScope.value)) {
      selectedTenantIds.value = activeBindings.map((item) => item.tenant_id);
    }
  } finally {
    loading.value = false;
  }
}

function handleTenantOptionsLoaded(
  options: Array<{
    extra?: null | Record<string, any>;
    label: string;
    value: number | string;
  }>,
) {
  cachedTenantOptions.value = mergeTenantOptions(
    cachedTenantOptions.value,
    options,
  );
}

async function onSave() {
  if (!taskId.value) return;

  saving.value = true;
  try {
    await syncPeriodicTaskBindingsApi(taskId.value, {
      scope: bindingScope.value,
      tenant_ids: selectedTenantIds.value,
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
            :api="getTenantSelectApi"
            :params="tenantSelectParams"
            result-field="items"
            option-right-field="extra.code"
            :pagination="true"
            :click-pagination="true"
            :page-size="20"
            :disabled="!requiresExplicitBindings"
            :max-tag-count="'responsive'"
            :placeholder="
              $t('admin.system.periodicTask.placeholder.selectTenant')
            "
            @options-loaded="handleTenantOptionsLoaded"
          />

          <div
            v-if="!requiresExplicitBindings"
            class="mt-3 text-xs leading-5 text-slate-500"
          >
            {{ $t('admin.system.periodicTask.bindingGlobalNote') }}
          </div>
        </section>

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
