import type { ComputedRef, Ref } from 'vue';

import type { DetailTabKey, PayloadEntry } from './action-log-detail-helpers';

import type {
  ActionLogDetail,
  ActionLogItem,
} from '#/api/tenant/action-logs';
import type { ExecutionDecisionItem } from '#/api/tenant/execution-decisions';

import { computed, ref, watch } from 'vue';

import { message } from 'ant-design-vue';

import { getActionLogDetailApi } from '#/api/tenant/action-logs';
import { getExecutionDecisionDetailApi } from '#/api/tenant/execution-decisions';
import { $t } from '#/locales';
import { copyToClipboard } from '#/utils/common';

import {
  buildPayloadEntries,
  stringifyPayload,
} from './action-log-detail-helpers';

export interface ActionLogDetailController {
  activeTab: Ref<DetailTabKey>;
  copyPayload: (text: string) => Promise<void>;
  data: Ref<ActionLogDetail | null>;
  errorPayloadText: ComputedRef<string>;
  linkedDecision: Ref<ExecutionDecisionItem | null>;
  linkedDecisionLoading: Ref<boolean>;
  loading: Ref<boolean>;
  open: Ref<boolean>;
  openDetail: (row: ActionLogItem) => Promise<void>;
  requestEntries: ComputedRef<PayloadEntry[]>;
  requestPayloadText: ComputedRef<string>;
  responseEntries: ComputedRef<PayloadEntry[]>;
  responsePayloadText: ComputedRef<string>;
}

export function useActionLogDetail(): ActionLogDetailController {
  const open = ref(false);
  const loading = ref(false);
  const data = ref<ActionLogDetail | null>(null);
  const linkedDecision = ref<ExecutionDecisionItem | null>(null);
  const linkedDecisionLoading = ref(false);
  const activeTab = ref<DetailTabKey>('overview');

  function resetDetailState() {
    data.value = null;
    linkedDecision.value = null;
    linkedDecisionLoading.value = false;
    loading.value = false;
    activeTab.value = 'overview';
  }

  async function copyPayload(text: string) {
    if (!text) {
      return;
    }

    const success = await copyToClipboard(text);
    if (success) {
      message.success($t('common.copied'));
      return;
    }

    message.error($t('common.http.copyFailed'));
  }

  async function openDetailById(id: number) {
    open.value = true;
    loading.value = true;
    linkedDecision.value = null;
    linkedDecisionLoading.value = false;
    activeTab.value = 'overview';

    try {
      data.value = await getActionLogDetailApi(id);

      if (data.value?.execution_decision_id) {
        linkedDecisionLoading.value = true;
        try {
          linkedDecision.value = await getExecutionDecisionDetailApi(
            data.value.execution_decision_id,
          );
        } catch {
          linkedDecision.value = null;
        } finally {
          linkedDecisionLoading.value = false;
        }
      }

      activeTab.value = data.value?.error_message ? 'error' : 'overview';
    } catch {
      data.value = null;
      linkedDecision.value = null;
    } finally {
      loading.value = false;
    }
  }

  async function openDetail(row: ActionLogItem) {
    await openDetailById(row.id);
  }

  watch(open, (isOpen) => {
    if (!isOpen) {
      resetDetailState();
    }
  });

  const requestEntries = computed(() =>
    buildPayloadEntries(data.value?.request_data ?? null),
  );
  const responseEntries = computed(() =>
    buildPayloadEntries(data.value?.response_data ?? null),
  );
  const requestPayloadText = computed(() =>
    stringifyPayload(data.value?.request_data ?? null),
  );
  const responsePayloadText = computed(() =>
    stringifyPayload(data.value?.response_data ?? null),
  );
  const errorPayloadText = computed(
    () => data.value?.error_message?.trim() ?? '',
  );

  return {
    activeTab,
    copyPayload,
    data,
    errorPayloadText,
    linkedDecision,
    linkedDecisionLoading,
    loading,
    open,
    openDetail,
    requestEntries,
    requestPayloadText,
    responseEntries,
    responsePayloadText,
  };
}
