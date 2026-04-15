import type { ComputedRef, Ref } from 'vue';

import type { DetailTabKey, PayloadEntry } from './action-log-detail-helpers';
import type {
  AdminActionLogDetail,
  AdminActionLogItem,
} from '#/api/admin/action-logs';
import type { AdminExecutionDecisionItem } from '#/api/admin/execution-decisions';

import { computed, ref, watch } from 'vue';

import { message } from 'ant-design-vue';

import { getAdminActionLogDetailApi } from '#/api/admin/action-logs';
import { getAdminExecutionDecisionDetailApi } from '#/api/admin/execution-decisions';
import { $t } from '#/locales';
import { copyToClipboard } from '#/utils/common';

import {
  buildPayloadEntries,
  stringifyPayload,
} from './action-log-detail-helpers';

export interface ActionLogDetailController {
  activeTab: Ref<DetailTabKey>;
  copyPayload: (text: string) => Promise<void>;
  data: Ref<AdminActionLogDetail | null>;
  errorPayloadText: ComputedRef<string>;
  linkedDecision: Ref<AdminExecutionDecisionItem | null>;
  linkedDecisionLoading: Ref<boolean>;
  loading: Ref<boolean>;
  open: Ref<boolean>;
  openDetail: (row: AdminActionLogItem) => Promise<void>;
  requestEntries: ComputedRef<PayloadEntry[]>;
  requestPayloadText: ComputedRef<string>;
  responseEntries: ComputedRef<PayloadEntry[]>;
  responsePayloadText: ComputedRef<string>;
}

export function useActionLogDetail(): ActionLogDetailController {
  const open = ref(false);
  const loading = ref(false);
  const data = ref<AdminActionLogDetail | null>(null);
  const linkedDecision = ref<AdminExecutionDecisionItem | null>(null);
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
      data.value = await getAdminActionLogDetailApi(id);

      if (data.value?.execution_decision_id) {
        linkedDecisionLoading.value = true;
        try {
          linkedDecision.value = await getAdminExecutionDecisionDetailApi(
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

  async function openDetail(row: AdminActionLogItem) {
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
