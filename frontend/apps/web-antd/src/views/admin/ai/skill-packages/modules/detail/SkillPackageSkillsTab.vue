<script lang="ts" setup>
import { IconifyIcon } from '@vben/icons';

import { Button, Empty, Popconfirm, Spin, Switch, Tag } from 'ant-design-vue';

import { $t } from '#/locales';
import { getSkillTypeColor, getSkillTypeIcon } from '#/utils/ai-helpers';
import { formatRelativeTime } from '#/utils/common';

import { getSkillTypeText } from '../../../skills/data';
import { useSkillPackageDetailContext } from './detail-context';

const {
  canDeleteSkill,
  canToggleSkillStatus,
  canViewSkillDetail,
  handleDeleteSkill,
  handleToggleSkillStatus,
  openSkillDetail,
  openWorkspace,
  pkg,
  skills,
  skillsLoading,
} = useSkillPackageDetailContext();
</script>

<template>
  <div v-if="pkg" class="flex flex-col gap-4 p-5 pt-3">
    <div class="flex items-start justify-between gap-4">
      <div>
        <div class="text-sm font-semibold text-foreground">
          {{ $t('admin.ai.skillPackage.detail.skills') }}
        </div>
        <p class="mt-1 text-xs text-muted-foreground">
          {{ pkg.skill_count }}
          {{ $t('admin.ai.skillPackage.skillCount') }}
        </p>
      </div>

      <div class="flex items-center gap-2">
        <Button size="small" @click="openWorkspace()">
          <IconifyIcon icon="lucide:layout-panel-left" class="mr-1 size-3.5" />
          {{ $t('admin.ai.skillPackage.detail.openWorkspace') }}
        </Button>
        <Button size="small" type="primary" @click="openWorkspace(true)">
          <IconifyIcon icon="lucide:plus" class="mr-1 size-3.5" />
          {{ $t('admin.ai.skill.create') }}
        </Button>
      </div>
    </div>

    <Spin :spinning="skillsLoading">
      <div v-if="skills.length === 0" class="py-12">
        <Empty :description="$t('admin.ai.skillPackage.detail.empty')" />
      </div>

      <div v-else class="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <div
          v-for="skill in skills"
          :key="skill.id"
          class="rounded-xl border bg-accent/30 p-4 transition-all duration-200 hover:border-primary/20 hover:shadow-sm"
        >
          <div class="flex items-start justify-between gap-4">
            <div class="flex min-w-0 flex-1 items-start gap-3">
              <div
                class="mt-0.5 flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/10"
              >
                <IconifyIcon
                  :icon="skill.avatar || getSkillTypeIcon(skill.type)"
                  class="size-5 text-primary"
                />
              </div>

              <div class="min-w-0 flex-1">
                <div class="flex flex-wrap items-center gap-2">
                  <span class="truncate text-sm font-semibold text-foreground">
                    {{ skill.name }}
                  </span>
                  <Tag
                    :color="getSkillTypeColor(skill.type)"
                    class="!mr-0 !text-[11px]"
                  >
                    {{ getSkillTypeText(skill.type) }}
                  </Tag>
                  <Tag
                    v-if="skill.is_system"
                    color="purple"
                    class="!mr-0 !text-[11px]"
                  >
                    {{ $t('admin.ai.skillPackage.system') }}
                  </Tag>
                  <Tag
                    v-if="skill.source_plugin"
                    color="geekblue"
                    class="!mr-0 !text-[11px]"
                  >
                    {{ skill.source_plugin }}
                  </Tag>
                </div>

                <p
                  class="mt-2 line-clamp-2 text-sm leading-relaxed text-muted-foreground"
                >
                  {{
                    skill.description ||
                    $t('admin.ai.skillPackage.detail.noDescription')
                  }}
                </p>

                <div
                  class="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground"
                >
                  <span class="flex items-center gap-1">
                    <IconifyIcon icon="lucide:clock-3" class="size-3.5" />
                    {{ skill.timeout }}s
                  </span>
                  <span class="flex items-center gap-1">
                    <IconifyIcon icon="lucide:calendar-days" class="size-3.5" />
                    {{ formatRelativeTime(skill.created_at) }}
                  </span>
                </div>
              </div>
            </div>

            <div class="flex shrink-0 items-center gap-1">
              <Button
                v-if="canViewSkillDetail"
                size="small"
                type="text"
                @click="openSkillDetail(skill.id)"
              >
                <IconifyIcon icon="lucide:external-link" class="size-4" />
              </Button>
              <Switch
                :checked="skill.is_active"
                size="small"
                :disabled="skill.is_system || !canToggleSkillStatus"
                @change="handleToggleSkillStatus(skill)"
              />
              <Popconfirm
                v-if="!skill.is_system && canDeleteSkill"
                :title="$t('admin.common.confirmDelete')"
                @confirm="handleDeleteSkill(skill)"
              >
                <Button danger size="small" type="text">
                  <IconifyIcon icon="lucide:trash-2" class="size-4" />
                </Button>
              </Popconfirm>
            </div>
          </div>
        </div>
      </div>
    </Spin>
  </div>
</template>
