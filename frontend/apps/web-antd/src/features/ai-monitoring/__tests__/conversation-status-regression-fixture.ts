/* eslint-disable vue/one-component-per-file */
import type { Component } from 'vue';

import type { MonitoringConversationInfo } from '../api';

import { createApp, defineComponent, h, nextTick } from 'vue';

import {
  conversationStatusColor,
  getConversationDisplayStatus,
} from '../pages/monitoring-conversation/helpers';
import MonitoringConversationsGridCard from '../pages/monitoring-conversation/MonitoringConversationsGridCard.vue';

interface ConversationStatusRegressionState {
  activeColor: string;
  activeText: string;
  displayStatus: string;
  failedColor: string;
  failedText: string;
}

declare global {
  interface Window {
    __conversationStatusRegressionReady?: boolean;
    __conversationStatusRegressionState?: ConversationStatusRegressionState;
  }
}

const failedConversation2344: MonitoringConversationInfo = {
  actor: null,
  agent_avatar: null,
  agent_id: 59,
  agent_name: '猫娘智能体',
  call_count: 1,
  created_at: '2026-05-06T05:01:32+08:00',
  display_status: null,
  id: 2344,
  last_call_at: '2026-05-06T05:01:38+08:00',
  latest_conversation_outcome: 'failed',
  latest_error_message: 'Connection error.',
  latest_failure_kind: 'provider_unavailable',
  latest_termination_reason: 'provider_unavailable',
  latest_turn_created_at: '2026-05-06T05:01:38+08:00',
  latest_turn_error_type: 'untrusted_final_output_source',
  latest_turn_flow_terminal_status: 'error',
  latest_turn_flow_terminal_type: 'failed',
  latest_turn_outcome: 'partial',
  latest_turn_status: null,
  lifecycle_status: 'active',
  message_count: 2,
  owner_type: 'platform_admin',
  status: 'active',
  tenant_id: 0,
  tenant_name: '平台管理端',
  title: '明天北京该穿什么衣服呢？',
  total_cost: 0,
  total_tokens: 0,
  updated_at: '2026-05-06T05:01:38+08:00',
};

const activeConversation: MonitoringConversationInfo = {
  ...failedConversation2344,
  display_status: null,
  id: 2345,
  latest_conversation_outcome: null,
  latest_error_message: null,
  latest_failure_kind: null,
  latest_termination_reason: null,
  latest_turn_created_at: null,
  latest_turn_error_type: null,
  latest_turn_flow_terminal_status: null,
  latest_turn_flow_terminal_type: null,
  latest_turn_outcome: null,
  latest_turn_status: null,
  title: '正在执行的会话',
};

function createGridStub(): Component {
  return defineComponent({
    name: 'ConversationStatusGridStub',
    setup(_props, { slots }) {
      return () =>
        h('div', { 'data-testid': 'conversation-status-grid-stub' }, [
          h(
            'div',
            { 'data-testid': 'conversation-2344-status' },
            slots.status_cell?.({ row: failedConversation2344 }),
          ),
          h(
            'div',
            { 'data-testid': 'conversation-active-status' },
            slots.status_cell?.({ row: activeConversation }),
          ),
        ]);
    },
  });
}

export async function mountConversationStatusRegressionFixture(
  target: Element,
) {
  const displayStatus = getConversationDisplayStatus(failedConversation2344);
  const activeStatus = getConversationDisplayStatus(activeConversation);
  const app = createApp({
    render() {
      return h(MonitoringConversationsGridCard, {
        bodyStyle: {},
        gridComponent: createGridStub(),
        i18nPrefix: 'admin.ai.conversation',
        scope: 'admin',
      });
    },
  });
  app.mount(target);
  await nextTick();

  window.__conversationStatusRegressionState = {
    activeColor: conversationStatusColor(activeStatus),
    activeText:
      document
        .querySelector('[data-testid="conversation-active-status"]')
        ?.textContent?.trim() || '',
    displayStatus,
    failedColor: conversationStatusColor(displayStatus),
    failedText:
      document
        .querySelector('[data-testid="conversation-2344-status"]')
        ?.textContent?.trim() || '',
  };
  window.__conversationStatusRegressionReady = true;
}
