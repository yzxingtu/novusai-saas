<script setup lang="ts">
import { computed, onMounted, watch } from 'vue';

import type { RadioChangeEvent } from 'ant-design-vue/es/radio/interface';

import {
  AutoComplete,
  Checkbox,
  Col,
  Form,
  Input,
  Radio,
  Row,
  Tooltip,
} from 'ant-design-vue';

import { $t } from '#/locales';

import type { CrudConfig, ScopeType } from '../types';
import { useProjectGraph } from '../composables/use-project-graph';

const props = defineProps<{
  config: CrudConfig;
}>();

const emit = defineEmits<{
  'update:config': [config: CrudConfig];
  snapshot: [];
}>();

const T = 'admin.dev.crudGenerator';

/** module → table_name auto-derive */
function toTableName(module: string): string {
  const cleaned = module
    .replace(/[^a-z0-9-]/gi, '')
    .toLowerCase()
    .replace(/-/g, '_');
  if (!cleaned) return '';
  if (cleaned.endsWith('s')) return cleaned;
  if (cleaned.endsWith('y')) return `${cleaned.slice(0, -1)}ies`;
  return `${cleaned}s`;
}

function updateField<K extends keyof CrudConfig>(key: K, value: CrudConfig[K]) {
  emit('update:config', { ...props.config, [key]: value });
}

watch(
  () => props.config.module,
  (val) => {
    if (val) {
      updateField('table_name', toTableName(val));
    }
  },
);

/** Dynamic parent menu options */
const DEFAULT_MENUS = ['system', 'content', 'finance', 'order', 'product', 'user', 'marketing', 'report', 'settings', 'ai'];

const { loadGraph, models } = useProjectGraph();
onMounted(() => loadGraph());

const parentMenuOptions = computed(() => {
  const fromGraph = new Set<string>();
  for (const model of Object.values(models.value)) {
    const parts = model.table_name.split('_');
    if (parts.length > 1) {
      fromGraph.add(parts[0]!);
    }
  }
  const merged = new Set([...DEFAULT_MENUS, ...fromGraph]);
  return [...merged].sort().map((v) => ({ value: v }));
});

function onScopeChange(val: ScopeType) {
  updateField('scope', val);
  emit('snapshot');
}
</script>

<template>
  <Form layout="vertical" class="basic-info-section">
    <Row :gutter="12">
      <!-- module -->
      <Col :span="8">
        <Form.Item :label="$t(`${T}.basicInfo.module`)" required>
          <Input
            :value="config.module"
            :placeholder="$t(`${T}.basicInfo.modulePlaceholder`)"
            size="small"
            @update:value="(v: string) => updateField('module', v)"
          />
        </Form.Item>
      </Col>

      <!-- table_name -->
      <Col :span="8">
        <Form.Item :label="$t(`${T}.basicInfo.tableName`)" required>
          <Input
            :value="config.table_name"
            :placeholder="$t(`${T}.basicInfo.tableNamePlaceholder`)"
            size="small"
            @update:value="(v: string) => updateField('table_name', v)"
          />
        </Form.Item>
      </Col>

      <!-- scope -->
      <Col :span="8">
        <Form.Item :label="$t(`${T}.basicInfo.scope`)">
          <Radio.Group
            :value="config.scope"
            button-style="solid"
            size="small"
            @change="(e: RadioChangeEvent) => onScopeChange(e.target.value as ScopeType)"
          >
            <Tooltip :title="$t(`${T}.basicInfo.scopeTenantDesc`)">
              <Radio.Button value="tenant">
                {{ $t(`${T}.basicInfo.scopeTenant`) }}
              </Radio.Button>
            </Tooltip>
            <Tooltip :title="$t(`${T}.basicInfo.scopeAdminDesc`)">
              <Radio.Button value="admin">
                {{ $t(`${T}.basicInfo.scopeAdmin`) }}
              </Radio.Button>
            </Tooltip>
            <Tooltip :title="$t(`${T}.basicInfo.scopeBothDesc`)">
              <Radio.Button value="both">
                {{ $t(`${T}.basicInfo.scopeBoth`) }}
              </Radio.Button>
            </Tooltip>
          </Radio.Group>
        </Form.Item>
      </Col>
    </Row>

    <Row :gutter="12">
      <!-- display_name -->
      <Col :span="8">
        <Form.Item :label="$t(`${T}.basicInfo.displayName`)" required>
          <Input
            :value="config.display_name"
            :placeholder="$t(`${T}.basicInfo.displayNamePlaceholder`)"
            size="small"
            @update:value="(v: string) => updateField('display_name', v)"
          />
        </Form.Item>
      </Col>

      <!-- display_name_en -->
      <Col :span="8">
        <Form.Item :label="$t(`${T}.basicInfo.displayNameEn`)" required>
          <Input
            :value="config.display_name_en"
            :placeholder="$t(`${T}.basicInfo.displayNameEnPlaceholder`)"
            size="small"
            @update:value="(v: string) => updateField('display_name_en', v)"
          />
        </Form.Item>
      </Col>

      <!-- parent_menu -->
      <Col :span="8">
        <Form.Item :label="$t(`${T}.basicInfo.parentMenu`)">
          <AutoComplete
            :value="config.parent_menu"
            :options="parentMenuOptions"
            :placeholder="$t(`${T}.basicInfo.parentMenuPlaceholder`)"
            size="small"
            @change="(v: unknown) => updateField('parent_menu', String(v ?? ''))"
          />
        </Form.Item>
      </Col>
    </Row>

    <!-- Options row -->
    <div class="flex flex-wrap gap-4">
      <Checkbox :checked="config.soft_delete" @update:checked="(v: boolean) => updateField('soft_delete', v)">
        <span class="flex items-center gap-1 text-xs">
          <span class="icon-[lucide--trash-2] size-3" />
          {{ $t(`${T}.basicInfo.softDelete`) }}
        </span>
      </Checkbox>

      <Checkbox :checked="config.drag_sort" @update:checked="(v: boolean) => updateField('drag_sort', v)">
        <span class="flex items-center gap-1 text-xs">
          <span class="icon-[lucide--grip-vertical] size-3" />
          {{ $t(`${T}.basicInfo.dragSort`) }}
        </span>
      </Checkbox>

      <Checkbox :checked="config.has_status_toggle" @update:checked="(v: boolean) => updateField('has_status_toggle', v)">
        <span class="flex items-center gap-1 text-xs">
          <span class="icon-[lucide--toggle-left] size-3" />
          {{ $t(`${T}.basicInfo.statusToggle`) }}
        </span>
      </Checkbox>

      <Checkbox :checked="config.recyclable" @update:checked="(v: boolean) => updateField('recyclable', v)">
        <span class="flex items-center gap-1 text-xs">
          <span class="icon-[lucide--archive-restore] size-3" />
          {{ $t(`${T}.basicInfo.recyclable`) }}
        </span>
      </Checkbox>
    </div>
  </Form>
</template>

<style scoped>
.basic-info-section :deep(.ant-form-item) {
  margin-bottom: 12px;
}
</style>
