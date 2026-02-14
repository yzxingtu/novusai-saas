<script setup lang="ts">
import { ref } from 'vue';

import {
  Button,
  Checkbox,
  Empty,
  Input,
  Select,
  Table,
  Tooltip,
} from 'ant-design-vue';

import { $t } from '#/locales';

import type { CrudConfig, FieldConfig } from '../types';

import {
  createDefaultField,
  FIELD_TYPE_OPTIONS,
  inferFieldByName,
} from '../composables/field-inference';

import FieldDetailDrawer from './FieldDetailDrawer.vue';

const props = defineProps<{
  config: CrudConfig;
}>();

const emit = defineEmits<{
  (e: 'update:config', config: CrudConfig): void;
  (e: 'snapshot'): void;
}>();

const T = 'admin.dev.crudGenerator.field';

const editingField = ref<FieldConfig | null>(null);
const drawerVisible = ref(false);

function addField() {
  const fields = [...props.config.fields, createDefaultField()];
  emit('update:config', { ...props.config, fields });
  emit('snapshot');
}

function removeField(index: number) {
  const fields = props.config.fields.filter((_, i) => i !== index);
  emit('update:config', { ...props.config, fields });
  emit('snapshot');
}

function openDetail(field: FieldConfig) {
  editingField.value = field;
  drawerVisible.value = true;
}

function closeDetail() {
  drawerVisible.value = false;
  editingField.value = null;
}

function onFieldNameChange(index: number, val: string) {
  const field = props.config.fields[index];
  if (!field) return;

  let updated: FieldConfig = { ...field, name: val };
  if (val) {
    const inferred = inferFieldByName(val);
    if (inferred) {
      updated = { ...updated, ...inferred, name: val };
    }
  }

  const fields = props.config.fields.map((f, i) => (i === index ? updated : f));
  emit('update:config', { ...props.config, fields });
}

function moveField(fromIndex: number, direction: -1 | 1) {
  const toIndex = fromIndex + direction;
  if (toIndex < 0 || toIndex >= props.config.fields.length) return;
  const fields = [...props.config.fields];
  const temp = fields[fromIndex]!;
  fields[fromIndex] = fields[toIndex]!;
  fields[toIndex] = temp;
  emit('update:config', { ...props.config, fields });
  emit('snapshot');
}

const columns = [
  {
    title: '#',
    dataIndex: 'sort',
    width: 60,
    align: 'center' as const,
  },
  {
    title: $t(`${T}.name`),
    dataIndex: 'name',
    width: 150,
  },
  {
    title: $t(`${T}.type`),
    dataIndex: 'type',
    width: 120,
  },
  {
    title: $t(`${T}.labelZh`),
    dataIndex: 'label_zh',
    width: 120,
  },
  {
    title: $t(`${T}.labelEn`),
    dataIndex: 'label_en',
    width: 120,
  },
  {
    title: $t(`${T}.required`),
    dataIndex: 'required',
    width: 60,
    align: 'center' as const,
  },
  {
    title: $t(`${T}.searchable`),
    dataIndex: 'searchable',
    width: 70,
    align: 'center' as const,
  },
  {
    title: $t(`${T}.inList`),
    dataIndex: 'in_list',
    width: 60,
    align: 'center' as const,
  },
  {
    title: $t(`${T}.inForm`),
    dataIndex: 'in_form',
    width: 60,
    align: 'center' as const,
  },
  {
    title: '',
    dataIndex: 'actions',
    width: 90,
    align: 'center' as const,
  },
];
</script>

<template>
  <div class="step-field-define">
    <!-- Toolbar -->
    <div class="mb-3 flex items-center justify-between">
      <div class="text-muted-foreground text-sm">
        {{ config.fields.length }} {{ $t(`${T}.title`).toLowerCase() }}
      </div>
      <div class="flex items-center gap-2">
        <Button size="small" type="dashed" @click="addField">
          <template #icon>
            <span class="icon-[lucide--plus] size-3.5" />
          </template>
          {{ $t(`${T}.add`) }}
        </Button>
      </div>
    </div>

    <!-- Field Table -->
    <Table
      v-if="config.fields.length > 0"
      :columns="columns"
      :data-source="config.fields"
      :pagination="false"
      :row-key="(_r: FieldConfig, idx?: number) => idx ?? 0"
      bordered
      size="small"
    >
      <template #bodyCell="{ column, index }">
        <!-- Sort buttons -->
        <template v-if="column.dataIndex === 'sort'">
          <div class="flex items-center justify-center gap-0.5">
            <Button
              :disabled="index === 0"
              size="small"
              type="text"
              @click="moveField(index, -1)"
            >
              <template #icon>
                <span class="icon-[lucide--chevron-up] size-3" />
              </template>
            </Button>
            <Button
              :disabled="index === config.fields.length - 1"
              size="small"
              type="text"
              @click="moveField(index, 1)"
            >
              <template #icon>
                <span class="icon-[lucide--chevron-down] size-3" />
              </template>
            </Button>
          </div>
        </template>

        <!-- Name -->
        <template v-else-if="column.dataIndex === 'name'">
          <Input
            :placeholder="$t(`${T}.namePlaceholder`)"
            :value="config.fields[index]!.name"
            size="small"
            @change="(e: Event) => onFieldNameChange(index, (e.target as HTMLInputElement).value)"
          />
        </template>

        <!-- Type -->
        <template v-else-if="column.dataIndex === 'type'">
          <Select
            v-model:value="config.fields[index]!.type"
            :options="FIELD_TYPE_OPTIONS"
            size="small"
            style="width: 100%"
          />
        </template>

        <!-- Label ZH -->
        <template v-else-if="column.dataIndex === 'label_zh'">
          <Input
            v-model:value="config.fields[index]!.label_zh"
            :placeholder="$t(`${T}.labelZhPlaceholder`)"
            size="small"
          />
        </template>

        <!-- Label EN -->
        <template v-else-if="column.dataIndex === 'label_en'">
          <Input
            v-model:value="config.fields[index]!.label_en"
            :placeholder="$t(`${T}.labelEnPlaceholder`)"
            size="small"
          />
        </template>

        <!-- Required -->
        <template v-else-if="column.dataIndex === 'required'">
          <Checkbox v-model:checked="config.fields[index]!.required" />
        </template>

        <!-- Searchable -->
        <template v-else-if="column.dataIndex === 'searchable'">
          <Checkbox v-model:checked="config.fields[index]!.searchable" />
        </template>

        <!-- In List -->
        <template v-else-if="column.dataIndex === 'in_list'">
          <Checkbox v-model:checked="config.fields[index]!.in_list" />
        </template>

        <!-- In Form -->
        <template v-else-if="column.dataIndex === 'in_form'">
          <Checkbox v-model:checked="config.fields[index]!.in_form" />
        </template>

        <!-- Actions -->
        <template v-else-if="column.dataIndex === 'actions'">
          <div class="flex items-center justify-center gap-1">
            <Tooltip :title="$t(`${T}.detail`)">
              <Button
                size="small"
                type="text"
                @click="openDetail(config.fields[index]!)"
              >
                <template #icon>
                  <span class="icon-[lucide--settings-2] size-3.5" />
                </template>
              </Button>
            </Tooltip>
            <Button
              danger
              size="small"
              type="text"
              @click="removeField(index)"
            >
              <template #icon>
                <span class="icon-[lucide--trash-2] size-3.5" />
              </template>
            </Button>
          </div>
        </template>
      </template>
    </Table>

    <Empty
      v-else
      :description="$t(`${T}.empty`)"
      class="py-12"
    />

    <!-- Field Detail Drawer -->
    <FieldDetailDrawer
      :field="editingField"
      :open="drawerVisible"
      @close="closeDetail"
      @snapshot="emit('snapshot')"
    />
  </div>
</template>
