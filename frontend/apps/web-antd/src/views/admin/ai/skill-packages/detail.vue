<script lang="ts" setup>
import { provide } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Empty, Spin, TabPane, Tabs } from 'ant-design-vue';

import { $t } from '#/locales';

import { skillPackageDetailContextKey } from './modules/detail/detail-context';
import SkillPackageDetailHero from './modules/detail/SkillPackageDetailHero.vue';
import SkillPackageOverviewTab from './modules/detail/SkillPackageOverviewTab.vue';
import SkillPackageResolvedToolsTab from './modules/detail/SkillPackageResolvedToolsTab.vue';
import SkillPackageSkillsTab from './modules/detail/SkillPackageSkillsTab.vue';
import SkillPackageValvesTab from './modules/detail/SkillPackageValvesTab.vue';
import { useSkillPackageDetailPage } from './modules/detail/use-skill-package-detail-page';

defineOptions({ name: 'AdminSkillPackageDetail' });

const page = useSkillPackageDetailPage();
const { activeTab, hasValves, loading, pkg } = page;

provide(skillPackageDetailContextKey, page);
</script>

<template>
  <Page auto-content-height>
    <Spin :spinning="loading">
      <div v-if="!loading && !pkg" class="py-20">
        <Empty :description="$t('common.noData')" />
      </div>

      <div v-if="pkg" class="flex flex-col gap-4">
        <SkillPackageDetailHero />

        <div class="rounded-xl border bg-card">
          <Tabs v-model:active-key="activeTab" class="px-2 pt-1">
            <TabPane key="overview">
              <template #tab>
                <span class="flex items-center gap-1.5 px-1">
                  <IconifyIcon
                    icon="lucide:layout-dashboard"
                    class="size-3.5"
                  />
                  {{ $t('admin.ai.skillPackage.detail.overview') }}
                </span>
              </template>

              <SkillPackageOverviewTab />
            </TabPane>

            <TabPane key="skills">
              <template #tab>
                <span class="flex items-center gap-1.5 px-1">
                  <IconifyIcon icon="lucide:blocks" class="size-3.5" />
                  {{ $t('admin.ai.skillPackage.detail.skills') }}
                </span>
              </template>

              <SkillPackageSkillsTab />
            </TabPane>

            <TabPane key="tools">
              <template #tab>
                <span class="flex items-center gap-1.5 px-1">
                  <IconifyIcon icon="lucide:wrench" class="size-3.5" />
                  {{ $t('admin.ai.skillPackage.detail.tools') }}
                </span>
              </template>

              <SkillPackageResolvedToolsTab />
            </TabPane>

            <TabPane key="valves" :disabled="!hasValves">
              <template #tab>
                <span class="flex items-center gap-1.5 px-1">
                  <IconifyIcon icon="lucide:settings-2" class="size-3.5" />
                  {{ $t('admin.ai.skillPackage.valves.title') }}
                </span>
              </template>

              <SkillPackageValvesTab />
            </TabPane>
          </Tabs>
        </div>
      </div>
    </Spin>
  </Page>
</template>
