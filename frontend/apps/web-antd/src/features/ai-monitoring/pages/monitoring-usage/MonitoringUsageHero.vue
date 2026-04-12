<script lang="ts" setup>
import type { Dayjs } from 'dayjs';

import type { MonitoringScope } from '../../api';

import { Button, DatePicker } from 'ant-design-vue';

import AIPageHeroCard from '#/components/business/ai-page-hero/AIPageHeroCard.vue';
import { $t } from '#/locales';

import type { DateRange } from './use-monitoring-usage-dashboard';

defineOptions({ name: 'MonitoringUsageHero' });

interface PresetOption {
  key: string;
  label: string;
  value: DateRange;
}

interface HeroMetric {
  key: string;
  label: string;
  value: string;
}

interface HeroChip {
  key: string;
  icon: string;
  className: string;
  text: string;
}

defineProps<{
  dateRange: DateRange;
  heroChips: HeroChip[];
  heroMetrics: HeroMetric[];
  i18nPrefix: string;
  presets: PresetOption[];
  scope: MonitoringScope;
  title: string;
}>();

const emits = defineEmits<{
  preset: [range: DateRange];
  'range-change': [range: DateRange];
}>();

function handleDateChange(value: [Dayjs, Dayjs] | [string, string] | null) {
  if (!value) {
    return;
  }
  if (typeof value[0] === 'string' || typeof value[1] === 'string') {
    return;
  }
  emits('range-change', value as DateRange);
}
</script>

<template>
  <AIPageHeroCard
    :chips="heroChips"
    :description="$t(`${i18nPrefix}.pageDesc`)"
    icon="lucide:chart-column-big"
    icon-wrap-class="bg-primary/10 text-primary"
    :metrics="heroMetrics"
    :title="title"
  >
    <template #actions>
      <Button
        v-for="preset in presets"
        :key="preset.key"
        size="small"
        @click="emits('preset', preset.value)"
      >
        {{ preset.label }}
      </Button>
      <DatePicker.RangePicker
        :value="dateRange"
        class="monitoring-range-picker w-64"
        format="YYYY-MM-DD"
        :allow-clear="false"
        :id="`${scope}-usage-range`"
        :name="`${scope}-usage-range`"
        size="small"
        @change="handleDateChange"
      />
    </template>
  </AIPageHeroCard>
</template>
