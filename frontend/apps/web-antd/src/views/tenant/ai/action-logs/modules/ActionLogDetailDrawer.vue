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
  getInitialLetter,
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
        <span>{{ $t('tenant.ai.actionLog.detailTitle') }}</span>
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
                  {{ $t('tenant.ai.actionLog.summary') }}
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
                {{ $t('tenant.ai.actionLog.copyPayload') }}
              </Button>
            </div>

            <div class="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-2">
              <article
                class="rounded-xl border border-border/70 bg-background/80 px-3 py-3 shadow-sm"
              >
                <div class="text-xs text-muted-foreground">
                  {{ $t('tenant.ai.actionLog.agentName') }}
                </div>
                <div class="mt-2 flex items-center gap-3">
                  <div
                    class="flex size-10 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-border/60 bg-primary/10 text-primary"
                  >
                    <img
                      v-if="getAgentAvatarUrl(data.agent_avatar)"
                      :alt="getAgentDisplayName(data)"
                      :src="getAgentAvatarUrl(data.agent_avatar) ?? undefined"
                      class="size-full object-cover"
                    />
                    <IconifyIcon
                      v-else-if="isIconAvatar(data.agent_avatar)"
                      :icon="String(data.agent_avatar)"
                      class="size-5"
                    />
                    <span v-else class="text-sm font-semibold">
                      {{ getInitialLetter(getAgentDisplayName(data)) }}
                    </span>
                  </div>
                  <div class="min-w-0">
                    <div class="truncate text-sm font-semibold text-foreground">
                      {{ getAgentDisplayName(data) }}
                    </div>
                    <div
                      v-if="data.agent_id"
                      class="text-xs text-muted-foreground"
                    >
                      #{{ data.agent_id }}
                    </div>
                  </div>
                </div>
              </article>

              <IdentityTrigger
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
            </div>

            <div class="grid grid-cols-2 gap-3 xl:grid-cols-4">
              <div
                class="rounded-lg border border-dashed border-border bg-background p-3"
              >
                <div class="text-xs text-muted-foreground">
                  {{ $t('tenant.ai.actionLog.status') }}
                </div>
                <div class="mt-2 text-sm font-semibold">
                  {{ getStatusText(data.status) }}
                </div>
              </div>
              <div
                class="rounded-lg border border-dashed border-border bg-background p-3"
              >
                <div class="text-xs text-muted-foreground">
                  {{ $t('tenant.ai.actionLog.executionTime') }}
                </div>
                <div class="mt-2 text-sm font-semibold">
                  {{ formatDuration(data.duration_ms) }}
                </div>
              </div>
              <div
                class="rounded-lg border border-dashed border-border bg-background p-3"
              >
                <div class="text-xs text-muted-foreground">
                  {{ $t('tenant.ai.actionLog.traceId') }}
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
            :tab="$t('tenant.ai.actionLog.overviewTab')"
          >
            <div class="space-y-4">
              <Card size="small" :title="$t('tenant.ai.actionLog.basicInfo')">
                <Descriptions :column="2" bordered size="small">
                  <Descriptions.Item :label="$t('tenant.ai.actionLog.id')">
                    {{ data.id }}
                  </Descriptions.Item>
                  <Descriptions.Item
                    :label="$t('tenant.ai.actionLog.createdAt')"
                  >
                    {{ formatDate(data.created_at) }}
                  </Descriptions.Item>
                  <Descriptions.Item
                    :label="$t('tenant.ai.actionLog.actionName')"
                  >
                    <code class="rounded bg-accent px-1.5 py-0.5 text-xs">
                      {{ data.action_name }}
                    </code>
                  </Descriptions.Item>
                  <Descriptions.Item
                    :label="$t('tenant.ai.actionLog.actionType')"
                  >
                    <Tag :color="getTypeColor(data.action_type)">
                      {{ getTypeText(data.action_type) }}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item
                    :label="$t('tenant.ai.actionLog.actionLevel')"
                  >
                    <Tag :color="getLevelColor(data.action_level)">
                      {{ getLevelText(data.action_level) }}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item :label="$t('tenant.ai.actionLog.status')">
                    <Tag :color="getStatusColor(data.status)">
                      {{ getStatusText(data.status) }}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item
                    :label="$t('tenant.ai.actionLog.agentName')"
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
                    :label="$t('tenant.ai.actionLog.operatorId')"
                  >
                    <IdentityTrigger
                      :avatar-size="24"
                      :model="getOperatorIdentityModel(data)"
                      :meta="buildOperatorMeta(data)"
                    />
                  </Descriptions.Item>
                  <Descriptions.Item :label="$t('tenant.ai.actionLog.traceId')">
                    <code>{{ data.trace_id || '-' }}</code>
                  </Descriptions.Item>
                  <Descriptions.Item
                    :label="$t('tenant.ai.actionLog.toolCallId')"
                  >
                    <code>{{ data.tool_call_id || '-' }}</code>
                  </Descriptions.Item>
                  <Descriptions.Item
                    :label="$t('tenant.ai.actionLog.executionDecisionId')"
                  >
                    {{ data.execution_decision_id ?? '-' }}
                  </Descriptions.Item>
                </Descriptions>
              </Card>

              <Alert
                v-if="errorPayloadText"
                show-icon
                type="error"
                :message="$t('tenant.ai.actionLog.errorMessage')"
                :description="errorPayloadText"
              />

              <Card
                v-if="linkedDecision || linkedDecisionLoading"
                size="small"
                :title="$t('tenant.ai.actionLog.linkedDecision')"
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
                    :label="$t('tenant.ai.executionDecision.id')"
                  >
                    {{ linkedDecision.id }}
                  </Descriptions.Item>
                  <Descriptions.Item
                    :label="$t('tenant.ai.executionDecision.createdAt')"
                  >
                    {{ formatDate(linkedDecision.created_at) }}
                  </Descriptions.Item>
                  <Descriptions.Item
                    :label="$t('tenant.ai.executionDecision.decisionType')"
                  >
                    {{
                      getExecutionDecisionTypeText(linkedDecision.decision_type)
                    }}
                  </Descriptions.Item>
                  <Descriptions.Item
                    :label="$t('tenant.ai.executionDecision.status')"
                  >
                    {{ getExecutionDecisionStatusText(linkedDecision.status) }}
                  </Descriptions.Item>
                  <Descriptions.Item
                    :label="$t('tenant.ai.executionDecision.toolName')"
                  >
                    {{ linkedDecision.tool_name || '-' }}
                  </Descriptions.Item>
                  <Descriptions.Item
                    :label="$t('tenant.ai.executionDecision.actionName')"
                  >
                    {{ linkedDecision.action_name || '-' }}
                  </Descriptions.Item>
                  <Descriptions.Item
                    :label="$t('tenant.ai.executionDecision.correlationKey')"
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
            :tab="$t('tenant.ai.actionLog.requestTab')"
          >
            <ActionLogPayloadCard
              :copy-payload="copyPayload"
              :empty-description="$t('tenant.ai.actionLog.noRequestData')"
              :entries="requestEntries"
              :payload-text="requestPayloadText"
              :title="$t('tenant.ai.actionLog.requestData')"
            />
          </Tabs.TabPane>

          <Tabs.TabPane
            key="response"
            :tab="$t('tenant.ai.actionLog.responseTab')"
          >
            <ActionLogPayloadCard
              :copy-payload="copyPayload"
              :empty-description="$t('tenant.ai.actionLog.noResponseData')"
              :entries="responseEntries"
              :payload-text="responsePayloadText"
              :title="$t('tenant.ai.actionLog.responseData')"
            />
          </Tabs.TabPane>

          <Tabs.TabPane key="error" :tab="$t('tenant.ai.actionLog.errorTab')">
            <Card size="small" :title="$t('tenant.ai.actionLog.errorMessage')">
              <template #extra>
                <Button
                  v-if="errorPayloadText"
                  size="small"
                  type="text"
                  @click="copyPayload(errorPayloadText)"
                >
                  {{ $t('tenant.ai.actionLog.copyPayload') }}
                </Button>
              </template>

              <Alert
                v-if="errorPayloadText"
                show-icon
                type="error"
                :message="$t('tenant.ai.actionLog.errorMessage')"
                :description="errorPayloadText"
              />
              <Empty
                v-else
                :description="$t('tenant.ai.actionLog.noErrorData')"
              />
            </Card>
          </Tabs.TabPane>
        </Tabs>
      </div>
    </template>

    <Empty v-else :description="$t('tenant.ai.actionLog.noDetailData')" />
  </Drawer>
</template>
