<script lang="ts" setup>
import type { ItemType } from 'ant-design-vue/es/menu';

import type { PageOperation } from './page-operation-types';
import type {
  PageAIDiagnostics,
  PageAIStatBadge,
} from './use-page-ai-capability';

import AIChatPanelUtilityActions from './AIChatPanelUtilityActions.vue';
import PageAIRail from './PageAIRail.vue';

defineOptions({ name: 'AIChatPanelToolbarRow' });

const props = withDefaults(
  defineProps<{
    canForceReroute?: boolean;
    forceRerouteNextTurn?: boolean;
    hasExpandablePageAIDetails?: boolean;
    hasHeaderVariableValues?: boolean;
    hasPageAI?: boolean;
    headerMoreHasAttention?: boolean;
    headerMoreMenuItems?: ItemType[];
    pageAIDetailsExpanded?: boolean;
    pageAIDiagnostics?: null | PageAIDiagnostics;
    pageAIFallbackOnly?: boolean;
    pageAIOperationCount?: number;
    pageAIRailTooltip?: string;
    pageAIRemainingOperationCount?: number;
    pageAIStatBadges?: PageAIStatBadge[];
    pageAISummary?: string;
    pageAIVisibleOperations?: PageOperation[];
    resolvedPageAITitle?: string;
    showHeaderMoreMenu?: boolean;
    showHeaderVarsButton?: boolean;
    showHistory?: boolean;
    showRerouteButton?: boolean;
  }>(),
  {
    canForceReroute: false,
    forceRerouteNextTurn: false,
    hasExpandablePageAIDetails: false,
    hasHeaderVariableValues: false,
    hasPageAI: false,
    headerMoreHasAttention: false,
    headerMoreMenuItems: () => [],
    pageAIDetailsExpanded: false,
    pageAIDiagnostics: null,
    pageAIFallbackOnly: false,
    pageAIOperationCount: 0,
    pageAIRailTooltip: '',
    pageAIRemainingOperationCount: 0,
    pageAIStatBadges: () => [],
    pageAISummary: '',
    pageAIVisibleOperations: () => [],
    resolvedPageAITitle: '',
    showHeaderMoreMenu: false,
    showHeaderVarsButton: false,
    showHistory: false,
    showRerouteButton: false,
  },
);

const emit = defineEmits<{
  editVars: [];
  expandAllOperations: [];
  newChat: [];
  toggleHistory: [];
  togglePageDetails: [];
  toggleReroute: [];
}>();
</script>

<template>
  <div
    data-testid="ai-panel-toolbar-row"
    class="w-full shrink-0 px-3 pb-2 pt-1"
    :class="hasPageAI ? '' : 'flex justify-end'"
  >
    <PageAIRail
      v-if="hasPageAI"
      data-testid="ai-panel-page-ai-row"
      :diagnostics="pageAIDiagnostics"
      :fallback-only="pageAIFallbackOnly"
      :has-page-a-i="hasPageAI"
      :has-expandable-details="hasExpandablePageAIDetails"
      :details-expanded="pageAIDetailsExpanded"
      :page-a-i-rail-tooltip="pageAIRailTooltip"
      :operation-count="pageAIOperationCount"
      :page-a-i-summary="pageAISummary"
      :page-a-i-stat-badges="pageAIStatBadges"
      :page-a-i-visible-operations="pageAIVisibleOperations"
      :page-a-i-remaining-operation-count="pageAIRemainingOperationCount"
      :resolved-page-a-i-title="resolvedPageAITitle"
      @toggle-details="emit('togglePageDetails')"
      @expand-all-operations="emit('expandAllOperations')"
    >
      <template #actions>
        <AIChatPanelUtilityActions
          :can-force-reroute="canForceReroute"
          compact
          :force-reroute-next-turn="forceRerouteNextTurn"
          :has-header-variable-values="hasHeaderVariableValues"
          :header-more-has-attention="headerMoreHasAttention"
          :header-more-menu-items="headerMoreMenuItems"
          :show-header-more-menu="showHeaderMoreMenu"
          :show-header-vars-button="showHeaderVarsButton"
          :show-history="showHistory"
          :show-reroute-button="showRerouteButton"
          @edit-vars="emit('editVars')"
          @new-chat="emit('newChat')"
          @toggle-history="emit('toggleHistory')"
          @toggle-reroute="emit('toggleReroute')"
        />
      </template>
    </PageAIRail>

    <AIChatPanelUtilityActions
      v-else
      :can-force-reroute="canForceReroute"
      :force-reroute-next-turn="forceRerouteNextTurn"
      :has-header-variable-values="hasHeaderVariableValues"
      :header-more-has-attention="headerMoreHasAttention"
      :header-more-menu-items="headerMoreMenuItems"
      :show-header-more-menu="showHeaderMoreMenu"
      :show-header-vars-button="showHeaderVarsButton"
      :show-history="showHistory"
      :show-reroute-button="showRerouteButton"
      @edit-vars="emit('editVars')"
      @new-chat="emit('newChat')"
      @toggle-history="emit('toggleHistory')"
      @toggle-reroute="emit('toggleReroute')"
    />
  </div>
</template>
