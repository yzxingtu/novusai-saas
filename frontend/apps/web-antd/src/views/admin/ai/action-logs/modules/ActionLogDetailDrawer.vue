<script lang="ts" setup>
import type { ActionLogDetailController } from '../use-action-log-detail';

import { IconifyIcon } from '@vben/icons';

import {
  Alert,
  Avatar,
  Button,
  Card,
  Descriptions,
  Drawer,
  Empty,
  Skeleton,
  Tabs,
  Tag,
} from 'ant-design-vue';

import { IdentitySummaryCard } from '#/components/business/identity-display';
import { $t } from '#/locales';
import { formatDate } from '#/utils/common';
import IdentityTrigger from '#/views/_shared/identity/IdentityTrigger.vue';

import {
  buildOperatorMeta,
  formatDuration,
  getAgentAvatarUrl,
  getAgentDisplayName,
  getOperatorIdentityModel,
  isIconAvatar,
} from '../action-log-detail-helpers';
import {
  getExecutionDecisionStatusText,
  getExecutionDecisionTypeText,
  getLevelColor,
  getLevelText,
  getStatusColor,
  getStatusText,
  getTenantDisplay,
  getTypeColor,
  getTypeText,
} from '../data';
import ActionLogPayloadCard from './ActionLogPayloadCard.vue';

defineOptions({ name: 'ActionLogDetailDrawer' });

const props = defineProps<{
  controller: ActionLogDetailController;
}>();

const {
  activeTab,
  copyPayload,
  data,
  errorPayloadText,
  linkedDecision,
  linkedDecisionLoading,
  loading,
  open,
  requestEntries,
  requestPayloadText,
  responseEntries,
  responsePayloadText,
} = props.controller;
</script>

<template>
  <Drawer v-model:open="open" width="920">
    <template #title>
      <div class="flex flex-wrap items-center gap-2">
        <IconifyIcon icon="lucide:file-search" class="text-primary" />
        <span>{{ $t('admin.ai.actionLog.detailTitle') }}</span>
        <Tag v-if="data" :color="getStatusColor(data.status)">
          {{ getStatusText(data.status) }}
        </Tag>
      </div>
    </template>

    <div v-if="loading" class="space-y-3 p-1">
      <Skeleton active :paragraph="{ rows: 4 }" />
      <Skeleton active :paragraph="{ rows: 6 }" />
    </div>

    <template v-else-if="data">
      <div class="space-y-4">
        <Card :bordered="false" class="bg-accent/35">
          <div class="space-y-4">
            <div class="flex flex-wrap items-start justify-between gap-3">
              <div class="space-y-2">
                <div class="text-xs text-muted-foreground">
                  {{ $t('admin.ai.actionLog.summary') }}
                </div>
                <div class="flex flex-wrap items-center gap-2">
                  <IconifyIcon icon="lucide:zap" class="text-primary" />
                  <code
                    class="rounded bg-background px-2 py-1 text-sm font-semibold"
                  >
                    {{ data.action_name }}
                  </code>
                </div>
                <div class="flex flex-wrap gap-2">
                  <Tag :color="getTypeColor(data.action_type)">
                    {{ getTypeText(data.action_type) }}
                  </Tag>
                  <Tag :color="getLevelColor(data.action_level)">
                    {{ getLevelText(data.action_level) }}
                  </Tag>
                  <Tag :color="getStatusColor(data.status)">
                    {{ getStatusText(data.status) }}
                  </Tag>
                </div>
              </div>

              <Button
                size="small"
                @click="copyPayload(responsePayloadText || requestPayloadText)"
              >
                {{ $t('admin.ai.actionLog.copyPayload') }}
              </Button>
            </div>

            <div class="grid grid-cols-2 gap-3 xl:grid-cols-4">
              <div
                class="rounded-lg border border-dashed border-border bg-background p-3"
              >
                <div class="text-xs text-muted-foreground">
                  {{ $t('admin.ai.actionLog.status') }}
                </div>
                <div class="mt-2 text-sm font-semibold">
                  {{ getStatusText(data.status) }}
                </div>
              </div>
              <div
                class="rounded-lg border border-dashed border-border bg-background p-3"
              >
                <div class="text-xs text-muted-foreground">
                  {{ $t('admin.ai.actionLog.executionTime') }}
                </div>
                <div class="mt-2 text-sm font-semibold">
                  {{ formatDuration(data.duration_ms) }}
                </div>
              </div>
              <div
                class="rounded-lg border border-dashed border-border bg-background p-3"
              >
                <div class="text-xs text-muted-foreground">
                  {{ $t('admin.ai.actionLog.tenantInfo') }}
                </div>
                <div class="mt-2 text-sm font-semibold">
                  {{ getTenantDisplay(data) }}
                </div>
              </div>
              <IdentityTrigger
                class="xl:col-span-2"
                :model="getOperatorIdentityModel(data)"
                :meta="buildOperatorMeta(data)"
              >
                <template #default="{ detailRequest }">
                  <IdentitySummaryCard
                    :detail-request="detailRequest"
                    :model="getOperatorIdentityModel(data)"
                    mode="embedded"
                  />
                </template>
              </IdentityTrigger>
              <div
                class="rounded-lg border border-dashed border-border bg-background p-3"
              >
                <div class="text-xs text-muted-foreground">
                  {{ $t('admin.ai.actionLog.traceId') }}
                </div>
                <div class="mt-2 text-sm font-semibold">
                  {{ data.trace_id || '-' }}
                </div>
                <div class="mt-1 text-xs text-muted-foreground">
                  {{ data.tool_call_id || '-' }}
                </div>
              </div>
            </div>
          </div>
        </Card>

        <Tabs v-model:active-key="activeTab" size="small">
          <Tabs.TabPane
            key="overview"
            :tab="$t('admin.ai.actionLog.overviewTab')"
          >
            <div class="space-y-4">
              <Card size="small" :title="$t('admin.ai.actionLog.basicInfo')">
                <Descriptions :column="2" bordered size="small">
                  <Descriptions.Item :label="$t('admin.ai.actionLog.id')">
                    {{ data.id }}
                  </Descriptions.Item>
                  <Descriptions.Item
                    :label="$t('admin.ai.actionLog.createdAt')"
                  >
                    {{ formatDate(data.created_at) }}
                  </Descriptions.Item>
                  <Descriptions.Item
                    :label="$t('admin.ai.actionLog.actionName')"
                  >
                    <code class="rounded bg-accent px-1.5 py-0.5 text-xs">
                      {{ data.action_name }}
                    </code>
                  </Descriptions.Item>
                  <Descriptions.Item
                    :label="$t('admin.ai.actionLog.actionType')"
                  >
                    <Tag :color="getTypeColor(data.action_type)">
                      {{ getTypeText(data.action_type) }}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item
                    :label="$t('admin.ai.actionLog.actionLevel')"
                  >
                    <Tag :color="getLevelColor(data.action_level)">
                      {{ getLevelText(data.action_level) }}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item :label="$t('admin.ai.actionLog.status')">
                    <Tag :color="getStatusColor(data.status)">
                      {{ getStatusText(data.status) }}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item
                    :label="$t('admin.ai.actionLog.agentName')"
                  >
                    <div class="flex items-center gap-2">
                      <Avatar
                        v-if="getAgentAvatarUrl(data.agent_avatar)"
                        :size="24"
                        :src="getAgentAvatarUrl(data.agent_avatar) ?? undefined"
                      />
                      <span class="flex items-center gap-1.5">
                        <IconifyIcon
                          v-if="isIconAvatar(data.agent_avatar)"
                          :icon="String(data.agent_avatar)"
                          class="size-4 text-primary"
                        />
                        <IconifyIcon
                          v-else-if="!data.agent_avatar"
                          icon="lucide:bot"
                          class="size-4 text-primary"
                        />
                        <span>{{ getAgentDisplayName(data) }}</span>
                      </span>
                    </div>
                  </Descriptions.Item>
                  <Descriptions.Item
                    :label="$t('admin.ai.actionLog.tenantInfo')"
                  >
                    {{ getTenantDisplay(data) }}
                  </Descriptions.Item>
                  <Descriptions.Item :label="$t('admin.ai.actionLog.traceId')">
                    <code>{{ data.trace_id || '-' }}</code>
                  </Descriptions.Item>
                  <Descriptions.Item
                    :label="$t('admin.ai.actionLog.operatorId')"
                  >
                    <IdentityTrigger
                      :avatar-size="32"
                      :model="getOperatorIdentityModel(data)"
                      :meta="buildOperatorMeta(data)"
                      :show-status-badge="false"
                    />
                  </Descriptions.Item>
                  <Descriptions.Item
                    :label="$t('admin.ai.actionLog.toolCallId')"
                  >
                    <code>{{ data.tool_call_id || '-' }}</code>
                  </Descriptions.Item>
                  <Descriptions.Item
                    :label="$t('admin.ai.actionLog.executionDecisionId')"
                  >
                    {{ data.execution_decision_id ?? '-' }}
                  </Descriptions.Item>
                </Descriptions>
              </Card>

              <Alert
                v-if="errorPayloadText"
                show-icon
                type="error"
                :message="$t('admin.ai.actionLog.error')"
                :description="errorPayloadText"
              />

              <Card
                v-if="linkedDecision || linkedDecisionLoading"
                size="small"
                :title="$t('admin.ai.actionLog.linkedDecision')"
              >
                <div
                  v-if="linkedDecisionLoading"
                  class="flex items-center justify-center py-6"
                >
                  <Skeleton active :paragraph="{ rows: 2 }" />
                </div>
                <Descriptions
                  v-else-if="linkedDecision"
                  :column="2"
                  bordered
                  size="small"
                >
                  <Descriptions.Item
                    :label="$t('admin.ai.executionDecision.id')"
                  >
                    {{ linkedDecision.id }}
                  </Descriptions.Item>
                  <Descriptions.Item
                    :label="$t('admin.ai.executionDecision.createdAt')"
                  >
                    {{ formatDate(linkedDecision.created_at) }}
                  </Descriptions.Item>
                  <Descriptions.Item
                    :label="$t('admin.ai.executionDecision.decisionType')"
                  >
                    {{
                      getExecutionDecisionTypeText(linkedDecision.decision_type)
                    }}
                  </Descriptions.Item>
                  <Descriptions.Item
                    :label="$t('admin.ai.executionDecision.status')"
                  >
                    {{ getExecutionDecisionStatusText(linkedDecision.status) }}
                  </Descriptions.Item>
                  <Descriptions.Item
                    :label="$t('admin.ai.executionDecision.toolName')"
                  >
                    {{ linkedDecision.tool_name || '-' }}
                  </Descriptions.Item>
                  <Descriptions.Item
                    :label="$t('admin.ai.executionDecision.actionName')"
                  >
                    {{ linkedDecision.action_name || '-' }}
                  </Descriptions.Item>
                  <Descriptions.Item
                    :label="$t('admin.ai.executionDecision.correlationKey')"
                    :span="2"
                  >
                    <code>{{ linkedDecision.correlation_key }}</code>
                  </Descriptions.Item>
                </Descriptions>
              </Card>
            </div>
          </Tabs.TabPane>

          <Tabs.TabPane
            key="request"
            :tab="$t('admin.ai.actionLog.requestTab')"
          >
            <ActionLogPayloadCard
              :copy-payload="copyPayload"
              :empty-description="$t('admin.ai.actionLog.noRequestData')"
              :entries="requestEntries"
              :payload-text="requestPayloadText"
              :title="$t('admin.ai.actionLog.requestData')"
            />
          </Tabs.TabPane>

          <Tabs.TabPane
            key="response"
            :tab="$t('admin.ai.actionLog.responseTab')"
          >
            <ActionLogPayloadCard
              :copy-payload="copyPayload"
              :empty-description="$t('admin.ai.actionLog.noResponseData')"
              :entries="responseEntries"
              :payload-text="responsePayloadText"
              :title="$t('admin.ai.actionLog.responseData')"
            />
          </Tabs.TabPane>

          <Tabs.TabPane key="error" :tab="$t('admin.ai.actionLog.errorTab')">
            <Card size="small" :title="$t('admin.ai.actionLog.error')">
              <template #extra>
                <Button
                  v-if="errorPayloadText"
                  size="small"
                  type="text"
                  @click="copyPayload(errorPayloadText)"
                >
                  {{ $t('admin.ai.actionLog.copyPayload') }}
                </Button>
              </template>

              <Alert
                v-if="errorPayloadText"
                show-icon
                type="error"
                :message="$t('admin.ai.actionLog.error')"
                :description="errorPayloadText"
              />
              <Empty
                v-else
                :description="$t('admin.ai.actionLog.noErrorData')"
              />
            </Card>
          </Tabs.TabPane>
        </Tabs>
      </div>
    </template>

    <Empty v-else :description="$t('admin.ai.actionLog.noDetailData')" />
  </Drawer>
</template>
