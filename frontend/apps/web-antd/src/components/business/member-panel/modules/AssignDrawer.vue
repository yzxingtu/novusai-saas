<script setup lang="ts">
import type { IdentitySelectOption } from '#/components/business/identity-display';
import type { IdentityValue } from '#/components/business/identity-display/types';

import { computed, ref } from 'vue';

import { useVbenDrawer } from '@vben/common-ui';

import { message } from 'ant-design-vue';

import { getAdminIdentitySelectApi } from '#/api/admin/users';
import { getTenantAdminIdentitySelectApi } from '#/api/tenant/admins';
import {
  IdentityRemoteSelect,
  normalizeIdentitySelectOption,
} from '#/components/business/identity-display';
import { $t } from '#/locales';

const props = withDefaults(
  defineProps<{
    addMembers: (adminIds: number[]) => Promise<boolean>;
    apiPrefix?: 'admin' | 'tenant';
    nodeId?: null | number;
  }>(),
  {
    apiPrefix: 'admin',
    nodeId: null,
  },
);

const emits = defineEmits<{ success: [] }>();

const selectedValues = ref<IdentityValue[]>([]);
const loading = ref(false);

const optionCache = ref<Map<number, IdentitySelectOption>>(new Map());

const identityApi = computed(() =>
  props.apiPrefix === 'tenant'
    ? getTenantAdminIdentitySelectApi
    : getAdminIdentitySelectApi,
);

const identityParams = computed(() => {
  const params: Record<string, unknown> = {};
  if (typeof props.nodeId === 'number') {
    params.org_node_id = props.nodeId;
  }
  return params;
});

const selectedOptions = computed<IdentitySelectOption[]>(() => {
  const ids = normalizeIdList(selectedValues.value);
  return ids
    .map((id) => optionCache.value.get(id))
    .filter((option): option is IdentitySelectOption => option !== undefined);
});

const [Drawer, drawerApi] = useVbenDrawer({
  async onConfirm() {
    if (typeof props.nodeId !== 'number') {
      message.error($t('shared.memberPanel.selectNodeFirst'));
      return;
    }
    const normalizedIds = normalizeIdList(selectedValues.value);
    if (normalizedIds.length === 0) {
      message.warning($t('shared.memberPanel.selectMemberFirst'));
      return;
    }
    loading.value = true;
    try {
      const success = await props.addMembers(normalizedIds);
      if (success) {
        emits('success');
        drawerApi.close();
      }
    } finally {
      loading.value = false;
    }
  },
  onOpenChange(isOpen) {
    if (!isOpen) {
      selectedValues.value = [];
    }
  },
});

function open() {
  drawerApi.open();
}

function mergeOptions(options: IdentitySelectOption[]) {
  if (options.length === 0) return;
  const nextCache = new Map(optionCache.value);
  for (const option of options) {
    const normalized = normalizeIdentitySelectOption(option);
    const normalizedValue = Number(normalized.value);
    if (!Number.isFinite(normalizedValue) || normalizedValue <= 0) continue;
    nextCache.set(normalizedValue, normalized);
  }
  optionCache.value = nextCache;
}

function handleOptionsLoaded(options: IdentitySelectOption[]) {
  mergeOptions(options);
}

function normalizeIdList(
  raw: IdentityValue | IdentityValue[] | null | undefined,
) {
  if (!raw) return [];
  const list = Array.isArray(raw) ? raw : [raw];
  return list
    .map((item) =>
      typeof item === 'string' ? Number.parseInt(item, 10) : Number(item),
    )
    .filter((value) => Number.isFinite(value) && value > 0);
}

defineExpose({ open });
</script>

<template>
  <Drawer
    :title="$t('shared.memberPanel.assignMembers')"
    class="w-[440px]"
    :confirm-loading="loading"
  >
    <div class="flex flex-col gap-3">
      <p class="text-sm text-gray-500">
        {{ $t('shared.memberPanel.assignHint') }}
      </p>
      <IdentityRemoteSelect
        v-model:value="selectedValues"
        :api="identityApi"
        :params="identityParams"
        mode="multiple"
        :click-pagination="true"
        :pagination="true"
        :immediate="false"
        :selected-options="selectedOptions"
        :placeholder="$t('shared.memberPanel.assignSelectPlaceholder')"
        class="w-full"
        @options-loaded="handleOptionsLoaded"
      />
    </div>
  </Drawer>
</template>
