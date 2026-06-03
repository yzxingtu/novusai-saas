<script lang="ts" setup>
import type { MonitoringConversationDetail, MonitoringScope } from '../api';

import { computed, ref, watch } from 'vue';

import { Drawer, Spin } from 'ant-design-vue';

import { $t } from '#/locales';

import { getMonitoringConversationDetail } from '../api';
import MonitoringConversationCallTraceCard from './monitoring-conversation/MonitoringConversationCallTraceCard.vue';
import MonitoringConversationDiagnosticsCard from './monitoring-conversation/MonitoringConversationDiagnosticsCard.vue';
import MonitoringConversationHero from './monitoring-conversation/MonitoringConversationHero.vue';
import MonitoringConversationMessagesCard from './monitoring-conversation/MonitoringConversationMessagesCard.vue';
import MonitoringConversationOverviewCard from './monitoring-conversation/MonitoringConversationOverviewCard.vue';

defineOptions({ name: 'MonitoringConversationDrawerShell' });

const props = defineProps<{
  conversationId: null | number;
  i18nPrefix: string;
  open: boolean;
  scope: MonitoringScope;
}>();

const emits = defineEmits<{ 'update:open': [value: boolean] }>();

const loading = ref(false);
const detail = ref<MonitoringConversationDetail | null>(null);

watch(
  () => [props.open, props.conversationId] as const,
  async ([open, id]) => {
    if (!open || !id) {
      detail.value = null;
      return;
    }
    loading.value = true;
    try {
      detail.value = await getMonitoringConversationDetail(props.scope, id, {
        message_limit: 200,
        message_skip: 0,
      });
    } finally {
      loading.value = false;
    }
  },
  { immediate: true },
);

const drawerTitle = computed(() => $t(`${props.i18nPrefix}.detailTitle`));

function closeDrawer() {
  emits('update:open', false);
}
</script>

<template>
  <Drawer
    class="monitoring-conversation-drawer"
    :open="open"
    :title="drawerTitle"
    :body-style="{
      background:
        'linear-gradient(180deg, hsl(var(--background)) 0%, hsl(var(--card)) 100%)',
      padding: '20px',
    }"
    width="980"
    @close="closeDrawer"
  >
    <Spin :spinning="loading">
      <template v-if="detail">
        <MonitoringConversationHero
          :detail="detail"
          :i18n-prefix="i18nPrefix"
          :scope="scope"
        />

        <MonitoringConversationOverviewCard
          :detail="detail"
          :i18n-prefix="i18nPrefix"
          :scope="scope"
        />

        <MonitoringConversationDiagnosticsCard
          :detail="detail"
          :i18n-prefix="i18nPrefix"
        />

        <div class="mt-4 grid grid-cols-1 gap-4 2xl:grid-cols-2">
          <MonitoringConversationMessagesCard
            :i18n-prefix="i18nPrefix"
            :messages="detail.message_list"
            :scope="scope"
          />
          <MonitoringConversationCallTraceCard
            :call-trace="detail.call_trace"
            :i18n-prefix="i18nPrefix"
          />
        </div>
      </template>
    </Spin>
  </Drawer>
</template>

<style
  src="./monitoring-conversation/monitoring-conversation-drawer.css"
></style>
