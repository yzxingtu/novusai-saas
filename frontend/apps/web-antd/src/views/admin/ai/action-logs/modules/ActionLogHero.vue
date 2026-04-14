<script lang="ts" setup>
import { computed } from 'vue';

import { $t } from '#/locales';

import AIPageHeroCard from '../../_shared/AIPageHeroCard.vue';

defineOptions({ name: 'ActionLogHero' });

const heroChips = computed(() => [
  {
    key: 'audit',
    icon: 'lucide:shield-check',
    className: 'bg-sky-500/10 text-sky-700 dark:text-sky-200',
    text: `${$t('admin.ai.actionLog.actionType')} / ${$t('admin.ai.actionLog.actionLevel')} / ${$t('admin.ai.actionLog.status')}`,
  },
  {
    key: 'payload',
    icon: 'lucide:braces',
    className: 'bg-background/90 text-foreground',
    text: `${$t('admin.ai.actionLog.requestTab')} / ${$t('admin.ai.actionLog.responseTab')} / ${$t('admin.ai.actionLog.errorTab')}`,
  },
  {
    key: 'trace',
    icon: 'lucide:file-search',
    className: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-200',
    text: `${$t('admin.ai.actionLog.tenantInfo')} / ${$t('admin.ai.actionLog.executionTime')} / ${$t('admin.ai.actionLog.detailTitle')}`,
  },
]);
</script>

<template>
  <AIPageHeroCard
    :chips="heroChips"
    :description="$t('admin.ai.actionLog.pageDesc')"
    icon="lucide:shield-check"
    icon-wrap-class="bg-primary/10 text-primary"
    :title="$t('admin.ai.actionLog.title')"
  />
</template>
