<script setup lang="ts">
/**
 * EnumEditor — 枚举定义编辑器 + 状态机可视化
 *
 * 功能: 枚举增删改、枚举值管理 (value/label_zh/label_en/color/icon)、
 *       状态转换规则编辑、状态机流程图可视化
 */
import { computed } from 'vue';

import {
  Button,
  Card,
  Collapse,
  Divider,
  Empty,
  Input,
  Select,
  Tag,
} from 'ant-design-vue';

import { $t } from '#/locales';

import type {
  CrudConfig,
  EnumDefinition,
  EnumOption,
  StateTransition,
} from '../types';

const T = 'admin.dev.crudGenerator';

const TAG_COLORS = [
  'default', 'blue', 'green', 'red', 'orange', 'purple',
  'cyan', 'magenta', 'gold', 'lime', 'volcano', 'geekblue',
];

const props = defineProps<{
  config: CrudConfig;
}>();

const emit = defineEmits<{
  (e: 'update:config', config: CrudConfig): void;
}>();

// ============================================================
// Enum CRUD
// ============================================================

function addEnum() {
  const name = `Status${props.config.enums.length + 1}`;
  const newEnum: EnumDefinition = {
    name,
    description: '',
    values: [
      { value: 'active', label_zh: 'Active', label_en: 'Active', color: 'green' },
      { value: 'inactive', label_zh: 'Inactive', label_en: 'Inactive', color: 'red' },
    ],
    transitions: null,
  };
  emit('update:config', {
    ...props.config,
    enums: [...props.config.enums, newEnum],
  });
}

function removeEnum(index: number) {
  const enums = [...props.config.enums];
  enums.splice(index, 1);
  emit('update:config', { ...props.config, enums });
}

function updateEnum(index: number, key: keyof EnumDefinition, value: unknown) {
  const enums = props.config.enums.map((en, i) => {
    if (i === index) return { ...en, [key]: value };
    return en;
  });
  emit('update:config', { ...props.config, enums });
}

// ============================================================
// Enum values CRUD
// ============================================================

function addEnumValue(enumIndex: number) {
  const en = props.config.enums[enumIndex];
  if (!en) return;
  const newVal: EnumOption = {
    value: `value_${en.values.length + 1}`,
    label_zh: '',
    label_en: '',
    color: 'default',
  };
  updateEnum(enumIndex, 'values', [...en.values, newVal]);
}

function removeEnumValue(enumIndex: number, valueIndex: number) {
  const en = props.config.enums[enumIndex];
  if (!en) return;
  const values = [...en.values];
  values.splice(valueIndex, 1);
  updateEnum(enumIndex, 'values', values);
}

function updateEnumValue(
  enumIndex: number,
  valueIndex: number,
  key: keyof EnumOption,
  value: string,
) {
  const en = props.config.enums[enumIndex];
  if (!en) return;
  const values = en.values.map((v, i) => {
    if (i === valueIndex) return { ...v, [key]: value };
    return v;
  });
  updateEnum(enumIndex, 'values', values);
}

// ============================================================
// State transitions
// ============================================================

function addTransition(enumIndex: number) {
  const en = props.config.enums[enumIndex];
  if (!en) return;
  const newTransition: StateTransition = {
    from_state: en.values[0]?.value || '',
    to_state: en.values.length > 1 ? en.values[1]!.value : '',
    action: 'transition',
    label_zh: '转换',
    label_en: 'Transition',
    confirm: false,
  };
  const transitions = [...(en.transitions || []), newTransition];
  updateEnum(enumIndex, 'transitions', transitions);
}

function removeTransition(enumIndex: number, transIndex: number) {
  const en = props.config.enums[enumIndex];
  if (!en?.transitions) return;
  const transitions = [...en.transitions];
  transitions.splice(transIndex, 1);
  updateEnum(enumIndex, 'transitions', transitions.length > 0 ? transitions : null);
}

function updateTransition(
  enumIndex: number,
  transIndex: number,
  key: keyof StateTransition,
  value: unknown,
) {
  const en = props.config.enums[enumIndex];
  if (!en?.transitions) return;
  const transitions = en.transitions.map((t, i) => {
    if (i === transIndex) return { ...t, [key]: value };
    return t;
  });
  updateEnum(enumIndex, 'transitions', transitions);
}

// State options for transition selects
function getStateOptions(enumIndex: number) {
  const en = props.config.enums[enumIndex];
  if (!en) return [];
  return en.values.map((v) => ({
    label: `${v.label_zh || v.value} (${v.value})`,
    value: v.value,
  }));
}

// Active keys for Collapse
const activeKeys = computed(() =>
  props.config.enums.map((_, i) => String(i)),
);
</script>

<template>
  <div class="space-y-4">
    <!-- Empty state -->
    <Empty
      v-if="config.enums.length === 0"
      :description="$t(`${T}.enumEditor.title`)"
      class="py-8"
    >
      <Button type="primary" size="small" @click="addEnum">
        <template #icon>
          <span class="icon-[lucide--plus] size-3.5" />
        </template>
        {{ $t(`${T}.enumEditor.addEnum`) }}
      </Button>
    </Empty>

    <!-- Enum list -->
    <template v-else>
      <Collapse :active-key="activeKeys" size="small">
        <Collapse.Panel
          v-for="(en, enumIdx) in config.enums"
          :key="String(enumIdx)"
          :header="en.name"
        >
          <template #extra>
            <span
              class="icon-[lucide--trash-2] text-muted-foreground size-4 cursor-pointer hover:text-red-500"
              @click.stop="removeEnum(enumIdx)"
            />
          </template>

          <!-- Enum meta -->
          <div class="mb-3 grid grid-cols-2 gap-2">
            <Input
              :value="en.name"
              :placeholder="$t(`${T}.enumEditor.name`)"
              size="small"
              @change="(e: Event) => updateEnum(enumIdx, 'name', (e.target as HTMLInputElement).value)"
            />
            <Input
              :value="en.description"
              :placeholder="$t(`${T}.enumEditor.description`)"
              size="small"
              @change="(e: Event) => updateEnum(enumIdx, 'description', (e.target as HTMLInputElement).value)"
            />
          </div>

          <!-- Values -->
          <div class="text-muted-foreground mb-1 text-xs font-medium">
            {{ $t(`${T}.enumEditor.values`) }}
          </div>
          <div class="space-y-1">
            <div
              v-for="(val, valIdx) in en.values"
              :key="valIdx"
              class="flex items-center gap-1"
            >
              <Input
                :value="val.value"
                :placeholder="$t(`${T}.enumEditor.value`)"
                size="small"
                style="width: 90px"
                @change="(e: Event) => updateEnumValue(enumIdx, valIdx, 'value', (e.target as HTMLInputElement).value)"
              />
              <Input
                :value="val.label_zh"
                :placeholder="$t(`${T}.enumEditor.labelZh`)"
                size="small"
                style="width: 80px"
                @change="(e: Event) => updateEnumValue(enumIdx, valIdx, 'label_zh', (e.target as HTMLInputElement).value)"
              />
              <Input
                :value="val.label_en"
                :placeholder="$t(`${T}.enumEditor.labelEn`)"
                size="small"
                style="width: 80px"
                @change="(e: Event) => updateEnumValue(enumIdx, valIdx, 'label_en', (e.target as HTMLInputElement).value)"
              />
              <Select
                :value="val.color || 'default'"
                size="small"
                style="width: 90px"
                @change="(v: unknown) => updateEnumValue(enumIdx, valIdx, 'color', String(v))"
              >
                <Select.Option v-for="c in TAG_COLORS" :key="c" :value="c">
                  <Tag :color="c" class="m-0">{{ c }}</Tag>
                </Select.Option>
              </Select>
              <span
                class="icon-[lucide--x] text-muted-foreground size-3.5 cursor-pointer hover:text-red-500"
                @click="removeEnumValue(enumIdx, valIdx)"
              />
            </div>
          </div>
          <Button class="mt-2" size="small" @click="addEnumValue(enumIdx)">
            <template #icon>
              <span class="icon-[lucide--plus] size-3" />
            </template>
            {{ $t(`${T}.enumEditor.addValue`) }}
          </Button>

          <!-- State Transitions -->
          <Divider class="!my-3" orientation="left" plain>
            {{ $t(`${T}.enumEditor.transitions`) }}
          </Divider>

          <div v-if="!en.transitions || en.transitions.length === 0" class="text-muted-foreground text-xs">
            {{ $t(`${T}.enumEditor.noTransitions`) }}
          </div>
          <div v-else class="space-y-1">
            <div
              v-for="(trans, tIdx) in en.transitions"
              :key="tIdx"
              class="flex items-center gap-1"
            >
              <Select
                :value="trans.from_state"
                :options="getStateOptions(enumIdx)"
                size="small"
                style="width: 100px"
                @change="(v: unknown) => updateTransition(enumIdx, tIdx, 'from_state', v)"
              />
              <span class="icon-[lucide--arrow-right] text-muted-foreground size-3.5" />
              <Select
                :value="trans.to_state"
                :options="getStateOptions(enumIdx)"
                size="small"
                style="width: 100px"
                @change="(v: unknown) => updateTransition(enumIdx, tIdx, 'to_state', v)"
              />
              <Input
                :value="trans.label_zh"
                placeholder="操作名"
                size="small"
                style="width: 70px"
                @change="(e: Event) => updateTransition(enumIdx, tIdx, 'label_zh', (e.target as HTMLInputElement).value)"
              />
              <span
                class="icon-[lucide--x] text-muted-foreground size-3.5 cursor-pointer hover:text-red-500"
                @click="removeTransition(enumIdx, tIdx)"
              />
            </div>
          </div>
          <Button class="mt-2" size="small" @click="addTransition(enumIdx)">
            <template #icon>
              <span class="icon-[lucide--plus] size-3" />
            </template>
            {{ $t(`${T}.enumEditor.addTransition`) }}
          </Button>

          <!-- State Machine Visualization -->
          <div v-if="en.transitions && en.transitions.length > 0" class="mt-3">
            <Card size="small" :title="$t(`${T}.enumEditor.stateMachine`)">
              <div class="flex flex-wrap items-center gap-2">
                <template v-for="(trans, tIdx) in en.transitions" :key="tIdx">
                  <div class="bg-accent/30 flex items-center gap-1 rounded-md px-2 py-1 text-xs">
                    <Tag :color="en.values.find(v => v.value === trans.from_state)?.color || 'default'" class="m-0">
                      {{ en.values.find(v => v.value === trans.from_state)?.label_zh || trans.from_state }}
                    </Tag>
                    <span class="text-muted-foreground">→</span>
                    <span class="text-primary">{{ trans.label_zh }}</span>
                    <span class="text-muted-foreground">→</span>
                    <Tag :color="en.values.find(v => v.value === trans.to_state)?.color || 'default'" class="m-0">
                      {{ en.values.find(v => v.value === trans.to_state)?.label_zh || trans.to_state }}
                    </Tag>
                  </div>
                </template>
              </div>
            </Card>
          </div>
        </Collapse.Panel>
      </Collapse>

      <Button @click="addEnum">
        <template #icon>
          <span class="icon-[lucide--plus] size-3.5" />
        </template>
        {{ $t(`${T}.enumEditor.addEnum`) }}
      </Button>
    </template>
  </div>
</template>
