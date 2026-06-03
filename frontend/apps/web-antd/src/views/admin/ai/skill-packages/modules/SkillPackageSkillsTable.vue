<script lang="ts" setup>
import type { TableProps } from 'ant-design-vue';

import type { AdminSkillInfo } from '#/api/admin/skills';

import { IconifyIcon } from '@vben/icons';

import {
  Badge,
  Button,
  Empty,
  Space,
  Table,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import { $t } from '#/locales';
import { formatDate, formatRelativeTime } from '#/utils/common';

import { getSkillTypeColor, getSkillTypeText } from '../../skills/data';

interface Props {
  onDeleteSkill: (row: AdminSkillInfo) => void;
  onEditSkill: (row: AdminSkillInfo) => void;
  onTestSkill: (row: AdminSkillInfo) => void;
  onToggleSkillStatus: (row: AdminSkillInfo) => void;
  skillColumns: TableProps['columns'];
  skills: AdminSkillInfo[];
  skillsLoading: boolean;
}

defineProps<Props>();

function isRuntimeActiveSkill(record: AdminSkillInfo): boolean {
  const status = String(
    (record as AdminSkillInfo & { status?: string }).status ?? '',
  );
  return record.is_active === true && status === 'active';
}
</script>

<template>
  <Table
    :columns="skillColumns"
    :data-source="skills"
    :loading="skillsLoading"
    :pagination="false"
    row-key="id"
    size="small"
  >
    <template #bodyCell="{ column, record }">
      <template v-if="column.key === 'name'">
        <div class="flex items-center gap-2">
          <IconifyIcon
            :icon="record.avatar || 'lucide:sparkles'"
            class="size-4 text-muted-foreground"
          />
          <div class="flex flex-col">
            <span class="font-medium">
              {{ record.name }}
              <Tag
                v-if="record.is_system"
                color="purple"
                class="ml-1"
                style="padding: 0 4px; font-size: 10px; line-height: 16px"
              >
                {{ $t('admin.ai.skill.system') }}
              </Tag>
            </span>
            <span
              v-if="record.description"
              class="line-clamp-1 text-xs text-muted-foreground"
            >
              {{ record.description }}
            </span>
          </div>
        </div>
      </template>

      <template v-else-if="column.key === 'type'">
        <Tag :color="getSkillTypeColor(record.type)">
          {{ getSkillTypeText(record.type) }}
        </Tag>
        <Badge
          v-if="record.type === 'toolkit' && record.toolkit_meta?.tools?.length"
          :count="record.toolkit_meta.tools.length"
          :number-style="{
            backgroundColor: 'hsl(var(--primary))',
            fontSize: '10px',
            minWidth: '16px',
            height: '16px',
            lineHeight: '16px',
          }"
          :title="`${record.toolkit_meta.tools.length} tools`"
          class="ml-1"
        />
        <Badge
          v-if="
            record.type === 'builtin' &&
            Array.isArray((record.config as Record<string, unknown>)?.tools)
          "
          :count="
            ((record.config as Record<string, unknown>).tools as unknown[])
              .length
          "
          :number-style="{
            backgroundColor: '#722ed1',
            fontSize: '10px',
            minWidth: '16px',
            height: '16px',
            lineHeight: '16px',
          }"
          :title="`${((record.config as Record<string, unknown>).tools as unknown[]).length} tools`"
          class="ml-1"
        />
      </template>

      <template v-else-if="column.key === 'is_active'">
        <Tag
          :color="
            isRuntimeActiveSkill(record as AdminSkillInfo)
              ? 'success'
              : 'default'
          "
          :class="{ 'cursor-pointer': !record.is_system }"
          @click="
            !record.is_system && onToggleSkillStatus(record as AdminSkillInfo)
          "
        >
          {{
            isRuntimeActiveSkill(record as AdminSkillInfo)
              ? $t('admin.common.enabled')
              : $t('admin.common.disabled')
          }}
        </Tag>
      </template>

      <template v-else-if="column.key === 'timeout'">
        <span class="font-mono text-sm text-muted-foreground">
          {{ record.timeout }}s
        </span>
      </template>

      <template v-else-if="column.key === 'created_at'">
        <Tooltip :title="formatDate(record.created_at)">
          <span class="text-muted-foreground">
            {{ formatRelativeTime(record.created_at) }}
          </span>
        </Tooltip>
      </template>

      <template v-else-if="column.key === 'action'">
        <Space>
          <Tooltip :title="$t('admin.ai.skill.testBtn')">
            <Button
              v-access:code="['ai_skill:detail']"
              type="link"
              size="small"
              @click="onTestSkill(record as AdminSkillInfo)"
            >
              <IconifyIcon icon="lucide:play" class="size-3.5" />
            </Button>
          </Tooltip>
          <Button
            v-access:code="['ai_skill:update']"
            type="link"
            size="small"
            @click="onEditSkill(record as AdminSkillInfo)"
          >
            {{ $t('admin.common.edit') }}
          </Button>
          <Button
            v-if="!record.is_system"
            v-access:code="['ai_skill:delete']"
            type="link"
            size="small"
            danger
            @click="onDeleteSkill(record as AdminSkillInfo)"
          >
            {{ $t('admin.common.delete') }}
          </Button>
        </Space>
      </template>
    </template>

    <template #emptyText>
      <Empty :description="$t('admin.ai.skillPackage.detail.empty')" />
    </template>
  </Table>
</template>
