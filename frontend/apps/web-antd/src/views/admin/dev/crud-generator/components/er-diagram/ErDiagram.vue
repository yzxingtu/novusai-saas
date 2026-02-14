<script setup lang="ts">
import { computed, ref, watch } from 'vue';

import { VueFlow, useVueFlow } from '@vue-flow/core';
import type { Edge, Node } from '@vue-flow/core';
import { Background } from '@vue-flow/background';
import { Controls } from '@vue-flow/controls';
import {
  Button,
  Drawer,
  Empty,
  Select,
  Switch,
  Tooltip,
} from 'ant-design-vue';

import { $t } from '#/locales';

import type { UseBatchEditorReturn } from '../../composables/use-batch-editor';
import type { EntityRelation, RelationType } from '../../types';

import EntityNode from './EntityNode.vue';

const props = defineProps<{
  editor: UseBatchEditorReturn;
}>();

const emit = defineEmits<{
  'select-entity': [module: string];
}>();

const T = 'admin.dev.crudGenerator.erDiagram';

// ---- Vue Flow ----
const { fitView } = useVueFlow({ id: 'er-diagram' });

// ---- Layout constants ----
const NODE_WIDTH = 200;
const NODE_HEIGHT = 130;
const H_GAP = 80;
const V_GAP = 60;

// ---- Build nodes from editor entities ----
const nodes = computed<Node[]>(() => {
  const entities = props.editor.entities.value;
  const order = props.editor.generationOrder.value;
  const selectedModule = props.editor.selectedModule.value;
  const validationIssues = props.editor.validationIssues.value;

  // Simple grid layout
  const cols = Math.max(Math.ceil(Math.sqrt(entities.length)), 1);

  return entities.map((entity, idx) => {
    const col = idx % cols;
    const row = Math.floor(idx / cols);
    const orderIdx = order.indexOf(entity.module);
    const entityIssues = validationIssues.filter(
      (i) => i.entityModule === entity.module && i.severity === 'error',
    );
    const entityWarnings = validationIssues.filter(
      (i) => i.entityModule === entity.module && i.severity === 'warning',
    );

    return {
      id: entity.module,
      type: 'entity',
      position: {
        x: col * (NODE_WIDTH + H_GAP) + 50,
        y: row * (NODE_HEIGHT + V_GAP) + 50,
      },
      data: {
        module: entity.module,
        label: entity.module,
        fieldCount: entity.fields.length,
        relationCount: entity.relations.length,
        generationOrder: orderIdx >= 0 ? orderIdx + 1 : 0,
        issueCount: entityIssues.length,
        warningCount: entityWarnings.length,
        isSelected: selectedModule === entity.module,
      },
    };
  });
});

// ---- Build edges from cross-relations ----
const edges = computed<Edge[]>(() => {
  const relations = props.editor.crossRelations.value;

  return relations.map((rel, idx) => {
    const labelMap: Record<RelationType, string> = {
      belongs_to: $t(`${T}.belongsTo`),
      has_many: $t(`${T}.hasMany`),
      many_to_many: 'M:N',
      self_ref_tree: $t(`${T}.selfRefTree`),
    };

    return {
      id: `edge-${idx}`,
      source: rel.source_entity,
      target: rel.target_entity,
      label: labelMap[rel.relation_type] ?? rel.relation_type,
      animated: rel.relation_type === 'has_many',
      style: {
        stroke: rel.relation_type === 'belongs_to' ? '#1677ff' : '#52c41a',
        strokeWidth: 2,
      },
      labelStyle: { fontSize: '11px', fontWeight: 500 },
      labelBgStyle: { fill: 'var(--ant-color-bg-container)', fillOpacity: 0.9 },
      data: { relationIndex: idx, relation: rel },
    };
  });
});

// ---- Node click → select entity ----
function onNodeClick(event: { node: Node }) {
  emit('select-entity', event.node.id);
}

// ---- Edge click → edit relation ----
const editingRelation = ref<EntityRelation | null>(null);
const editingRelationIndex = ref(-1);
const showRelationDrawer = ref(false);

function onEdgeClick(event: { edge: Edge }) {
  const data = event.edge.data as { relationIndex: number; relation: EntityRelation } | undefined;
  if (!data) return;
  editingRelationIndex.value = data.relationIndex;
  editingRelation.value = { ...data.relation };
  showRelationDrawer.value = true;
}

function saveRelation() {
  if (!editingRelation.value || editingRelationIndex.value < 0) return;
  const relations = props.editor.crossRelations.value;
  if (editingRelationIndex.value < relations.length) {
    relations[editingRelationIndex.value] = { ...editingRelation.value };
  }
  showRelationDrawer.value = false;
}

// ---- Relation type options ----
const relationTypeOptions = computed(() => [
  { value: 'belongs_to', label: $t(`${T}.belongsTo`) },
  { value: 'has_many', label: $t(`${T}.hasMany`) },
  { value: 'self_ref_tree', label: $t(`${T}.selfRefTree`) },
]);

// ---- Auto layout ----
function autoLayout() {
  const cols = Math.max(Math.ceil(Math.sqrt(nodes.value.length)), 1);
  nodes.value.forEach((node, idx) => {
    const col = idx % cols;
    const row = Math.floor(idx / cols);
    node.position = {
      x: col * (NODE_WIDTH + H_GAP) + 50,
      y: row * (NODE_HEIGHT + V_GAP) + 50,
    };
  });
  setTimeout(() => fitView({ padding: 0.2, duration: 300 }), 50);
}

// ---- Watch for entity changes → fitView ----
watch(
  () => props.editor.entities.value.length,
  () => {
    setTimeout(() => fitView({ padding: 0.2, duration: 300 }), 100);
  },
);
</script>

<template>
  <div class="relative h-[500px] w-full rounded-lg border bg-accent/20">
    <!-- Toolbar -->
    <div class="absolute left-3 top-3 z-10 flex gap-1.5">
      <Tooltip :title="$t(`${T}.autoLayout`)">
        <Button size="small" type="text" @click="autoLayout">
          <template #icon>
            <span class="icon-[lucide--layout-grid] size-3.5" />
          </template>
        </Button>
      </Tooltip>
      <Tooltip :title="$t(`${T}.fitView`)">
        <Button size="small" type="text" @click="fitView({ padding: 0.2, duration: 300 })">
          <template #icon>
            <span class="icon-[lucide--maximize-2] size-3.5" />
          </template>
        </Button>
      </Tooltip>
    </div>

    <!-- Hints -->
    <div class="absolute bottom-3 left-3 z-10 flex gap-3 text-xs text-muted-foreground">
      <span class="flex items-center gap-1">
        <span class="icon-[lucide--mouse-pointer-click] size-3" />
        {{ $t(`${T}.clickNodeHint`) }}
      </span>
      <span class="flex items-center gap-1">
        <span class="icon-[lucide--move] size-3" />
        {{ $t(`${T}.clickEdgeHint`) }}
      </span>
    </div>

    <VueFlow
      v-if="nodes.length > 0"
      id="er-diagram"
      :nodes="nodes"
      :edges="edges"
      :default-viewport="{ x: 0, y: 0, zoom: 0.9 }"
      :max-zoom="2"
      :min-zoom="0.3"
      class="h-full w-full"
      fit-view-on-init
      @node-click="onNodeClick"
      @edge-click="onEdgeClick"
    >
      <template #node-entity="entityNodeProps">
        <EntityNode v-bind="entityNodeProps" />
      </template>

      <Background />
      <Controls :show-fit-view="false" :show-interactive="false" />
    </VueFlow>

    <!-- Empty state -->
    <div v-else class="flex h-full items-center justify-center">
      <Empty :description="$t(`${T}.noEntities`)" />
    </div>

    <!-- ============ Relation Edit Drawer ============ -->
    <Drawer
      v-model:open="showRelationDrawer"
      :title="$t(`${T}.editRelation`)"
      :width="360"
      placement="right"
    >
      <div v-if="editingRelation" class="space-y-4">
        <div>
          <label class="mb-1 block text-sm text-muted-foreground">{{ $t(`${T}.sourceEntity`) }}</label>
          <div class="rounded-md bg-accent/50 px-3 py-1.5 font-mono text-sm">
            {{ editingRelation.source_entity }}
          </div>
        </div>
        <div>
          <label class="mb-1 block text-sm text-muted-foreground">{{ $t(`${T}.targetEntity`) }}</label>
          <div class="rounded-md bg-accent/50 px-3 py-1.5 font-mono text-sm">
            {{ editingRelation.target_entity }}
          </div>
        </div>
        <div>
          <label class="mb-1 block text-sm text-muted-foreground">{{ $t(`${T}.relationType`) }}</label>
          <Select
            v-model:value="editingRelation.relation_type"
            :options="relationTypeOptions"
            class="w-full"
          />
        </div>
        <div>
          <label class="mb-1 block text-sm text-muted-foreground">{{ $t(`${T}.foreignKey`) }}</label>
          <a-input
            :value="editingRelation.foreign_key ?? ''"
            @update:value="(v: string) => { if (editingRelation) editingRelation.foreign_key = v || null; }"
          />
        </div>
        <div class="flex items-center justify-between">
          <label class="text-sm text-muted-foreground">{{ $t(`${T}.nullable`) }}</label>
          <Switch v-model:checked="editingRelation.nullable" />
        </div>
      </div>

      <template #footer>
        <div class="flex justify-end gap-2">
          <Button @click="showRelationDrawer = false">
            {{ $t('common.cancel') }}
          </Button>
          <Button type="primary" @click="saveRelation">
            {{ $t('common.save') }}
          </Button>
        </div>
      </template>
    </Drawer>
  </div>
</template>

<style>
@import '@vue-flow/core/dist/style.css';
@import '@vue-flow/core/dist/theme-default.css';
@import '@vue-flow/controls/dist/style.css';
</style>
