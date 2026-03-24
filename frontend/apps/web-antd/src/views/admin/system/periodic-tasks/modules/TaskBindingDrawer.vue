<script lang="ts" setup>
import { ref } from 'vue';

import { useVbenDrawer } from '@vben/common-ui';

import { Button, Select, Spin, message } from 'ant-design-vue';

import {
  getPeriodicTaskBindingsApi,
  syncPeriodicTaskBindingsApi,
} from '#/api/admin/periodic-task';
import { getTenantSelectApi } from '#/api/admin/tenant';
import { $t } from '#/locales';

defineOptions({ name: 'TaskBindingDrawer' });

const emit = defineEmits<{ success: [] }>();

const taskId = ref<number | null>(null);
const taskName = ref('');
const tenantOptions = ref<Array<{ label: string; value: number }>>([]);
const selectedTenantIds = ref<number[]>([]);
const loading = ref(false);
const saving = ref(false);

const [Drawer, drawerApi] = useVbenDrawer({
  async onOpenChange(isOpen: boolean) {
    if (!isOpen) return;
    const data = drawerApi.getData<{ id: number; name: string }>();
    if (!data) return;
    taskId.value = data.id;
    taskName.value = data.name;
    await loadData();
  },
});

async function loadData() {
  if (!taskId.value) return;
  loading.value = true;
  try {
    const [bindingItems, tenantResult] = await Promise.all([
      getPeriodicTaskBindingsApi(taskId.value),
      getTenantSelectApi({ is_active: 'true', page: 1, page_size: 500 }),
    ]);
    selectedTenantIds.value = bindingItems
      .filter((item) => item.is_enabled)
      .map((item) => item.tenant_id);
    tenantOptions.value = tenantResult.items.map((item) => ({
      label: item.label,
      value: item.value,
    }));
  } finally {
    loading.value = false;
  }
}

async function onSave() {
  if (!taskId.value) return;
  saving.value = true;
  try {
    await syncPeriodicTaskBindingsApi(taskId.value, selectedTenantIds.value);
    message.success($t('admin.system.periodicTask.messages.bindingSaveSuccess'));
    emit('success');
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
    class="w-[520px]"
  >
    <Spin :spinning="loading">
      <div class="flex flex-col gap-4">
        <div class="text-sm text-muted-foreground">
          {{ $t('admin.system.periodicTask.bindingHelp') }}
        </div>

        <Select
          v-model:value="selectedTenantIds"
          mode="multiple"
          :options="tenantOptions"
          class="w-full"
          :placeholder="$t('admin.system.periodicTask.placeholder.selectTenant')"
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
