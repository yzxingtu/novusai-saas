<script lang="ts" setup>
import type { MonitoringScope } from '../api';

import { Page } from '@vben/common-ui';

import { Spin } from 'ant-design-vue';

import MonitoringUsageAccessChannelCard from './monitoring-usage/MonitoringUsageAccessChannelCard.vue';
import MonitoringUsageCharts from './monitoring-usage/MonitoringUsageCharts.vue';
import MonitoringUsageHero from './monitoring-usage/MonitoringUsageHero.vue';
import MonitoringUsageTopSectionCard from './monitoring-usage/MonitoringUsageTopSectionCard.vue';
import MonitoringUsageTopTenantsCard from './monitoring-usage/MonitoringUsageTopTenantsCard.vue';
import { useMonitoringUsageDashboard } from './monitoring-usage/use-monitoring-usage-dashboard';

defineOptions({ name: 'MonitoringUsagePageShell' });

const props = defineProps<{
  i18nPrefix: string;
  scope: MonitoringScope;
  showTopTenants?: boolean;
  title: string;
}>();

const {
  applyPreset,
  averageTokensPerCall,
  breakdownLabel,
  busiestDay,
  dashboard,
  dateRange,
  handleDateChange,
  heroChips,
  heroMetrics,
  isAdmin,
  loading,
  presets,
  rangeLabel,
  scopeLabel,
  tenantLeaders,
  topModel,
  topSections,
  topTenant,
  totalCalls,
} = useMonitoringUsageDashboard({
  i18nPrefix: props.i18nPrefix,
  scope: props.scope,
});
</script>

<template>
  <Page
    auto-content-height
    content-class="monitoring-usage-page flex flex-col gap-4 !p-4"
  >
    <MonitoringUsageHero
      :date-range="dateRange"
      :hero-chips="heroChips"
      :hero-metrics="heroMetrics"
      :i18n-prefix="i18nPrefix"
      :presets="presets"
      :scope="scope"
      :title="title"
      @preset="applyPreset"
      @range-change="handleDateChange"
    />

    <Spin :spinning="loading">
      <template v-if="dashboard">
        <section
          class="grid items-start gap-5 2xl:grid-cols-[minmax(0,1.58fr)_minmax(328px,0.92fr)]"
        >
          <div class="flex min-w-0 flex-col gap-5">
            <MonitoringUsageCharts
              :average-tokens-per-call="averageTokensPerCall"
              :breakdown-label="breakdownLabel"
              :busiest-day="busiestDay"
              :dashboard="dashboard"
              :i18n-prefix="i18nPrefix"
              :range-label="rangeLabel"
              :scope-label="scopeLabel"
              :total-calls="totalCalls"
              :top-model="topModel"
            />

            <MonitoringUsageTopSectionCard
              v-if="!isAdmin && topSections[0]"
              :breakdown-label="breakdownLabel"
              :i18n-prefix="i18nPrefix"
              :scope="scope"
              :section="topSections[0]"
              :tenant-id="dashboard.tenant_id"
              :tenant-name="dashboard.tenant_name"
              :total-calls="totalCalls"
            />
          </div>

          <div class="flex min-w-0 flex-col gap-5 self-start">
            <MonitoringUsageTopTenantsCard
              v-if="isAdmin && showTopTenants"
              :breakdown-label="breakdownLabel"
              :i18n-prefix="i18nPrefix"
              :tenant-leaders="tenantLeaders"
              :top-tenant="topTenant"
              :total-calls="totalCalls"
            />

            <MonitoringUsageAccessChannelCard
              :breakdown-label="breakdownLabel"
              :i18n-prefix="i18nPrefix"
              :items="dashboard.access_channel_stats"
              :total-calls="totalCalls"
            />

            <MonitoringUsageTopSectionCard
              v-for="section in !isAdmin ? topSections.slice(1) : []"
              :key="section.key"
              :breakdown-label="breakdownLabel"
              :i18n-prefix="i18nPrefix"
              :scope="scope"
              :section="section"
              :tenant-id="dashboard.tenant_id"
              :tenant-name="dashboard.tenant_name"
              :total-calls="totalCalls"
            />
          </div>
        </section>

        <section v-if="isAdmin" class="mt-5 grid items-start gap-5 xl:grid-cols-2">
          <MonitoringUsageTopSectionCard
            v-for="section in topSections"
            :key="section.key"
            :breakdown-label="breakdownLabel"
            :i18n-prefix="i18nPrefix"
            :scope="scope"
            :section="section"
            :tenant-id="dashboard.tenant_id"
            :tenant-name="dashboard.tenant_name"
            :total-calls="totalCalls"
          />
        </section>
      </template>
    </Spin>
  </Page>
</template>

<style src="./monitoring-usage/monitoring-usage-page.css"></style>
