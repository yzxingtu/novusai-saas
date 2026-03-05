<script lang="ts" setup>
/**
 * 定时任务新建/编辑表单抽屉
 */
import type { adminApi } from '#/api';

import { computed } from 'vue';

import { useVbenForm } from '#/adapter/form';
import { getPeriodicTaskDetailApi } from '#/api/admin/periodic-task';
import { useCrudDrawer } from '#/composables';
import { $t } from '#/locales';

import { getFormDefaults, useFormSchema } from '../data';

defineOptions({ name: 'PeriodicTaskForm' });

const emits = defineEmits<{ success: [] }>();

type PeriodicTaskInfo = adminApi.PeriodicTaskInfo;

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
      scope: values.scope || 'admin_only',
      tenant_id: values.tenant_id || null,
      is_locked: values.is_locked ?? false,
      is_editable: values.is_editable ?? true,
      max_retries: values.max_retries ?? 0,
      retry_delay: values.retry_delay ?? 60,
      timeout: values.timeout ?? 3600,
      notify_on_failure: values.notify_on_failure ?? false,
      notify_emails: values.notify_emails || null,
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
      scope: data.scope,
      tenant_id: data.tenantId,
      is_locked: data.isLocked,
      is_editable: data.isEditable,
      max_retries: data.maxRetries,
      retry_delay: data.retryDelay,
      timeout: data.timeout,
      notify_on_failure: data.notifyOnFailure,
      notify_emails: data.notifyEmails,
    };
  },
  onSuccess: () => {
    emits('success');
  },
  detailApi: (id) => getPeriodicTaskDetailApi(id as number),
});

const title = computed(() =>
  isEdit.value
    ? $t('admin.system.periodicTask.edit')
    : $t('admin.system.periodicTask.create'),
);
</script>

<template>
  <Drawer :title="title" class="w-[600px]">
    <Form />
  </Drawer>
</template>
