<script lang="ts" setup>
import { useRouter } from 'vue-router';

import { useUserStore } from '@vben/stores';

import { Spin } from 'ant-design-vue';

import PluginDashboardWidgets from '#/components/business/plugin-slots/PluginDashboardWidgets.vue';
import { $t } from '#/locales';
import TenantDashboardUsageChart from '#/views/_shared/charts/TenantDashboardUsageChart.vue';
import DashboardActivityFeed from '#/views/_shared/dashboard/DashboardActivityFeed.vue';
import DashboardHeroBanner from '#/views/_shared/dashboard/DashboardHeroBanner.vue';
import DashboardMetricCards from '#/views/_shared/dashboard/DashboardMetricCards.vue';
import DashboardRouteCardList from '#/views/_shared/dashboard/DashboardRouteCardList.vue';
import DashboardSectionHeader from '#/views/_shared/dashboard/DashboardSectionHeader.vue';
import DashboardSpotlightGrid from '#/views/_shared/dashboard/DashboardSpotlightGrid.vue';
import DashboardSummaryPanels from '#/views/_shared/dashboard/DashboardSummaryPanels.vue';

import { useTenantDashboard } from './use-tenant-dashboard';

defineOptions({ name: 'TenantDashboard' });

const router = useRouter();
const userStore = useUserStore();
const {
  actionDeck,
  activityEntries,
  aiTrend,
  heroActions,
  loading,
  operationalSignals,
  overviewCards,
  portalHealthCards,
  realtimeChips,
  spotlights,
  stats,
  summaryPanels,
} = useTenantDashboard();

function goTo(routePath: string) {
  void router.push(routePath);
}

</script>

<template>
  <div class="space-y-6 p-5">
    <DashboardHeroBanner
      :actions="heroActions"
      :badge="$t('tenant.dashboard.cockpit.badge')"
      badge-icon="lucide:gauge"
      :chips="realtimeChips"
      :description="
        $t('tenant.dashboard.cockpit.description', {
          name: userStore.userInfo?.realName || $t('tenant.common.admin'),
        })
      "
      :metrics="overviewCards"
      secondary-glow-class="bg-emerald-500/10"
      :title="$t('tenant.dashboard.title')"
      @select="goTo"
    >
      <template #footer>
        <DashboardSpotlightGrid :items="spotlights" />
      </template>
    </DashboardHeroBanner>

    <Spin :spinning="loading">
      <div class="space-y-6">
        <section
          class="grid gap-6 2xl:grid-cols-[minmax(0,1.05fr)_minmax(360px,0.95fr)]"
        >
          <div
            class="rounded-[28px] border border-border/70 bg-card p-5 shadow-sm sm:p-6"
          >
            <div class="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 class="text-xl font-semibold text-foreground">
                  {{ $t('tenant.dashboard.cockpit.trendTitle') }}
                </h2>
                <p class="mt-1 text-sm text-muted-foreground">
                  {{ $t('tenant.dashboard.cockpit.trendDesc') }}
                </p>
              </div>
              <div
                class="rounded-[20px] border border-border/60 bg-background/80 px-4 py-3"
              >
                <div
                  class="text-xs uppercase tracking-[0.18em] text-muted-foreground"
                >
                  {{ $t('tenant.dashboard.cockpit.trendSummary') }}
                </div>
                <div class="mt-2 text-2xl font-semibold text-foreground">
                  {{ stats.monthly_conversations }}
                </div>
              </div>
            </div>

            <div class="mt-5">
              <TenantDashboardUsageChart
                :data="aiTrend"
                :empty-text="$t('tenant.dashboard.aiTrend.empty')"
              />
            </div>
          </div>

          <div
            class="rounded-[28px] border border-border/70 bg-card p-5 shadow-sm sm:p-6"
          >
            <DashboardSectionHeader
              icon="lucide:activity"
              :title="$t('tenant.dashboard.activities.title')"
              :description="$t('tenant.dashboard.cockpit.activitiesDesc')"
            />
            <DashboardActivityFeed
              :items="activityEntries"
              empty-height="420px"
              max-height="420px"
              :empty-text="$t('tenant.dashboard.activities.empty')"
            />
          </div>
        </section>

        <section class="grid gap-6 xl:grid-cols-2">
          <div
            class="rounded-[28px] border border-border/70 bg-card p-5 shadow-sm sm:p-6"
          >
            <DashboardSectionHeader
              icon="lucide:radar"
              :title="$t('tenant.dashboard.cockpit.signalsTitle')"
              :description="$t('tenant.dashboard.cockpit.signalsDesc')"
            />
            <DashboardRouteCardList
              variant="signal"
              :columns="2"
              :items="operationalSignals"
              @select="goTo"
            />
          </div>

          <div
            class="rounded-[28px] border border-border/70 bg-card p-5 shadow-sm sm:p-6"
          >
            <DashboardSectionHeader
              icon="lucide:rocket"
              :title="$t('tenant.dashboard.cockpit.actionsTitle')"
              :description="$t('tenant.dashboard.cockpit.actionsDesc')"
            />
            <DashboardRouteCardList
              :columns="2"
              :items="actionDeck"
              @select="goTo"
            />
          </div>
        </section>

        <section
          class="grid gap-6 xl:grid-cols-[minmax(0,1.05fr)_minmax(360px,0.95fr)]"
        >
          <div class="space-y-6">
            <div
              class="rounded-[28px] border border-border/70 bg-card p-5 shadow-sm sm:p-6"
            >
              <DashboardSectionHeader
                icon="lucide:layout-dashboard"
                :title="$t('tenant.dashboard.cockpit.portalTitle')"
                :description="$t('tenant.dashboard.cockpit.portalDesc')"
              />

              <div class="mt-5">
                <DashboardMetricCards :items="portalHealthCards" />
              </div>
            </div>

            <div
              class="rounded-[28px] border border-border/70 bg-card p-5 shadow-sm sm:p-6"
            >
              <DashboardSectionHeader
                icon="lucide:gallery-horizontal-end"
                :title="$t('tenant.dashboard.cockpit.widgetsTitle')"
                :description="$t('tenant.dashboard.cockpit.widgetsDesc')"
              />
              <div class="mt-5">
                <PluginDashboardWidgets
                  :empty-title="
                    $t('tenant.dashboard.cockpit.widgetsEmptyTitle')
                  "
                  :empty-description="
                    $t('tenant.dashboard.cockpit.widgetsEmptyDesc')
                  "
                />
              </div>
            </div>
          </div>

          <div
            class="rounded-[28px] border border-border/70 bg-card p-5 shadow-sm sm:p-6"
          >
            <DashboardSectionHeader
              icon="lucide:hard-drive"
              :title="$t('tenant.dashboard.cockpit.summaryTitle')"
              :description="$t('tenant.dashboard.cockpit.summaryDesc')"
            />
            <DashboardSummaryPanels :items="summaryPanels" />
          </div>
        </section>
      </div>
    </Spin>
  </div>
</template>
