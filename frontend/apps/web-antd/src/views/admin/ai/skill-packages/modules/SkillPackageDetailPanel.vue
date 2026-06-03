<script lang="ts" setup>
import type { TableProps } from 'ant-design-vue';

import type { AdminSkillPackageInfo } from '#/api/admin/skill-packages';
import type { AdminSkillInfo } from '#/api/admin/skills';

import { IconifyIcon, Plus } from '@vben/icons';

import { Button, Empty, Space, Tag } from 'ant-design-vue';

import { $t } from '#/locales';

import {
  getPackageRoleColor,
  getPackageRoleText,
  getRuntimeBindingModeColor,
  getRuntimeBindingModeText,
  getSourceSummaryText,
} from '../data';
import SkillPackageSkillsTable from './SkillPackageSkillsTable.vue';

interface Props {
  onCreatePackage: () => void;
  onCreateSkill: () => void;
  onDeleteSkill: (row: AdminSkillInfo) => void;
  onEditSkill: (row: AdminSkillInfo) => void;
  onOpenValvesConfig: () => void;
  onTestSkill: (row: AdminSkillInfo) => void;
  onTogglePackageStatus: (pkg: AdminSkillPackageInfo) => void;
  onToggleSkillStatus: (row: AdminSkillInfo) => void;
  selectedPackage: AdminSkillPackageInfo | null;
  skillColumns: TableProps['columns'];
  skills: AdminSkillInfo[];
  skillsLoading: boolean;
}

defineProps<Props>();
</script>

<template>
  <div
    class="flex h-full min-w-0 flex-1 flex-col overflow-hidden rounded-lg border border-border bg-card p-4 shadow-sm"
  >
    <template v-if="selectedPackage">
      <div class="mb-4 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div
            class="flex size-9 items-center justify-center rounded-lg bg-primary/10"
          >
            <IconifyIcon
              :icon="selectedPackage.avatar || 'lucide:package'"
              class="size-4.5 text-primary"
            />
          </div>
          <div>
            <div class="flex items-center gap-2">
              <span class="text-base font-semibold text-foreground">
                {{ selectedPackage.name }}
              </span>
              <Tag
                :color="getPackageRoleColor(selectedPackage.package_role_key)"
                style="
                  padding: 0 4px;
                  margin: 0;
                  font-size: 10px;
                  line-height: 16px;
                "
              >
                {{ getPackageRoleText(selectedPackage.package_role_key) }}
              </Tag>
              <Tag
                :color="selectedPackage.is_active ? 'success' : 'default'"
                :class="{ 'cursor-pointer': !selectedPackage.is_system }"
                style="
                  padding: 0 4px;
                  margin: 0;
                  font-size: 10px;
                  line-height: 16px;
                "
                @click="
                  !selectedPackage.is_system &&
                  onTogglePackageStatus(selectedPackage)
                "
              >
                {{
                  selectedPackage.is_active
                    ? $t('admin.common.enabled')
                    : $t('admin.common.disabled')
                }}
              </Tag>
              <Tag
                :color="
                  getRuntimeBindingModeColor(
                    selectedPackage.runtime_binding_mode,
                  )
                "
                style="
                  padding: 0 4px;
                  margin: 0;
                  font-size: 10px;
                  line-height: 16px;
                "
              >
                {{
                  getRuntimeBindingModeText(
                    selectedPackage.runtime_binding_mode,
                  )
                }}
              </Tag>
            </div>
            <div class="flex flex-col gap-0.5">
              <span
                v-if="selectedPackage.description"
                class="text-xs text-muted-foreground"
              >
                {{ selectedPackage.description }}
              </span>
              <span class="text-xs text-muted-foreground">
                {{
                  getSourceSummaryText(
                    selectedPackage.source_summary,
                    selectedPackage.source_plugin,
                  )
                }}
              </span>
            </div>
          </div>
        </div>
        <Space>
          <Button
            v-if="selectedPackage.valves_field_count > 0"
            size="small"
            @click="onOpenValvesConfig"
          >
            <IconifyIcon icon="lucide:settings" class="mr-1 size-3.5" />
            {{ $t('admin.ai.skillPackage.valves.configBtn') }}
          </Button>
          <Button
            v-access:code="['ai_skill:create']"
            type="primary"
            size="small"
            @click="onCreateSkill"
          >
            <Plus class="mr-1 size-3.5" />
            {{ $t('admin.ai.skill.create') }}
          </Button>
        </Space>
      </div>

      <div class="min-h-0 flex-1 overflow-auto">
        <SkillPackageSkillsTable
          :on-delete-skill="onDeleteSkill"
          :on-edit-skill="onEditSkill"
          :on-test-skill="onTestSkill"
          :on-toggle-skill-status="onToggleSkillStatus"
          :skill-columns="skillColumns"
          :skills="skills"
          :skills-loading="skillsLoading"
        />
      </div>
    </template>

    <div v-else class="flex h-full items-center justify-center">
      <Empty :description="$t('admin.ai.skillPackage.detail.empty')">
        <Button
          v-access:code="['ai_skill_package:create']"
          type="primary"
          @click="onCreatePackage"
        >
          <Plus class="mr-1 size-4" />
          {{ $t('admin.ai.skillPackage.create') }}
        </Button>
      </Empty>
    </div>
  </div>
</template>
