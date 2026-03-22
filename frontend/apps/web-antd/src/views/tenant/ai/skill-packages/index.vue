<script lang="ts" setup>
import type { TenantSkillPackageInfo } from '#/api/tenant/skill-packages';

import { watch } from 'vue';
import { useRouter } from 'vue-router';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import {
  Alert,
  Button,
  Empty,
  Input,
  Pagination,
  Spin,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import { getSkillPackageListApi } from '#/api/tenant/skill-packages';
import { useCrudList } from '#/composables';
import { $t } from '#/locales';
import { formatDate, formatRelativeTime } from '#/utils/common';

import {
  getPackageRoleColor,
  getPackageRoleText,
  getRuntimeBindingModeColor,
  getRuntimeBindingModeText,
  getSourceSummaryText,
} from './data';

defineOptions({ name: 'TenantSkillPackageCatalog' });

const router = useRouter();

const {
  list,
  total,
  loading,
  currentPage,
  pageSize,
  searchKeyword,
  onPageChange,
  onSearch,
} = useCrudList<TenantSkillPackageInfo>({
  api: {
    list: getSkillPackageListApi,
    resource: '/tenant/ai/skill-packages',
  },
  defaultSort: 'sort_order,-created_at',
  i18nPrefix: 'tenant.ai.skillPackage',
  pageSize: 12,
  ai: {
    detailRoute: '/tenant/ai/skill-packages/:id',
    entityName: $t('tenant.ai.skillPackage.name'),
    entityDescription: $t('tenant.ai.skillPackage.pageDesc'),
  },
});

function doSearch() {
  const keyword = searchKeyword.value.trim();
  const params: Record<string, unknown> = {};

  if (keyword) {
    params['filter[name][ilike]'] = keyword;
  }

  onSearch(params);
}

function openDetail(item: TenantSkillPackageInfo) {
  router.push(`/tenant/ai/skill-packages/${item.id}`);
}

function getPackageStatusColor(isActive: boolean): string {
  return isActive ? 'success' : 'default';
}

function getPackageStatusText(isActive: boolean): string {
  return isActive ? $t('common.enabled') : $t('common.disabled');
}

watch(searchKeyword, (value) => {
  if (!value) {
    doSearch();
  }
});
</script>

<template>
  <Page
    auto-content-height
    :description="$t('tenant.ai.skillPackage.pageDesc')"
    content-class="flex flex-col gap-4"
  >
    <Alert
      :message="$t('tenant.ai.skillPackage.runtimeTruthHint')"
      type="info"
      show-icon
    />

    <div class="flex flex-wrap items-center gap-3">
      <Input
        v-model:value="searchKeyword"
        :placeholder="$t('tenant.ai.skillPackage.placeholder.searchName')"
        allow-clear
        class="max-w-sm"
        @press-enter="doSearch"
      >
        <template #prefix>
          <IconifyIcon icon="lucide:search" class="size-4 text-muted-foreground" />
        </template>
      </Input>

      <div class="flex items-center gap-2 text-sm text-muted-foreground">
        <IconifyIcon icon="lucide:package-search" class="size-4" />
        <span>{{ total }} {{ $t('tenant.ai.skillPackage.title') }}</span>
      </div>
    </div>

    <Spin :spinning="loading">
      <div
        v-if="list.length === 0 && !loading"
        class="flex min-h-[320px] items-center justify-center"
      >
        <Empty :description="$t('common.noData')" />
      </div>

      <div
        v-else
        class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3"
      >
        <div
          v-for="item in list"
          :key="item.id"
          class="group rounded-2xl border border-border bg-card p-4 transition-all duration-200 hover:border-primary/30 hover:shadow-md"
        >
          <div class="flex items-start gap-3">
            <div
              class="flex size-11 shrink-0 items-center justify-center rounded-2xl bg-primary/10"
            >
              <IconifyIcon
                :icon="item.avatar || 'lucide:package'"
                class="size-5 text-primary"
              />
            </div>

            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-2">
                <button
                  class="truncate text-left text-sm font-semibold text-foreground transition-colors hover:text-primary"
                  @click="openDetail(item)"
                >
                  {{ item.name }}
                </button>

                <Tag
                  :color="getPackageRoleColor(item.package_role_key)"
                  class="!mr-0 !text-[11px]"
                >
                  {{ getPackageRoleText(item.package_role_key) }}
                </Tag>

                <Tag
                  :color="getPackageStatusColor(item.is_active)"
                  class="!mr-0 !text-[11px]"
                >
                  {{ getPackageStatusText(item.is_active) }}
                </Tag>

                <Tag
                  v-if="item.is_recommended"
                  color="gold"
                  class="!mr-0 !text-[11px]"
                >
                  {{ $t('tenant.ai.skillPackage.isRecommended') }}
                </Tag>
              </div>

              <p class="mt-2 line-clamp-2 text-sm text-muted-foreground">
                {{
                  item.description ||
                  $t('tenant.ai.skillPackage.detail.noDescription')
                }}
              </p>
            </div>
          </div>

          <div class="mt-4 flex flex-wrap items-center gap-2">
            <Tag
              :color="getRuntimeBindingModeColor(item.runtime_binding_mode)"
              class="!mr-0 !text-[11px]"
            >
              {{ getRuntimeBindingModeText(item.runtime_binding_mode) }}
            </Tag>

            <Tooltip
              :title="
                getSourceSummaryText(item.source_summary, item.source_plugin)
              "
            >
              <Tag color="blue" class="!mr-0 !text-[11px]">
                {{
                  getSourceSummaryText(item.source_summary, item.source_plugin)
                }}
              </Tag>
            </Tooltip>

            <Tag
              v-if="item.source_plugin"
              color="geekblue"
              class="!mr-0 !text-[11px]"
            >
              {{ item.source_plugin }}
            </Tag>
          </div>

          <div
            class="mt-4 grid grid-cols-2 gap-3 rounded-xl border bg-accent/20 p-3 text-xs text-muted-foreground"
          >
            <div class="rounded-lg bg-background px-3 py-2">
              <div>{{ $t('tenant.ai.skillPackage.skillCount') }}</div>
              <div class="mt-1 text-sm font-semibold text-foreground">
                {{ item.skill_count }}
              </div>
            </div>

            <div class="rounded-lg bg-background px-3 py-2">
              <div>{{ $t('tenant.ai.skillPackage.detail.envVars') }}</div>
              <div class="mt-1 text-sm font-semibold text-foreground">
                {{ item.configured_valves_count }}/{{ item.valves_field_count }}
              </div>
            </div>
          </div>

          <div
            class="mt-4 flex items-center justify-between border-t border-border/60 pt-3 text-xs text-muted-foreground"
          >
            <Tooltip :title="formatDate(item.updated_at)">
              <span class="flex items-center gap-1">
                <IconifyIcon icon="lucide:clock-3" class="size-3.5" />
                {{ formatRelativeTime(item.updated_at) }}
              </span>
            </Tooltip>

            <Button size="small" type="link" @click="openDetail(item)">
              {{ $t('shared.common.viewDetail') }}
            </Button>
          </div>
        </div>
      </div>
    </Spin>

    <div v-if="total > pageSize" class="flex justify-end">
      <Pagination
        :current="currentPage"
        :total="total"
        :page-size="pageSize"
        size="small"
        :show-size-changer="false"
        @change="onPageChange"
      />
    </div>
  </Page>
</template>
