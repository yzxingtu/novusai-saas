<script lang="ts" setup>
/**
 * 关联关系编辑器 / Relations editor
 *
 * 可增删的关联配置，每条：type + target + foreign_key + name
 */
import { computed, onMounted, ref } from 'vue';

import { Button, Input, Select } from 'ant-design-vue';

import { getCodegenParentResourcesApi } from '#/api/admin/codegen';
import { $t } from '#/locales';
import { useCodegenBuilderStore } from '#/store';

import { singularize } from './infer';

defineOptions({ name: 'RelationsEditor' });

const store = useCodegenBuilderStore();
const parentResources = ref<string[]>([]);
const resource = computed(() => (store.configJson.resource as string) || '');

type RelationType = 'many_to_many' | 'many_to_one' | 'one_to_many';

interface RelationItem {
  foreign_key: string;
  name: string;
  target: string;
  type: RelationType;
}

const RELATION_TYPES = new Set<RelationType>([
  'many_to_many',
  'many_to_one',
  'one_to_many',
]);

function normalizeRelation(item?: Partial<RelationItem>): RelationItem {
  const type = item?.type;
  return {
    foreign_key: item?.foreign_key ?? '',
    name: item?.name ?? '',
    target: item?.target ?? '',
    type: RELATION_TYPES.has(type as RelationType)
      ? (type as RelationType)
      : 'many_to_one',
  };
}

const relations = computed<RelationItem[]>(() => {
  const rels = store.configJson.relations;
  return Array.isArray(rels)
    ? (rels as Partial<RelationItem>[]).map((item) => normalizeRelation(item))
    : [];
});

function toPascalFromSnake(s: string): string {
  if (!s) return '';
  return s
    .replaceAll('-', '_')
    .replaceAll(/(?:^|_)([a-z])/g, (_, c) => c.toUpperCase());
}

const targetOptions = computed(() => {
  const opts = parentResources.value.map((r) => ({
    label: toPascalFromSnake(r),
    value: toPascalFromSnake(r),
  }));
  const res = resource.value;
  if (res) {
    const pascal = toPascalFromSnake(res);
    if (pascal && !opts.some((o) => o.value === pascal)) {
      opts.push({ label: pascal, value: pascal });
    }
  }
  return opts;
});

onMounted(async () => {
  try {
    const arr = await getCodegenParentResourcesApi();
    parentResources.value = Array.isArray(arr) ? arr : [];
  } catch {
    parentResources.value = [];
  }
});

const typeOptions = computed(() => [
  {
    label: $t('admin.system.codegen.expert.relationTypeManyToOne'),
    value: 'many_to_one',
  },
  {
    label: $t('admin.system.codegen.expert.relationTypeOneToMany'),
    value: 'one_to_many',
  },
  {
    label: $t('admin.system.codegen.expert.relationTypeManyToMany'),
    value: 'many_to_many',
  },
]);

function inferFkForManyToOne(target: string): string {
  const table = target
    .replaceAll(/([A-Z])/g, '_$1')
    .toLowerCase()
    .replace(/^_/, '');
  const singular = singularize(table);
  return `${singular}_id`;
}

function inferFkForOneToMany(): string {
  return `${resource.value}_id`;
}

function addRelation() {
  const rels = [
    ...relations.value,
    {
      type: 'many_to_one',
      target: '',
      foreign_key: '',
      name: '',
    },
  ];
  store.updateConfig({ relations: rels });
}

function removeRelation(idx: number) {
  const rels = [...relations.value];
  rels.splice(idx, 1);
  store.updateConfig({ relations: rels });
}

function updateRelation(idx: number, patch: Partial<RelationItem>) {
  const rels = [...relations.value];
  const current = rels[idx];
  if (!current) return;
  rels[idx] = normalizeRelation({ ...current, ...patch });
  if (patch.target && !rels[idx].foreign_key) {
    const target = patch.target;
    if (rels[idx].type === 'many_to_one') {
      rels[idx].foreign_key = inferFkForManyToOne(target);
    } else if (rels[idx].type === 'one_to_many') {
      rels[idx].foreign_key = inferFkForOneToMany();
    }
  }
  store.updateConfig({ relations: rels });
}

function onRelationTypeChange(idx: number, value: unknown) {
  if (typeof value === 'string' && RELATION_TYPES.has(value as RelationType)) {
    updateRelation(idx, { type: value as RelationType });
  }
}

function onRelationTargetChange(idx: number, value: unknown) {
  if (typeof value === 'string') {
    updateRelation(idx, { target: value });
    return;
  }
  updateRelation(idx, { target: '' });
}
</script>

<template>
  <div class="flex flex-col gap-2">
    <div
      v-for="(r, idx) in relations"
      :key="`rel-${idx}-${r.target || ''}-${r.foreign_key || ''}`"
      class="flex flex-wrap items-center gap-2 rounded border border-border p-2"
    >
      <Select
        :value="r.type"
        :options="typeOptions"
        class="w-36"
        @change="(value) => onRelationTypeChange(idx, value)"
      />
      <Select
        :value="r.target"
        :options="targetOptions"
        allow-clear
        :placeholder="$t('admin.system.codegen.expert.relationTarget')"
        class="w-36"
        @change="(value) => onRelationTargetChange(idx, value)"
      />
      <Input
        :value="r.foreign_key"
        :placeholder="$t('admin.system.codegen.expert.relationForeignKey')"
        class="!w-32"
        @update:value="(v: string) => updateRelation(idx, { foreign_key: v })"
      />
      <Input
        :value="r.name"
        :placeholder="$t('admin.system.codegen.expert.relationNameOptional')"
        class="!w-28"
        @update:value="(v: string) => updateRelation(idx, { name: v })"
      />
      <Button type="text" danger size="small" @click="removeRelation(idx)">
        {{ $t('common.delete') }}
      </Button>
    </div>
    <Button type="dashed" @click="addRelation">
      {{ $t('admin.system.codegen.expert.addRelation') }}
    </Button>
  </div>
</template>
