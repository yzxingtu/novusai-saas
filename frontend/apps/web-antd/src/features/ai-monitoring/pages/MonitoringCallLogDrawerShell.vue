<script lang="ts" setup>
import type { MonitoringCallLogInfo, MonitoringScope } from '../api';

import { computed, ref, watch } from 'vue';

import { Drawer, Empty, Spin } from 'ant-design-vue';

import { getAIRuntimeRootCauseApi } from '#/api/admin/ai-runtime';
import { $t } from '#/locales';

import { getMonitoringCallLogDetail } from '../api';
import MonitoringCallLogHero from './monitoring-call-log/MonitoringCallLogHero.vue';
import MonitoringCallLogOverviewCard from './monitoring-call-log/MonitoringCallLogOverviewCard.vue';
import MonitoringCallLogPayloadCard from './monitoring-call-log/MonitoringCallLogPayloadCard.vue';
import MonitoringCallLogRootCauseCard from './monitoring-call-log/MonitoringCallLogRootCauseCard.vue';

defineOptions({ name: 'MonitoringCallLogDrawerShell' });

const props = defineProps<{
  i18nPrefix: string;
  logId: null | number;
  open: boolean;
  scope: MonitoringScope;
}>();

const emits = defineEmits<{ 'update:open': [value: boolean] }>();

const detail = ref<MonitoringCallLogInfo | null>(null);
const loading = ref(false);
const rootCauseLoading = ref(false);
const rootCausePayload = ref<null | Record<string, unknown>>(null);

const drawerTitle = computed(() =>
  props.scope === 'admin'
    ? $t('admin.ai.callLog.detail.title')
    : $t('tenant.ai.callLog.detailTitle'),
);
const summaryDescription = computed(() => $t(`${props.i18nPrefix}.pageDesc`));
const requestDataLabel = computed(() =>
  props.scope === 'admin'
    ? $t('admin.ai.callLog.detail.requestData')
    : $t(`${props.i18nPrefix}.requestData`),
);
const responseDataLabel = computed(() =>
  props.scope === 'admin'
    ? $t('admin.ai.callLog.detail.responseData')
    : $t(`${props.i18nPrefix}.responseData`),
);

watch(
  () => [props.open, props.logId] as const,
  async ([open, id]) => {
    if (!open || !id) {
      detail.value = null;
      rootCausePayload.value = null;
      return;
    }
    loading.value = true;
    try {
      detail.value = await getMonitoringCallLogDetail(props.scope, id);
      await loadRootCause();
    } finally {
      loading.value = false;
    }
  },
  { immediate: true },
);

async function loadRootCause() {
  if (props.scope !== 'admin' || !props.logId) {
    rootCausePayload.value = null;
    return;
  }
  rootCauseLoading.value = true;
  try {
    rootCausePayload.value = (await getAIRuntimeRootCauseApi({
      call_log_id: props.logId,
      trace_id: detail.value?.trace_id || undefined,
    })) as Record<string, unknown>;
  } catch {
    rootCausePayload.value = null;
  } finally {
    rootCauseLoading.value = false;
  }
}

function closeDrawer() {
  emits('update:open', false);
}
</script>

<template>
  <Drawer :open="open" :title="drawerTitle" width="860" @close="closeDrawer">
    <Spin :spinning="loading">
      <template v-if="detail">
        <MonitoringCallLogHero
          :detail="detail"
          :drawer-title="drawerTitle"
          :i18n-prefix="i18nPrefix"
          :scope="scope"
          :summary-description="summaryDescription"
        />
        <MonitoringCallLogOverviewCard
          :detail="detail"
          :drawer-title="drawerTitle"
          :i18n-prefix="i18nPrefix"
          :scope="scope"
        />
        <MonitoringCallLogRootCauseCard
          v-if="scope === 'admin'"
          :loading="rootCauseLoading"
          :payload="rootCausePayload"
          @refresh="loadRootCause"
        />

        <section
          v-if="detail.error_message"
          class="mt-4 rounded-2xl border border-destructive/30 bg-destructive/5 px-4 py-4 shadow-sm"
        >
          <div class="mb-2 text-sm font-semibold text-destructive">
            {{ $t(`${i18nPrefix}.errorMessage`) }}
          </div>
          <pre
            class="max-h-56 overflow-auto whitespace-pre-wrap rounded-xl border border-destructive/30 bg-background/80 p-3 font-mono text-xs leading-5 text-destructive"
            >{{ detail.error_message }}</pre
          >
        </section>

        <section class="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-2">
          <MonitoringCallLogPayloadCard
            icon="lucide:arrow-up-right"
            :payload="detail.request_data"
            :title="requestDataLabel"
          />
          <MonitoringCallLogPayloadCard
            icon="lucide:arrow-down-left"
            :payload="detail.response_data"
            :title="responseDataLabel"
          />
        </section>
      </template>
      <Empty v-else class="py-16" />
    </Spin>
  </Drawer>
</template>
