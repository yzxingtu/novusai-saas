<script lang="ts" setup>
defineOptions({ name: 'CronPicker' });

import { computed, ref, watch } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  Input,
  Select,
  Segmented,
  Tag,
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
const mode = ref<'custom' | 'preset'>('preset');

interface Preset {
  label: string;
  value: string;
  description: string;
  icon: string;
}

const presets = computed<Preset[]>(() => [
  {
    label: $t('common.cronPicker.presets.everyMinute'),
    value: '* * * * *',
    description: $t('common.cronPicker.presets.everyMinuteDesc'),
    icon: 'lucide:zap',
  },
  {
    label: $t('common.cronPicker.presets.every5Min'),
    value: '*/5 * * * *',
    description: $t('common.cronPicker.presets.every5MinDesc'),
    icon: 'lucide:timer',
  },
  {
    label: $t('common.cronPicker.presets.every15Min'),
    value: '*/15 * * * *',
    description: $t('common.cronPicker.presets.every15MinDesc'),
    icon: 'lucide:timer',
  },
  {
    label: $t('common.cronPicker.presets.every30Min'),
    value: '*/30 * * * *',
    description: $t('common.cronPicker.presets.every30MinDesc'),
    icon: 'lucide:timer',
  },
  {
    label: $t('common.cronPicker.presets.everyHour'),
    value: '0 * * * *',
    description: $t('common.cronPicker.presets.everyHourDesc'),
    icon: 'lucide:clock',
  },
  {
    label: $t('common.cronPicker.presets.daily2AM'),
    value: '0 2 * * *',
    description: $t('common.cronPicker.presets.daily2AMDesc'),
    icon: 'lucide:moon',
  },
  {
    label: $t('common.cronPicker.presets.daily6AM'),
    value: '0 6 * * *',
    description: $t('common.cronPicker.presets.daily6AMDesc'),
    icon: 'lucide:sunrise',
  },
  {
    label: $t('common.cronPicker.presets.weeklyMon'),
    value: '0 2 * * 1',
    description: $t('common.cronPicker.presets.weeklyMonDesc'),
    icon: 'lucide:calendar',
  },
  {
    label: $t('common.cronPicker.presets.monthly1st'),
    value: '0 2 1 * *',
    description: $t('common.cronPicker.presets.monthly1stDesc'),
    icon: 'lucide:calendar-days',
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
    return getNextExecutions(cronValue.value, 3);
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

function onFieldChange() {
  cronValue.value = buildExpression.value;
  emit('update:value', buildExpression.value);
}

function onModeChange(val: string | number) {
  mode.value = val as 'custom' | 'preset';
  if (val === 'preset' && cronValue.value) {
    parseCron(cronValue.value);
  }
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

if (props.value) {
  parseCron(props.value);
  const isPreset = presets.value.some((p) => p.value === props.value);
  mode.value = isPreset ? 'preset' : 'custom';
}

const activePreset = computed(() => presets.value.find((p) => p.value === cronValue.value));

const minuteOptions = computed(() => {
  const opts = [{ label: `* (${$t('common.cronPicker.every')})`, value: '*' }];
  for (const step of [5, 10, 15, 30]) {
    opts.push({ label: `*/${step}`, value: `*/${step}` });
  }
  for (let i = 0; i <= 59; i++) {
    opts.push({ label: String(i), value: String(i) });
  }
  return opts;
});

const hourOptions = computed(() => {
  const opts = [{ label: `* (${$t('common.cronPicker.every')})`, value: '*' }];
  for (let i = 0; i <= 23; i++) {
    opts.push({ label: `${i}:00`, value: String(i) });
  }
  return opts;
});

const dayOfMonthOptions = computed(() => {
  const opts = [{ label: `* (${$t('common.cronPicker.every')})`, value: '*' }];
  for (let i = 1; i <= 31; i++) {
    opts.push({ label: String(i), value: String(i) });
  }
  return opts;
});

const monthOptions = computed(() => {
  const names = $t('common.cronPicker.monthNames').split(',');
  const opts = [{ label: `* (${$t('common.cronPicker.every')})`, value: '*' }];
  for (let i = 1; i <= 12; i++) {
    opts.push({ label: `${i} - ${names[i - 1]?.trim() ?? ''}`, value: String(i) });
  }
  return opts;
});

const dayOfWeekOptions = computed(() => {
  const names = $t('common.cronPicker.dayNames').split(',');
  const opts = [{ label: `* (${$t('common.cronPicker.every')})`, value: '*' }];
  for (let i = 0; i <= 6; i++) {
    opts.push({ label: `${i} - ${names[i]?.trim() ?? ''}`, value: String(i) });
  }
  return opts;
});
</script>

<template>
  <div class="cron-picker w-full">
    <!-- 模式切换 -->
    <Segmented
      :value="mode"
      :disabled="disabled"
      :options="[
        { label: $t('common.cronPicker.quickPresets'), value: 'preset' },
        { label: $t('common.cronPicker.customMode'), value: 'custom' },
      ]"
      class="mb-3"
      block
      @change="onModeChange"
    />

    <!-- 预设模式 -->
    <div v-if="mode === 'preset'" class="grid grid-cols-3 gap-2">
      <div
        v-for="preset in presets"
        :key="preset.value"
        class="cursor-pointer rounded-lg border px-3 py-2 transition-all"
        :class="
          activePreset?.value === preset.value
            ? 'border-primary bg-primary/5 shadow-sm'
            : 'border-border hover:border-primary/30 hover:bg-accent/30'
        "
        @click="selectPreset(preset)"
      >
        <div class="flex items-center gap-1.5">
          <IconifyIcon
            :icon="preset.icon"
            class="size-3.5 shrink-0"
            :class="activePreset?.value === preset.value ? 'text-primary' : 'text-muted-foreground'"
          />
          <span
            class="text-xs font-medium"
            :class="activePreset?.value === preset.value ? 'text-primary' : 'text-foreground'"
          >
            {{ preset.label }}
          </span>
        </div>
        <div class="mt-0.5 pl-5 text-[11px] text-muted-foreground">
          {{ preset.description }}
        </div>
      </div>
    </div>

    <!-- 自定义模式 -->
    <div v-else>
      <!-- 可视化字段选择器 -->
      <div class="mb-3 grid grid-cols-5 gap-2">
        <div v-for="field in [
          { key: 'minute', label: $t('common.cronPicker.fields.minute'), model: minute, options: minuteOptions },
          { key: 'hour', label: $t('common.cronPicker.fields.hour'), model: hour, options: hourOptions },
          { key: 'dayOfMonth', label: $t('common.cronPicker.fields.dayOfMonth'), model: dayOfMonth, options: dayOfMonthOptions },
          { key: 'month', label: $t('common.cronPicker.fields.month'), model: month, options: monthOptions },
          { key: 'dayOfWeek', label: $t('common.cronPicker.fields.dayOfWeek'), model: dayOfWeek, options: dayOfWeekOptions },
        ]" :key="field.key" class="flex flex-col gap-1">
          <span class="text-center text-xs font-medium text-muted-foreground">
            {{ field.label }}
          </span>
          <Select
            :value="field.model"
            size="small"
            :disabled="disabled"
            show-search
            :options="field.options"
            @change="(val: unknown) => {
              const v = String(val);
              if (field.key === 'minute') minute = v;
              else if (field.key === 'hour') hour = v;
              else if (field.key === 'dayOfMonth') dayOfMonth = v;
              else if (field.key === 'month') month = v;
              else if (field.key === 'dayOfWeek') dayOfWeek = v;
              onFieldChange();
            }"
          />
        </div>
      </div>

      <!-- 手动输入 -->
      <div class="flex items-center gap-2">
        <span class="shrink-0 text-xs text-muted-foreground">
          {{ $t('common.cronPicker.expression') }}:
        </span>
        <Input
          :value="cronValue"
          :disabled="disabled"
          :placeholder="$t('common.cronPicker.placeholder')"
          size="small"
          class="font-mono"
          @change="(e: Event) => onCustomInput((e.target as HTMLInputElement).value)"
        />
      </div>
    </div>

    <!-- 底部信息栏：当前表达式 + 描述 + 下次执行 -->
    <div
      v-if="cronValue"
      class="mt-3 rounded-lg border border-border bg-accent/30 p-2.5"
    >
      <div class="flex items-center gap-2">
        <Tag color="blue" class="!m-0 font-mono">{{ cronValue }}</Tag>
        <span v-if="cronDescription" class="text-xs text-muted-foreground">
          {{ cronDescription }}
        </span>
      </div>
      <div
        v-if="nextExecutions.length > 0"
        class="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1"
      >
        <span class="text-[11px] font-medium text-muted-foreground/70">
          {{ $t('common.cronPicker.nextExecutions') }}:
        </span>
        <span
          v-for="(time, idx) in nextExecutions"
          :key="idx"
          class="flex items-center gap-1 text-[11px] text-muted-foreground"
        >
          <IconifyIcon icon="lucide:clock" class="size-3 text-primary/60" />
          {{ time }}
        </span>
      </div>
    </div>
  </div>
</template>
