<script setup lang="ts">
import { computed } from 'vue';

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
  (e: 'update:relations', relations: RelationConfig[]): void;
  (e: 'snapshot'): void;
}>();

const T = 'admin.dev.crudGenerator.relation';

const RELATION_TYPE_KEYS = [
  { value: 'belongs_to', labelKey: 'belongsTo' },
  { value: 'has_many', labelKey: 'hasMany' },
  { value: 'many_to_many', labelKey: 'manyToMany' },
  { value: 'self_ref_tree', labelKey: 'selfRefTree' },
] as const;

function getRelationTypeOptions() {
  return RELATION_TYPE_KEYS.map((o) => ({
    value: o.value,
    label: $t(`${T}.${o.labelKey}`),
  }));
}

function updateRelations(newList: RelationConfig[]) {
  emit('update:relations', newList);
  emit('snapshot');
}

function updateAt(index: number, patch: Partial<RelationConfig>) {
  const list = props.relations.map((r, i) =>
    i === index ? { ...r, ...patch } : r,
  );
  emit('update:relations', list);
}

function addRelation() {
  const newRel: RelationConfig = {
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
  };
  updateRelations([...props.relations, newRel]);
}

function removeRelation(index: number) {
  updateRelations(props.relations.filter((_, i) => i !== index));
}

/** target_model → target_table 自动联动 */
function onTargetModelChange(index: number, val: string) {
  const patch: Partial<RelationConfig> = { target_model: val };
  if (val) {
    const snake = val
      .replace(/([A-Z])/g, '_$1')
      .toLowerCase()
      .replace(/^_/, '');
    patch.target_table = snake.endsWith('s') ? snake : `${snake}s`;
  }
  updateAt(index, patch);
  emit('snapshot');
}

/** name 变化时，belongs_to 自动推断 foreign_key */
function onNameChange(index: number, val: string) {
  const rel = props.relations[index];
  if (!rel) return;
  const patch: Partial<RelationConfig> = { name: val };
  if (rel.type === 'belongs_to' && val) {
    patch.foreign_key = `${val}_id`;
  }
  updateAt(index, patch);
  emit('snapshot');
}

const columns = computed(() => [
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
]);
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
            :options="getRelationTypeOptions()"
            :value="relations[index]!.type"
            size="small"
            style="width: 100%"
            @change="(v: unknown) => updateAt(index, { type: v as RelationConfig['type'] })"
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
            :placeholder="$t(`${T}.targetTablePlaceholder`)"
            :value="relations[index]!.target_table"
            size="small"
            @change="(e: Event) => updateAt(index, { target_table: (e.target as HTMLInputElement).value })"
          />
        </template>

        <template v-else-if="column.dataIndex === 'foreign_key'">
          <Input
            :placeholder="$t(`${T}.foreignKeyPlaceholder`)"
            :value="relations[index]!.foreign_key ?? ''"
            size="small"
            @change="(e: Event) => updateAt(index, { foreign_key: (e.target as HTMLInputElement).value || null })"
          />
        </template>

        <template v-else-if="column.dataIndex === 'label_field'">
          <Input
            :placeholder="$t(`${T}.labelFieldPlaceholder`)"
            :value="relations[index]!.label_field"
            size="small"
            @change="(e: Event) => updateAt(index, { label_field: (e.target as HTMLInputElement).value })"
          />
        </template>

        <template v-else-if="column.dataIndex === 'nullable'">
          <Switch
            :checked="relations[index]!.nullable"
            size="small"
            @change="(v: unknown) => updateAt(index, { nullable: !!v })"
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
