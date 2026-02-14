<script setup lang="ts">
import {
  Button,
  Empty,
  Input,
  Popconfirm,
  Select,
  Switch,
} from 'ant-design-vue';

import { $t } from '#/locales';

import type { CrudConfig, RelationConfig, RelationType } from '../types';

const props = defineProps<{
  entity: CrudConfig;
  entityModules: string[];
}>();

const emit = defineEmits<{
  touched: [path: string];
}>();

const T = 'admin.dev.crudGenerator.relation';

const relationTypeOptions: Array<{ value: RelationType; label: string }> = [
  { value: 'belongs_to', label: $t(`${T}.belongsTo`) },
  { value: 'has_many', label: $t(`${T}.hasMany`) },
  { value: 'self_ref_tree', label: $t(`${T}.selfRefTree`) },
];

function addRelation() {
  const rel: RelationConfig = {
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
  props.entity.relations.push(rel);
  emit('touched', 'relations');
}

function removeRelation(index: number) {
  props.entity.relations.splice(index, 1);
  emit('touched', 'relations');
}

function onRelationChange() {
  emit('touched', 'relations');
}
</script>

<template>
  <div>
    <div class="mb-3 flex items-center justify-between">
      <span class="text-sm font-medium">
        {{ $t(`${T}.title`) }} ({{ entity.relations.length }})
      </span>
      <Button size="small" type="primary" @click="addRelation">
        <template #icon>
          <span class="icon-[lucide--plus] size-3.5" />
        </template>
        {{ $t(`${T}.add`) }}
      </Button>
    </div>

    <div v-if="entity.relations.length > 0" class="space-y-3">
      <div
        v-for="(rel, idx) in entity.relations"
        :key="idx"
        class="rounded-lg border bg-accent/30 p-3"
      >
        <div class="mb-2 flex items-center justify-between">
          <span class="text-sm font-medium">#{{ idx + 1 }}</span>
          <Popconfirm
            :title="$t('common.confirmDelete')"
            @confirm="removeRelation(idx)"
          >
            <Button danger size="small" type="text">
              <template #icon>
                <span class="icon-[lucide--trash-2] size-3.5" />
              </template>
            </Button>
          </Popconfirm>
        </div>

        <div class="grid grid-cols-3 gap-3">
          <div>
            <label class="mb-1 block text-xs text-muted-foreground">{{ $t(`${T}.name`) }}</label>
            <Input
              v-model:value="rel.name"
              :placeholder="$t(`${T}.namePlaceholder`)"
              size="small"
              @change="onRelationChange"
            />
          </div>
          <div>
            <label class="mb-1 block text-xs text-muted-foreground">{{ $t(`${T}.type`) }}</label>
            <Select
              v-model:value="rel.type"
              :options="relationTypeOptions"
              class="w-full"
              size="small"
              @change="onRelationChange"
            />
          </div>
          <div>
            <label class="mb-1 block text-xs text-muted-foreground">{{ $t(`${T}.targetModel`) }}</label>
            <Input
              v-model:value="rel.target_model"
              :placeholder="$t(`${T}.targetModelPlaceholder`)"
              size="small"
              @change="onRelationChange"
            />
          </div>
          <div>
            <label class="mb-1 block text-xs text-muted-foreground">{{ $t(`${T}.targetTable`) }}</label>
            <Input
              v-model:value="rel.target_table"
              :placeholder="$t(`${T}.targetTablePlaceholder`)"
              size="small"
              @change="onRelationChange"
            />
          </div>
          <div>
            <label class="mb-1 block text-xs text-muted-foreground">{{ $t(`${T}.foreignKey`) }}</label>
            <Input
              :value="rel.foreign_key ?? ''"
              :placeholder="$t(`${T}.foreignKeyPlaceholder`)"
              size="small"
              @update:value="(v: string) => { rel.foreign_key = v || null; onRelationChange(); }"
            />
          </div>
          <div>
            <label class="mb-1 block text-xs text-muted-foreground">{{ $t(`${T}.labelField`) }}</label>
            <Input
              v-model:value="rel.label_field"
              :placeholder="$t(`${T}.labelFieldPlaceholder`)"
              size="small"
              @change="onRelationChange"
            />
          </div>
        </div>

        <div class="mt-2 flex gap-4">
          <label class="flex items-center gap-1.5 text-xs">
            <Switch
              v-model:checked="rel.cascade_delete"
              size="small"
              @change="onRelationChange"
            />
            {{ $t(`${T}.cascadeDelete`) }}
          </label>
          <label class="flex items-center gap-1.5 text-xs">
            <Switch
              v-model:checked="rel.nullable"
              size="small"
              @change="onRelationChange"
            />
            {{ $t(`${T}.nullable`) }}
          </label>
        </div>
      </div>
    </div>

    <Empty
      v-else
      :description="$t(`${T}.empty`)"
      :image="Empty.PRESENTED_IMAGE_SIMPLE"
    />
  </div>
</template>
