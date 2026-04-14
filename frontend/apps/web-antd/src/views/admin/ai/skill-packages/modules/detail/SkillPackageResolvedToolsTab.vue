<script lang="ts" setup>
import { IconifyIcon } from '@vben/icons';

import { Empty, Spin, Tag } from 'ant-design-vue';

import { $t } from '#/locales';

import { useSkillPackageDetailContext } from './detail-context';

const {
  getToolRequiredParamCount,
  getToolTypeColor,
  getToolTypeIcon,
  getToolTypeText,
  resolvedTools,
  toolsLoading,
} = useSkillPackageDetailContext();
</script>

<template>
  <div class="flex flex-col gap-4 p-5 pt-3">
    <div>
      <div class="text-sm font-semibold text-foreground">
        {{ $t('admin.ai.skillPackage.detail.tools') }}
      </div>
      <p class="mt-1 text-xs text-muted-foreground">
        {{ resolvedTools.length }}
        {{ $t('admin.ai.skillPackage.detail.tools') }}
      </p>
    </div>

    <Spin :spinning="toolsLoading">
      <div v-if="resolvedTools.length === 0" class="py-12">
        <Empty :description="$t('admin.ai.skillPackage.detail.noTools')" />
      </div>

      <div v-else class="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <div
          v-for="tool in resolvedTools"
          :key="tool.name"
          class="rounded-xl border bg-accent/30 p-4 transition-all duration-200 hover:border-primary/20 hover:shadow-sm"
        >
          <div class="flex items-start gap-3">
            <div
              class="mt-0.5 flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/10"
            >
              <IconifyIcon
                :icon="getToolTypeIcon(tool.tool_type)"
                class="size-5 text-primary"
              />
            </div>

            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-2">
                <span class="font-mono text-sm font-semibold text-foreground">
                  {{ tool.name }}
                </span>
                <Tag
                  v-if="tool.tool_type"
                  :color="getToolTypeColor(tool.tool_type)"
                  class="!mr-0 !text-[11px]"
                >
                  {{ getToolTypeText(tool.tool_type) }}
                </Tag>
                <Tag
                  v-if="tool.source_plugin"
                  color="geekblue"
                  class="!mr-0 !text-[11px]"
                >
                  {{ tool.source_plugin }}
                </Tag>
              </div>

              <p class="mt-2 text-sm leading-relaxed text-muted-foreground">
                {{
                  tool.description ||
                  $t('admin.ai.skillPackage.detail.noDescription')
                }}
              </p>

              <div class="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
                <div class="rounded-lg border bg-background px-3 py-2">
                  <div class="text-[11px] text-muted-foreground">
                    {{ $t('admin.ai.skillPackage.detail.skillName') }}
                  </div>
                  <div
                    class="mt-1 truncate text-sm font-medium text-foreground"
                  >
                    {{ tool.source_skill_name }}
                  </div>
                </div>

                <div class="rounded-lg border bg-background px-3 py-2">
                  <div class="text-[11px] text-muted-foreground">
                    {{ $t('admin.ai.skillPackage.detail.toolParams') }}
                  </div>
                  <div class="mt-1 text-sm font-medium text-foreground">
                    {{ tool.parameters.length }}
                  </div>
                </div>

                <div class="rounded-lg border bg-background px-3 py-2">
                  <div class="text-[11px] text-muted-foreground">
                    {{ $t('admin.ai.skillPackage.valves.required') }}
                  </div>
                  <div class="mt-1 text-sm font-medium text-foreground">
                    {{ getToolRequiredParamCount(tool) }}
                  </div>
                </div>
              </div>

              <div v-if="tool.parameters.length > 0" class="mt-3">
                <div class="mb-2 text-xs font-medium text-muted-foreground">
                  {{ $t('admin.ai.skillPackage.detail.toolParams') }}
                </div>
                <div class="flex flex-wrap gap-2">
                  <div
                    v-for="param in tool.parameters"
                    :key="param.name"
                    class="rounded-full border bg-background px-3 py-1 text-xs"
                  >
                    <span class="font-mono text-foreground">
                      {{ param.name }}
                    </span>
                    <span class="ml-1 text-muted-foreground">
                      {{ param.type }}
                    </span>
                    <span
                      v-if="param.required"
                      class="ml-1 text-red-500 dark:text-red-400"
                    >
                      *
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Spin>
  </div>
</template>
