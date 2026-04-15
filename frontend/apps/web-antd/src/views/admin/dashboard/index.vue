<script lang="ts" setup>
import { useRouter } from 'vue-router';

import { useUserStore } from '@vben/stores';

import { Spin } from 'ant-design-vue';

import PluginDashboardWidgets from '#/components/business/plugin-slots/PluginDashboardWidgets.vue';
import { $t } from '#/locales';
import AdminDashboardGrowthChart from '#/views/_shared/charts/AdminDashboardGrowthChart.vue';
import DashboardActivityFeed from '#/views/_shared/dashboard/DashboardActivityFeed.vue';
import DashboardHeroBanner from '#/views/_shared/dashboard/DashboardHeroBanner.vue';
import DashboardRouteCardList from '#/views/_shared/dashboard/DashboardRouteCardList.vue';
import DashboardSectionHeader from '#/views/_shared/dashboard/DashboardSectionHeader.vue';
import DashboardSpotlightGrid from '#/views/_shared/dashboard/DashboardSpotlightGrid.vue';
import DashboardSummaryPanels from '#/views/_shared/dashboard/DashboardSummaryPanels.vue';

import { useAdminDashboard } from './use-admin-dashboard';

defineOptions({ name: 'Dashboard' });

const router = useRouter();
const userStore = useUserStore();
const {
  actionDeck,
  activityEntries,
  growthSummary,
  healthTone,
  heroActions,
  infrastructurePanels,
  loading,
  overviewCards,
  realtimeChips,
  runtimeValue,
  signalCards,
  spotlightCards,
  tenantGrowth,
} = useAdminDashboard();

function goTo(routePath: string) {
  void router.push(routePath);
}

</script>

<template>
  <div class="space-y-6 p-5">
    <DashboardHeroBanner
      :actions="heroActions"
      :badge="$t('admin.dashboard.command.badge')"
      :badge-dot-class="healthTone.dot"
      :chips="realtimeChips"
      :description="
        $t('admin.dashboard.command.description', {
          name: userStore.userInfo?.realName || $t('admin.dashboard.admin'),
        })
      "
      :metrics="overviewCards"
      :title="$t('admin.dashboard.platformConsole')"
      @select="goTo"
    >
      <template #footer>
        <DashboardSpotlightGrid :items="spotlightCards" />
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
                  {{ $t('admin.dashboard.controlTower.growthTitle') }}
                </h2>
                <p class="mt-1 text-sm text-muted-foreground">
                  {{ $t('admin.dashboard.controlTower.growthDesc') }}
                </p>
              </div>
              <div
                class="flex items-center gap-4 rounded-[20px] border border-border/60 bg-background/80 px-4 py-3"
              >
                <div>
                  <div
                    class="text-xs uppercase tracking-[0.18em] text-muted-foreground"
                  >
                    {{ $t('admin.dashboard.controlTower.recentWindow') }}
                  </div>
                  <div class="mt-2 text-2xl font-semibold text-foreground">
                    {{ growthSummary.recent }}
                  </div>
                </div>
                <div class="h-10 w-px bg-border"></div>
                <div>
                  <div
                    class="text-xs uppercase tracking-[0.18em] text-muted-foreground"
                  >
                    {{ $t('admin.dashboard.controlTower.deltaLabel') }}
                  </div>
                  <div
                    class="mt-2 text-2xl font-semibold"
                    :class="
                      growthSummary.delta >= 0
                        ? 'text-emerald-600 dark:text-emerald-300'
                        : 'text-destructive'
                    "
                  >
                    {{ growthSummary.delta }}%
                  </div>
                </div>
              </div>
            </div>

            <div class="mt-5">
              <AdminDashboardGrowthChart
                :data="tenantGrowth"
                :empty-text="$t('admin.dashboard.tenantGrowth.empty')"
              />
            </div>
          </div>

          <div
            class="rounded-[28px] border border-border/70 bg-card p-5 shadow-sm sm:p-6"
          >
            <DashboardSectionHeader
              icon="lucide:activity"
              :title="$t('admin.dashboard.activities.title')"
              :description="$t('admin.dashboard.controlTower.activitiesDesc')"
            />
            <DashboardActivityFeed
              :items="activityEntries"
              empty-height="420px"
              max-height="420px"
              :empty-text="$t('admin.dashboard.activities.empty')"
            />
          </div>
        </section>

        <section class="grid gap-6 xl:grid-cols-2">
          <div
            class="rounded-[28px] border border-border/70 bg-card p-5 shadow-sm sm:p-6"
          >
            <DashboardSectionHeader
              icon="lucide:siren"
              :title="$t('admin.dashboard.controlTower.signalsTitle')"
              :description="$t('admin.dashboard.controlTower.signalsDesc')"
            />
            <DashboardRouteCardList
              variant="signal"
              :columns="2"
              :items="signalCards"
              @select="goTo"
            />
          </div>

          <div
            class="rounded-[28px] border border-border/70 bg-card p-5 shadow-sm sm:p-6"
          >
            <DashboardSectionHeader
              icon="lucide:rocket"
              :title="$t('admin.dashboard.controlTower.actionsTitle')"
              :description="$t('admin.dashboard.controlTower.actionsDesc')"
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
          <div
            class="rounded-[28px] border border-border/70 bg-card p-5 shadow-sm sm:p-6"
          >
            <DashboardSectionHeader
              icon="lucide:network"
              :title="$t('admin.dashboard.infrastructure.title')"
              :description="$t('admin.dashboard.infrastructure.description')"
            />

            <DashboardSummaryPanels :items="infrastructurePanels" />

            <div
              class="mt-5 rounded-[22px] border border-border/60 bg-background/80 px-4 py-4"
            >
              <div class="flex items-center justify-between gap-3">
                <span class="text-sm text-muted-foreground">
                  {{ $t('admin.dashboard.infrastructure.runtime') }}
                </span>
                <span class="text-base font-semibold text-foreground">
                  {{ runtimeValue }}
                </span>
              </div>
            </div>
          </div>

          <div class="space-y-6">
            <div
              class="rounded-[28px] border border-border/70 bg-card p-5 shadow-sm sm:p-6"
            >
              <DashboardSectionHeader
                icon="lucide:gallery-horizontal-end"
                :title="$t('admin.dashboard.controlTower.widgetsTitle')"
                :description="$t('admin.dashboard.controlTower.widgetsDesc')"
              />
              <div class="mt-5">
                <PluginDashboardWidgets
                  :empty-title="
                    $t('admin.dashboard.controlTower.widgetsEmptyTitle')
                  "
                  :empty-description="
                    $t('admin.dashboard.controlTower.widgetsEmptyDesc')
                  "
                />
              </div>
            </div>
          </div>
        </section>
      </div>
    </Spin>
  </div>
</template>
