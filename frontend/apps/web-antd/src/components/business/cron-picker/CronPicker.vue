<script lang="ts" setup>
defineOptions({ name: 'CronPicker' });

import { computed, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Col,
  Divider,
  Flex,
  Input,
  Popover,
  Row,
  Tag,
  Typography,
} from 'ant-design-vue';

import { $t } from '#/locales';

const props = withDefaults(
  defineProps<{
    value?: string;
    disabled?: boolean;
  }>(),
  {
    value: '',
    disabled: false,
  },
);

const emit = defineEmits<{
  'update:value': [value: string];
}>();

const cronValue = ref(props.value || '');

interface Preset {
  label: string;
  value: string;
  description: string;
}

const presets = computed<Preset[]>(() => [
  {
    label: $t('common.cronPicker.presets.everyMinute'),
    value: '* * * * *',
    description: $t('common.cronPicker.presets.everyMinuteDesc'),
  },
  {
    label: $t('common.cronPicker.presets.every5Min'),
    value: '*/5 * * * *',
    description: $t('common.cronPicker.presets.every5MinDesc'),
  },
  {
    label: $t('common.cronPicker.presets.every15Min'),
    value: '*/15 * * * *',
    description: $t('common.cronPicker.presets.every15MinDesc'),
  },
  {
    label: $t('common.cronPicker.presets.every30Min'),
    value: '*/30 * * * *',
    description: $t('common.cronPicker.presets.every30MinDesc'),
  },
  {
    label: $t('common.cronPicker.presets.everyHour'),
    value: '0 * * * *',
    description: $t('common.cronPicker.presets.everyHourDesc'),
  },
  {
    label: $t('common.cronPicker.presets.daily2AM'),
    value: '0 2 * * *',
    description: $t('common.cronPicker.presets.daily2AMDesc'),
  },
  {
    label: $t('common.cronPicker.presets.daily6AM'),
    value: '0 6 * * *',
    description: $t('common.cronPicker.presets.daily6AMDesc'),
  },
  {
    label: $t('common.cronPicker.presets.weeklyMon'),
    value: '0 2 * * 1',
    description: $t('common.cronPicker.presets.weeklyMonDesc'),
  },
  {
    label: $t('common.cronPicker.presets.monthly1st'),
    value: '0 2 1 * *',
    description: $t('common.cronPicker.presets.monthly1stDesc'),
  },
]);

const minute = ref('*');
const hour = ref('*');
const dayOfMonth = ref('*');
const month = ref('*');
const dayOfWeek = ref('*');

function parseCron(expression: string) {
  const parts = expression.trim().split(/\s+/);
  if (parts.length === 5) {
    minute.value = parts[0]!;
    hour.value = parts[1]!;
    dayOfMonth.value = parts[2]!;
    month.value = parts[3]!;
    dayOfWeek.value = parts[4]!;
  }
}

const buildExpression = computed(() => {
  return `${minute.value} ${hour.value} ${dayOfMonth.value} ${month.value} ${dayOfWeek.value}`;
});

const cronDescription = computed(() => {
  const expr = cronValue.value || '';
  const matched = presets.value.find((p) => p.value === expr);
  if (matched) return matched.description;
  return describeCron(expr);
});

function describeCron(expr: string): string {
  if (!expr) return '';
  const parts = expr.trim().split(/\s+/);
  if (parts.length !== 5) return $t('common.cronPicker.invalidCron');
  return `${$t('common.cronPicker.fields.minute')}: ${parts[0]}, ${$t('common.cronPicker.fields.hour')}: ${parts[1]}, ${$t('common.cronPicker.fields.dayOfMonth')}: ${parts[2]}, ${$t('common.cronPicker.fields.month')}: ${parts[3]}, ${$t('common.cronPicker.fields.dayOfWeek')}: ${parts[4]}`;
}

const nextExecutions = computed(() => {
  try {
    return getNextExecutions(cronValue.value, 5);
  } catch {
    return [];
  }
});

function getNextExecutions(expr: string, count: number): string[] {
  if (!expr) return [];
  const parts = expr.trim().split(/\s+/);
  if (parts.length !== 5) return [];

  const results: string[] = [];
  const now = new Date();
  let current = new Date(now.getTime());
  current.setSeconds(0, 0);
  current.setMinutes(current.getMinutes() + 1);

  for (let i = 0; i < 365 * 24 * 60 && results.length < count; i++) {
    if (matchesCron(current, parts as [string, string, string, string, string])) {
      results.push(formatDateTime(current));
    }
    current = new Date(current.getTime() + 60_000);
  }
  return results;
}

function matchesCron(
  date: Date,
  parts: [string, string, string, string, string],
): boolean {
  return (
    matchField(date.getMinutes(), parts[0], 0, 59) &&
    matchField(date.getHours(), parts[1], 0, 23) &&
    matchField(date.getDate(), parts[2], 1, 31) &&
    matchField(date.getMonth() + 1, parts[3], 1, 12) &&
    matchField(date.getDay(), parts[4], 0, 6)
  );
}

function matchField(value: number, field: string, _min: number, _max: number): boolean {
  if (field === '*') return true;
  if (field.includes('/')) {
    const [, step] = field.split('/');
    return value % Number(step) === 0;
  }
  if (field.includes(',')) {
    return field.split(',').map(Number).includes(value);
  }
  if (field.includes('-')) {
    const [from, to] = field.split('-').map(Number);
    return value >= from! && value <= to!;
  }
  return value === Number(field);
}

function formatDateTime(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function selectPreset(preset: Preset) {
  cronValue.value = preset.value;
  parseCron(preset.value);
  emit('update:value', preset.value);
}

function onCustomInput(val: string) {
  cronValue.value = val;
  parseCron(val);
  emit('update:value', val);
}

function applyBuilder() {
  cronValue.value = buildExpression.value;
  emit('update:value', buildExpression.value);
}

watch(
  () => props.value,
  (val) => {
    if (val !== cronValue.value) {
      cronValue.value = val || '';
      parseCron(val || '');
    }
  },
);

const activePreset = computed(() => presets.value.find((p) => p.value === cronValue.value));
</script>

<template>
  <div class="cron-picker w-full">
    <Flex :gap="8" align="center">
      <Input
        :value="cronValue"
        :disabled="disabled"
        :placeholder="$t('common.cronPicker.placeholder')"
        class="flex-1"
        @change="(e: any) => onCustomInput(e.target.value)"
      />
      <Popover
        trigger="click"
        placement="bottomRight"
        :overlay-style="{ width: '480px' }"
      >
        <Button :disabled="disabled" type="dashed" size="small">
          <IconifyIcon icon="lucide:calendar-clock" class="mr-1 size-3.5" />
          {{ $t('common.cronPicker.helper') }}
        </Button>
        <template #content>
          <div class="p-1">
            <!-- 快捷预设 -->
            <Typography.Text strong class="mb-2 block text-sm">
              {{ $t('common.cronPicker.quickPresets') }}
            </Typography.Text>
            <Flex wrap="wrap" :gap="6" class="mb-3">
              <Tag
                v-for="preset in presets"
                :key="preset.value"
                :color="activePreset?.value === preset.value ? 'blue' : 'default'"
                class="cursor-pointer"
                @click="selectPreset(preset)"
              >
                {{ preset.label }}
              </Tag>
            </Flex>

            <Divider class="!my-3" />

            <!-- 可视化构建器 -->
            <Typography.Text strong class="mb-2 block text-sm">
              {{ $t('common.cronPicker.visualBuilder') }}
            </Typography.Text>
            <Row :gutter="[8, 8]" class="mb-2">
              <Col :span="4">
                <div class="text-center text-xs text-muted-foreground">
                  {{ $t('common.cronPicker.fields.minute') }}
                </div>
                <Input v-model:value="minute" size="small" class="text-center" />
              </Col>
              <Col :span="4">
                <div class="text-center text-xs text-muted-foreground">
                  {{ $t('common.cronPicker.fields.hour') }}
                </div>
                <Input v-model:value="hour" size="small" class="text-center" />
              </Col>
              <Col :span="5">
                <div class="text-center text-xs text-muted-foreground">
                  {{ $t('common.cronPicker.fields.dayOfMonth') }}
                </div>
                <Input v-model:value="dayOfMonth" size="small" class="text-center" />
              </Col>
              <Col :span="4">
                <div class="text-center text-xs text-muted-foreground">
                  {{ $t('common.cronPicker.fields.month') }}
                </div>
                <Input v-model:value="month" size="small" class="text-center" />
              </Col>
              <Col :span="5">
                <div class="text-center text-xs text-muted-foreground">
                  {{ $t('common.cronPicker.fields.dayOfWeek') }}
                </div>
                <Input v-model:value="dayOfWeek" size="small" class="text-center" />
              </Col>
              <Col :span="2" class="flex items-end">
                <Button type="primary" size="small" @click="applyBuilder">
                  <IconifyIcon icon="lucide:check" class="size-3" />
                </Button>
              </Col>
            </Row>
            <Typography.Text type="secondary" class="text-xs">
              {{ buildExpression }}
            </Typography.Text>

            <!-- 执行时间预览 -->
            <template v-if="cronValue && nextExecutions.length > 0">
              <Divider class="!my-3" />
              <Typography.Text strong class="mb-1 block text-sm">
                {{ $t('common.cronPicker.nextExecutions') }}
              </Typography.Text>
              <div class="space-y-1">
                <div
                  v-for="(time, idx) in nextExecutions"
                  :key="idx"
                  class="flex items-center gap-2 text-xs text-muted-foreground"
                >
                  <IconifyIcon icon="lucide:clock" class="size-3 text-primary" />
                  {{ time }}
                </div>
              </div>
            </template>
          </div>
        </template>
      </Popover>
    </Flex>
    <div v-if="cronDescription && cronValue" class="mt-1 text-xs text-muted-foreground">
      {{ cronDescription }}
    </div>
  </div>
</template>
