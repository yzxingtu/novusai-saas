<script lang="ts" setup>
import type { tenantApi } from '#/api';

import { computed } from 'vue';

import { useVbenForm } from '#/adapter/form';
import { getPeriodicTaskDetailApi } from '#/api/tenant/periodic-task';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';

import { getFormDefaults, useFormSchema } from '../data';

defineOptions({ name: 'TenantPeriodicTaskForm' });

const emits = defineEmits<{ success: [] }>();

type PeriodicTaskInfo = tenantApi.PeriodicTaskInfo;

const [Form, formApi] = useVbenForm({
  schema: useFormSchema(false),
  showDefaultActions: false,
});

const { Drawer, isEdit } = useCrudDrawer<PeriodicTaskInfo>({
  formApi,
  schema: useFormSchema,
  defaults: getFormDefaults,
  transform: (values) => {
    return {
      name: values.name,
      task_path: values.task_path,
      schedule_type: values.schedule_type,
      cron_expression: values.cron_expression || null,
      interval_seconds: values.interval_seconds || null,
      is_active: values.is_active ?? true,
      description: values.description || null,
    };
  },
  toFormValues: (data) => {
    return {
      name: data.name,
      task_path: data.taskPath,
      schedule_type: data.scheduleType,
      cron_expression: data.cronExpression,
      interval_seconds: data.intervalSeconds,
      is_active: data.isActive,
      description: data.description,
    };
  },
  onSuccess: () => {
    emits('success');
  },
  detailApi: (id) => getPeriodicTaskDetailApi(id as number),
});

const title = computed(() =>
  isEdit.value
    ? $t('tenant.system.periodicTask.edit')
    : $t('tenant.system.periodicTask.create'),
);
</script>

<template>
  <Drawer :title="title" class="w-[600px]">
    <Form />
  </Drawer>
</template>
