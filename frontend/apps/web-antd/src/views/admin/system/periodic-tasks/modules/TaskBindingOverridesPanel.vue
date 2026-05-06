<script lang="ts" setup>
import type { TaskBindingOverrideDraft } from './binding-overrides';

import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Input,
  InputNumber,
  Select,
  Switch,
  Tag,
} from 'ant-design-vue';

import { $t } from '#/locales';

defineOptions({ name: 'TaskBindingOverridesPanel' });

defineProps<{
  disabled?: boolean;
  drafts: TaskBindingOverrideDraft[];
  denyOnly?: boolean;
  savingTenantId?: null | number;
}>();

const emit = defineEmits<{
  saveTenant: [draft: TaskBindingOverrideDraft];
  updateDraft: [tenantId: number, patch: Partial<TaskBindingOverrideDraft>];
}>();

const scheduleOverrideOptions = computed(() => [
  {
    label: $t('admin.system.periodicTask.bindingOverride.inheritSchedule'),
    value: '',
  },
  {
    label: $t('admin.system.periodicTask.scheduleType.cron'),
    value: 'cron',
  },
  {
    label: $t('admin.system.periodicTask.scheduleType.interval'),
    value: 'interval',
  },
]);

function patchDraft(
  tenantId: number,
  patch: Partial<TaskBindingOverrideDraft>,
) {
  emit('updateDraft', tenantId, patch);
}

function getEffectiveScheduleText(draft: TaskBindingOverrideDraft): string {
  const scheduleType =
    draft.scheduleTypeOverride || draft.effectiveScheduleType || '';
  if (scheduleType === 'cron') {
    return (
      draft.cronExpressionOverride ||
      draft.effectiveCronExpression ||
      $t('admin.system.periodicTask.bindingOverride.inheritSchedule')
    );
  }
  if (scheduleType === 'interval') {
    const interval =
      draft.intervalSecondsOverride ?? draft.effectiveIntervalSeconds;
    return interval
      ? $t('admin.system.periodicTask.bindingOverride.intervalPreview', {
          seconds: interval,
        })
      : $t('admin.system.periodicTask.bindingOverride.inheritSchedule');
  }
  return $t('admin.system.periodicTask.bindingOverride.inheritSchedule');
}
</script>

<template>
  <section class="rounded-2xl border border-slate-200 bg-white px-4 py-4">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div>
        <div class="text-sm font-semibold text-slate-900">
          {{ $t('admin.system.periodicTask.bindingOverride.title') }}
        </div>
        <div class="mt-1 text-xs leading-5 text-slate-500">
          {{ $t('admin.system.periodicTask.bindingOverride.help') }}
        </div>
      </div>
      <Tag color="blue">
        {{
          $t('admin.system.periodicTask.bindingOverride.count', {
            count: drafts.length,
          })
        }}
      </Tag>
    </div>

    <div class="mt-4 flex flex-col gap-3">
      <div
        v-for="draft in drafts"
        :key="draft.tenantId"
        class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4"
      >
        <div class="flex flex-wrap items-center justify-between gap-3">
          <div class="min-w-0">
            <div class="flex flex-wrap items-center gap-2">
              <span class="text-sm font-semibold text-slate-900">
                {{ draft.tenantName }}
              </span>
              <Tag class="!m-0" color="default">#{{ draft.tenantId }}</Tag>
              <Tag :color="draft.isEnabled ? 'green' : 'red'" class="!m-0">
                {{
                  draft.isEnabled
                    ? $t('admin.system.periodicTask.status.enabled')
                    : $t('admin.system.periodicTask.status.disabled')
                }}
              </Tag>
            </div>
            <div class="mt-1 text-xs leading-5 text-slate-500">
              {{
                $t('admin.system.periodicTask.bindingOverride.effective', {
                  value: getEffectiveScheduleText(draft),
                })
              }}
            </div>
          </div>

          <Button
            size="small"
            :disabled="disabled"
            :loading="savingTenantId === draft.tenantId"
            @click="emit('saveTenant', draft)"
          >
            <template #icon>
              <IconifyIcon icon="lucide:save" />
            </template>
            {{ $t('admin.system.periodicTask.bindingOverride.saveTenant') }}
          </Button>
        </div>

        <div class="mt-4 grid gap-3 md:grid-cols-2">
          <label class="flex items-center gap-2 text-xs text-slate-600">
            <Switch
              :checked="draft.isEnabled"
              :disabled="disabled || denyOnly"
              @change="
                (checked) =>
                  patchDraft(draft.tenantId, {
                    isEnabled: Boolean(checked),
                  })
              "
            />
            {{ $t('admin.system.periodicTask.bindingOverride.enabled') }}
          </label>

          <Input
            v-if="!draft.isEnabled"
            :value="draft.disabledReason"
            :disabled="disabled"
            :placeholder="
              $t('admin.system.periodicTask.bindingOverride.disableReason')
            "
            @change="
              (event) =>
                patchDraft(draft.tenantId, {
                  disabledReason: event.target.value,
                })
            "
          />

          <Select
            :value="draft.scheduleTypeOverride ?? ''"
            :disabled="disabled || denyOnly"
            :options="scheduleOverrideOptions"
            @change="
              (value) =>
                patchDraft(draft.tenantId, {
                  scheduleTypeOverride: value ? String(value) : null,
                })
            "
          />

          <Input
            v-if="draft.scheduleTypeOverride === 'cron'"
            :value="draft.cronExpressionOverride"
            :disabled="disabled || denyOnly"
            :placeholder="$t('admin.system.periodicTask.placeholder.inputCron')"
            @change="
              (event) =>
                patchDraft(draft.tenantId, {
                  cronExpressionOverride: event.target.value,
                })
            "
          />

          <InputNumber
            v-if="draft.scheduleTypeOverride === 'interval'"
            class="w-full"
            :value="draft.intervalSecondsOverride ?? undefined"
            :disabled="disabled || denyOnly"
            :min="10"
            :placeholder="
              $t('admin.system.periodicTask.placeholder.inputInterval')
            "
            @change="
              (value) =>
                patchDraft(draft.tenantId, {
                  intervalSecondsOverride:
                    typeof value === 'number' ? value : null,
                })
            "
          />
        </div>

        <div class="mt-3 grid gap-3 md:grid-cols-2">
          <Input.TextArea
            :value="draft.kwargsOverrideText"
            :disabled="disabled || denyOnly"
            :rows="3"
            data-input-ai-assist="off"
            :placeholder="
              $t('admin.system.periodicTask.bindingOverride.kwargsOverride')
            "
            @change="
              (event) =>
                patchDraft(draft.tenantId, {
                  kwargsOverrideText: event.target.value,
                })
            "
          />
          <Input.TextArea
            :value="draft.configOverrideText"
            :disabled="disabled || denyOnly"
            :rows="3"
            data-input-ai-assist="off"
            :placeholder="
              $t('admin.system.periodicTask.bindingOverride.configOverride')
            "
            @change="
              (event) =>
                patchDraft(draft.tenantId, {
                  configOverrideText: event.target.value,
                })
            "
          />
        </div>
      </div>
    </div>
  </section>
</template>
