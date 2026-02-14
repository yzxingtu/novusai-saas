<script setup lang="ts">
/**
 * CRUD Wizard — Entity List Panel
 *
 * Left sidebar for batch CRUD generation.
 * Shows BatchCrudProject.entities list with select/add/remove/reorder.
 * Emits events for parent to coordinate with right-side editor.
 *
 * Single-entity mode: panel is hidden (controlled by parent).
 */
import { computed } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  Badge,
  Button,
  Divider,
  Empty,
  Popconfirm,
  Space,
  Tag,
  Tooltip,
  Typography,
} from 'ant-design-vue';

import type { EntityConfig, EntityListItem } from './types';

const props = withDefaults(
  defineProps<{
    /** All entities in the batch project */
    entities: EntityConfig[];
    /** Currently selected entity index (-1 = none) */
    selectedIndex: number;
    /** Project name */
    projectName?: string;
    /** Whether batch operations are in progress */
    loading?: boolean;
    /** i18n function */
    t: (key: string, ...args: unknown[]) => string;
  }>(),
  {
    projectName: '',
    loading: false,
  },
);

const emit = defineEmits<{
  /** Select an entity by index */
  (e: 'select', index: number): void;
  /** Add a new empty entity */
  (e: 'add'): void;
  /** Remove entity by index */
  (e: 'remove', index: number): void;
  /** Batch preview all entities */
  (e: 'batchPreview'): void;
  /** Batch generate all entities */
  (e: 'batchGenerate'): void;
  /** Move entity up/down in order */
  (e: 'reorder', fromIndex: number, toIndex: number): void;
}>();

/** Transform entities into display items */
const entityItems = computed<EntityListItem[]>(() => {
  return props.entities.map((entity, index) => ({
    index,
    module: entity.module,
    display_name: entity.display_name,
    display_name_en: entity.display_name_en,
    field_count: entity.fields?.length ?? 0,
    scope: entity.scope,
    hasError: !entity.module || !entity.table_name || !entity.fields?.length,
  }));
});

const entityCount = computed(() => props.entities.length);

function onSelect(index: number) {
  emit('select', index);
}

function onRemove(index: number) {
  emit('remove', index);
}

function onMoveUp(index: number) {
  if (index > 0) {
    emit('reorder', index, index - 1);
  }
}

function onMoveDown(index: number) {
  if (index < entityCount.value - 1) {
    emit('reorder', index, index + 1);
  }
}

/** Scope tag color mapping */
function getScopeColor(scope: string): string {
  switch (scope) {
    case 'admin': {
      return 'purple';
    }
    case 'both': {
      return 'blue';
    }
    case 'tenant': {
      return 'green';
    }
    default: {
      return 'default';
    }
  }
}
</script>

<template>
  <div class="entity-list-panel">
    <!-- Header -->
    <div class="panel-header">
      <div class="header-title">
        <IconifyIcon icon="lucide:layers" class="mr-1 text-primary" />
        <Typography.Text strong>
          {{ t('crudWizard.entityList') }}
        </Typography.Text>
        <Badge
          :count="entityCount"
          :number-style="{ backgroundColor: 'var(--primary)' }"
          class="ml-2"
        />
      </div>
      <Tooltip :title="t('crudWizard.addEntity')">
        <Button
          type="text"
          size="small"
          :disabled="loading"
          @click="emit('add')"
        >
          <template #icon>
            <IconifyIcon icon="lucide:plus" />
          </template>
        </Button>
      </Tooltip>
    </div>

    <!-- Project name -->
    <div v-if="projectName" class="project-name">
      <Typography.Text type="secondary" :ellipsis="{ tooltip: projectName }">
        {{ projectName }}
      </Typography.Text>
    </div>

    <Divider class="my-2" />

    <!-- Entity list -->
    <div class="entity-list">
      <Empty
        v-if="entityItems.length === 0"
        :description="t('crudWizard.noEntities')"
        :image="Empty.PRESENTED_IMAGE_SIMPLE"
      />

      <div
        v-for="item in entityItems"
        :key="item.module + '-' + item.index"
        class="entity-item"
        :class="{
          'entity-item--selected': item.index === selectedIndex,
          'entity-item--error': item.hasError,
        }"
        @click="onSelect(item.index)"
      >
        <div class="entity-item__main">
          <div class="entity-item__name">
            <IconifyIcon
              :icon="item.hasError ? 'lucide:alert-circle' : 'lucide:table-2'"
              :class="item.hasError ? 'text-destructive' : 'text-muted-foreground'"
              class="mr-1"
            />
            <span class="entity-item__label">{{ item.display_name }}</span>
          </div>
          <div class="entity-item__meta">
            <Tag :color="getScopeColor(item.scope)" size="small" class="mr-1">
              {{ item.scope }}
            </Tag>
            <Typography.Text type="secondary" class="text-xs">
              {{ item.field_count }} {{ t('crudWizard.fields') }}
            </Typography.Text>
          </div>
          <Typography.Text type="secondary" class="entity-item__module text-xs">
            {{ item.module }}
          </Typography.Text>
        </div>

        <!-- Actions (visible on hover / selected) -->
        <div class="entity-item__actions" @click.stop>
          <Space :size="2">
            <Tooltip :title="t('crudWizard.moveUp')">
              <Button
                type="text"
                size="small"
                :disabled="item.index === 0"
                @click="onMoveUp(item.index)"
              >
                <template #icon>
                  <IconifyIcon icon="lucide:chevron-up" class="text-xs" />
                </template>
              </Button>
            </Tooltip>
            <Tooltip :title="t('crudWizard.moveDown')">
              <Button
                type="text"
                size="small"
                :disabled="item.index === entityCount - 1"
                @click="onMoveDown(item.index)"
              >
                <template #icon>
                  <IconifyIcon icon="lucide:chevron-down" class="text-xs" />
                </template>
              </Button>
            </Tooltip>
            <Popconfirm
              :title="t('crudWizard.confirmRemove')"
              :ok-text="t('crudWizard.remove')"
              :cancel-text="t('crudWizard.cancel')"
              placement="right"
              @confirm="onRemove(item.index)"
            >
              <Tooltip :title="t('crudWizard.removeEntity')">
                <Button type="text" size="small" danger>
                  <template #icon>
                    <IconifyIcon icon="lucide:trash-2" class="text-xs" />
                  </template>
                </Button>
              </Tooltip>
            </Popconfirm>
          </Space>
        </div>
      </div>
    </div>

    <Divider class="my-2" />

    <!-- Batch actions -->
    <div class="batch-actions">
      <Button
        block
        :loading="loading"
        :disabled="entityCount === 0"
        class="mb-2"
        @click="emit('batchPreview')"
      >
        <template #icon>
          <IconifyIcon icon="lucide:eye" />
        </template>
        {{ t('crudWizard.batchPreview') }}
      </Button>
      <Button
        block
        type="primary"
        :loading="loading"
        :disabled="entityCount === 0"
        @click="emit('batchGenerate')"
      >
        <template #icon>
          <IconifyIcon icon="lucide:file-code" />
        </template>
        {{ t('crudWizard.batchGenerate') }}
      </Button>
    </div>
  </div>
</template>

<style scoped>
.entity-list-panel {
  display: flex;
  flex-direction: column;
  width: 280px;
  height: 100%;
  padding: 12px;
  border-right: 1px solid var(--border);
  background: var(--component-background);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-title {
  display: flex;
  align-items: center;
}

.project-name {
  margin-top: 4px;
  padding-left: 4px;
}

.entity-list {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}

.entity-item {
  position: relative;
  padding: 8px 10px;
  margin-bottom: 4px;
  border: 1px solid transparent;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.entity-item:hover {
  background: var(--accent);
  border-color: var(--border);
}

.entity-item--selected {
  background: hsl(var(--primary) / 8%);
  border-color: hsl(var(--primary) / 30%);
}

.entity-item--error {
  border-color: hsl(var(--destructive) / 30%);
}

.entity-item__main {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.entity-item__name {
  display: flex;
  align-items: center;
  font-weight: 500;
}

.entity-item__label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.entity-item__meta {
  display: flex;
  align-items: center;
  margin-left: 20px;
}

.entity-item__module {
  margin-left: 20px;
  font-family: monospace;
}

.entity-item__actions {
  position: absolute;
  top: 4px;
  right: 4px;
  opacity: 0;
  transition: opacity 0.15s ease;
}

.entity-item:hover .entity-item__actions,
.entity-item--selected .entity-item__actions {
  opacity: 1;
}

.batch-actions {
  padding-top: 4px;
}
</style>
