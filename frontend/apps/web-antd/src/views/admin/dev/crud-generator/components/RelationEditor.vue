<script setup lang="ts">
import {
  Button,
  Empty,
  Input,
  Select,
  Switch,
  Table,
} from 'ant-design-vue';

import { $t } from '#/locales';

import type { RelationConfig } from '../types';

const props = defineProps<{
  relations: RelationConfig[];
}>();

const emit = defineEmits<{
  snapshot: [];
}>();

const T = 'admin.dev.crudGenerator.relation';

const relationTypeOptions = [
  { value: 'belongs_to', labelKey: 'belongsTo' },
  { value: 'has_many', labelKey: 'hasMany' },
  { value: 'many_to_many', labelKey: 'manyToMany' },
  { value: 'self_ref_tree', labelKey: 'selfRefTree' },
];

function addRelation() {
  props.relations.push({
    name: '',
    type: 'belongs_to',
    target_model: '',
    target_table: '',
    foreign_key: null,
    pivot_table: null,
    cascade_delete: false,
    label_field: 'name',
    nullable: true,
    comment_zh: '',
    comment_en: '',
  });
  emit('snapshot');
}

function removeRelation(index: number) {
  props.relations.splice(index, 1);
  emit('snapshot');
}

/** target_model → target_table 自动联动 */
function onTargetModelChange(index: number, val: string) {
  const rel = props.relations[index];
  if (!rel) return;
  rel.target_model = val;
  if (val) {
    const snake = val
      .replace(/([A-Z])/g, '_$1')
      .toLowerCase()
      .replace(/^_/, '');
    rel.target_table = snake.endsWith('s') ? snake : `${snake}s`;
  }
}

/** name 变化时，belongs_to 自动推断 foreign_key */
function onNameChange(index: number, val: string) {
  const rel = props.relations[index];
  if (!rel) return;
  rel.name = val;
  if (rel.type === 'belongs_to' && val) {
    rel.foreign_key = `${val}_id`;
  }
}

const columns = [
  {
    title: $t(`${T}.name`),
    dataIndex: 'name',
    width: 130,
  },
  {
    title: $t(`${T}.type`),
    dataIndex: 'type',
    width: 130,
  },
  {
    title: $t(`${T}.targetModel`),
    dataIndex: 'target_model',
    width: 140,
  },
  {
    title: $t(`${T}.targetTable`),
    dataIndex: 'target_table',
    width: 140,
  },
  {
    title: $t(`${T}.foreignKey`),
    dataIndex: 'foreign_key',
    width: 130,
  },
  {
    title: $t(`${T}.labelField`),
    dataIndex: 'label_field',
    width: 100,
  },
  {
    title: $t(`${T}.nullable`),
    dataIndex: 'nullable',
    width: 70,
    align: 'center' as const,
  },
  {
    title: '',
    dataIndex: 'actions',
    width: 50,
    align: 'center' as const,
  },
];
</script>

<template>
  <div>
    <div class="mb-3 flex justify-end">
      <Button size="small" type="dashed" @click="addRelation">
        <template #icon>
          <span class="icon-[lucide--plus] size-3.5" />
        </template>
        {{ $t(`${T}.add`) }}
      </Button>
    </div>

    <Table
      v-if="relations.length > 0"
      :columns="columns"
      :data-source="relations"
      :pagination="false"
      :row-key="(_r: RelationConfig, idx?: number) => idx ?? 0"
      bordered
      size="small"
    >
      <template #bodyCell="{ column, index }">
        <template v-if="column.dataIndex === 'name'">
          <Input
            :placeholder="$t(`${T}.namePlaceholder`)"
            :value="relations[index]!.name"
            size="small"
            @change="(e: Event) => onNameChange(index, (e.target as HTMLInputElement).value)"
          />
        </template>

        <template v-else-if="column.dataIndex === 'type'">
          <Select
            v-model:value="relations[index]!.type"
            :options="relationTypeOptions.map(o => ({
              value: o.value,
              label: $t(`${T}.${o.labelKey}`),
            }))"
            size="small"
            style="width: 100%"
          />
        </template>

        <template v-else-if="column.dataIndex === 'target_model'">
          <Input
            :placeholder="$t(`${T}.targetModelPlaceholder`)"
            :value="relations[index]!.target_model"
            size="small"
            @change="(e: Event) => onTargetModelChange(index, (e.target as HTMLInputElement).value)"
          />
        </template>

        <template v-else-if="column.dataIndex === 'target_table'">
          <Input
            v-model:value="relations[index]!.target_table"
            :placeholder="$t(`${T}.targetTablePlaceholder`)"
            size="small"
          />
        </template>

        <template v-else-if="column.dataIndex === 'foreign_key'">
          <Input
            :value="relations[index]!.foreign_key ?? undefined"
            @update:value="(v: string) => { relations[index]!.foreign_key = v || null; }"
            :placeholder="$t(`${T}.foreignKeyPlaceholder`)"
            size="small"
          />
        </template>

        <template v-else-if="column.dataIndex === 'label_field'">
          <Input
            v-model:value="relations[index]!.label_field"
            :placeholder="$t(`${T}.labelFieldPlaceholder`)"
            size="small"
          />
        </template>

        <template v-else-if="column.dataIndex === 'nullable'">
          <Switch
            v-model:checked="relations[index]!.nullable"
            size="small"
          />
        </template>

        <template v-else-if="column.dataIndex === 'actions'">
          <Button
            danger
            size="small"
            type="text"
            @click="removeRelation(index)"
          >
            <template #icon>
              <span class="icon-[lucide--trash-2] size-3.5" />
            </template>
          </Button>
        </template>
      </template>
    </Table>

    <Empty
      v-else
      :description="$t(`${T}.empty`)"
      class="py-6"
    />
  </div>
</template>
