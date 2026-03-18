<script lang="ts" setup>
/**
 * 关联关系编辑器 / Relations editor
 *
 * 可增删的关联配置，每条：type + target + foreign_key + name
 */
import { computed, onMounted, ref } from 'vue';

import { Button, Form, Input, Select } from 'ant-design-vue';

import { getCodegenParentResourcesApi } from '#/api/admin/codegen';
import { $t } from '#/locales';
import { useCodegenBuilderStore } from '#/store';

defineOptions({ name: 'RelationsEditor' });

const store = useCodegenBuilderStore();
const parentResources = ref<string[]>([]);

const fields = computed(
  () => (store.configJson.fields as Array<Record<string, unknown>>) || [],
);
const resource = computed(() => (store.configJson.resource as string) || '');
const resourcePlural = computed(
  () => (store.configJson.resource_plural as string) || '',
);

const fieldOptions = computed(() =>
  fields.value
    .filter((f) => f.type !== '__divider__' && !f.divider && (f.name as string))
    .map((f) => ({ label: f.name as string, value: f.name as string })),
);

const relations = computed(() => {
  const rels = (store.configJson.relations as Array<Record<string, unknown>>) || [];
  return Array.isArray(rels) ? [...rels] : [];
});

function toPascalFromSnake(s: string): string {
  if (!s) return '';
  return s
    .replace(/-/g, '_')
    .replace(/(?:^|_)([a-z])/g, (_, c) => c.toUpperCase());
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
  { label: $t('admin.system.codegen.expert.relationTypeManyToOne'), value: 'many_to_one' },
  { label: $t('admin.system.codegen.expert.relationTypeOneToMany'), value: 'one_to_many' },
  { label: $t('admin.system.codegen.expert.relationTypeManyToMany'), value: 'many_to_many' },
]);

function inferFkForManyToOne(target: string): string {
  const table = target.replace(/([A-Z])/g, '_$1').toLowerCase().replace(/^_/, '');
  const singular = table.endsWith('s') ? table.slice(0, -1) : table;
  return `${singular}_id`;
}

function inferFkForOneToMany(): string {
  return `${resource.value}_id`;
}

function addRelation() {
  const rels = [...relations.value];
  rels.push({
    type: 'many_to_one',
    target: '',
    foreign_key: '',
    name: '',
  });
  store.updateConfig({ relations: rels });
}

function removeRelation(idx: number) {
  const rels = [...relations.value];
  rels.splice(idx, 1);
  store.updateConfig({ relations: rels });
}

function updateRelation(idx: number, patch: Record<string, unknown>) {
  const rels = [...relations.value];
  rels[idx] = { ...rels[idx], ...patch };
  if (patch.target && !rels[idx].foreign_key) {
    const t = patch.target as string;
    if (rels[idx].type === 'many_to_one') {
      rels[idx].foreign_key = inferFkForManyToOne(t);
    } else if (rels[idx].type === 'one_to_many') {
      rels[idx].foreign_key = inferFkForOneToMany();
    }
  }
  store.updateConfig({ relations: rels });
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
        @change="(v: string) => updateRelation(idx, { type: v })"
      />
      <Select
        :value="r.target"
        :options="targetOptions"
        allow-clear
        :placeholder="$t('admin.system.codegen.expert.relationTarget')"
        class="w-36"
        @change="(v: string) => updateRelation(idx, { target: v })"
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
