<script setup lang="ts">
import { watch } from 'vue';

import type { RadioChangeEvent } from 'ant-design-vue/es/radio/interface';

import {
  AutoComplete,
  Card,
  Checkbox,
  Col,
  Divider,
  Form,
  Input,
  Radio,
  Row,
  Tooltip,
} from 'ant-design-vue';

import { $t } from '#/locales';

import type { CrudConfig, LayoutVariant, ScopeType } from '../types';

import LayoutSelector from './LayoutSelector.vue';
import RelationEditor from './RelationEditor.vue';

const props = defineProps<{
  config: CrudConfig;
}>();

const emit = defineEmits<{
  (e: 'update:config', config: CrudConfig): void;
  (e: 'snapshot'): void;
}>();

const T = 'admin.dev.crudGenerator';

/** module → table_name 自动联动 */
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

/** Common parent menu options for AutoComplete */
const parentMenuOptions = [
  'system', 'content', 'finance', 'order', 'product',
  'user', 'marketing', 'report', 'settings', 'ai',
].map((v) => ({ value: v }));

function onScopeChange(val: ScopeType) {
  updateField('scope', val);
  emit('snapshot');
}

function onLayoutChange(val: LayoutVariant) {
  emit('update:config', {
    ...props.config,
    layout: { ...props.config.layout, variant: val },
  });
  emit('snapshot');
}
</script>

<template>
  <div class="step-basic-info">
    <!-- 基本信息 -->
    <Card :bordered="false" class="mb-4">
      <template #title>
        <span class="flex items-center gap-2">
          <span class="icon-[lucide--file-text] size-4" />
          {{ $t(`${T}.steps.basicInfo`) }}
        </span>
      </template>

      <Form layout="vertical">
        <Row :gutter="16">
          <!-- module -->
          <Col :span="8">
            <Form.Item
              :label="$t(`${T}.basicInfo.module`)"
              required
            >
              <Input
                :value="config.module"
                :placeholder="$t(`${T}.basicInfo.modulePlaceholder`)"
                @update:value="(v: string) => updateField('module', v)"
              />
              <div class="text-muted-foreground mt-1 text-xs">
                {{ $t(`${T}.basicInfo.moduleHelp`) }}
              </div>
            </Form.Item>
          </Col>

          <!-- table_name -->
          <Col :span="8">
            <Form.Item
              :label="$t(`${T}.basicInfo.tableName`)"
              required
            >
              <Input
                :value="config.table_name"
                :placeholder="$t(`${T}.basicInfo.tableNamePlaceholder`)"
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

        <Row :gutter="16">
          <!-- display_name -->
          <Col :span="8">
            <Form.Item
              :label="$t(`${T}.basicInfo.displayName`)"
              required
            >
              <Input
                :value="config.display_name"
                :placeholder="$t(`${T}.basicInfo.displayNamePlaceholder`)"
                @update:value="(v: string) => updateField('display_name', v)"
              />
            </Form.Item>
          </Col>

          <!-- display_name_en -->
          <Col :span="8">
            <Form.Item
              :label="$t(`${T}.basicInfo.displayNameEn`)"
              required
            >
              <Input
                :value="config.display_name_en"
                :placeholder="$t(`${T}.basicInfo.displayNameEnPlaceholder`)"
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
                @change="(v: unknown) => updateField('parent_menu', String(v ?? ''))"
              />
            </Form.Item>
          </Col>
        </Row>

        <Row :gutter="16">
          <!-- description -->
          <Col :span="24">
            <Form.Item :label="$t(`${T}.basicInfo.description`)">
              <Input.TextArea
                :value="config.description"
                :placeholder="$t(`${T}.basicInfo.descriptionPlaceholder`)"
                :rows="2"
                @update:value="(v: string) => updateField('description', v)"
              />
            </Form.Item>
          </Col>
        </Row>

        <!-- 选项开关 -->
        <Divider orientation="left" plain>
          {{ $t(`${T}.basicInfo.options`) }}
        </Divider>

        <div class="flex flex-wrap gap-6">
          <Tooltip :title="$t(`${T}.basicInfo.softDelete`)">
            <Checkbox :checked="config.soft_delete" @update:checked="(v: boolean) => updateField('soft_delete', v)">
              <span class="flex items-center gap-1">
                <span class="icon-[lucide--trash-2] size-3.5" />
                {{ $t(`${T}.basicInfo.softDelete`) }}
              </span>
            </Checkbox>
          </Tooltip>

          <Tooltip :title="$t(`${T}.basicInfo.dragSort`)">
            <Checkbox :checked="config.drag_sort" @update:checked="(v: boolean) => updateField('drag_sort', v)">
              <span class="flex items-center gap-1">
                <span class="icon-[lucide--grip-vertical] size-3.5" />
                {{ $t(`${T}.basicInfo.dragSort`) }}
              </span>
            </Checkbox>
          </Tooltip>

          <Tooltip :title="$t(`${T}.basicInfo.statusToggle`)">
            <Checkbox :checked="config.has_status_toggle" @update:checked="(v: boolean) => updateField('has_status_toggle', v)">
              <span class="flex items-center gap-1">
                <span class="icon-[lucide--toggle-left] size-3.5" />
                {{ $t(`${T}.basicInfo.statusToggle`) }}
              </span>
            </Checkbox>
          </Tooltip>

          <Tooltip :title="$t(`${T}.basicInfo.recyclable`)">
            <Checkbox :checked="config.recyclable" @update:checked="(v: boolean) => updateField('recyclable', v)">
              <span class="flex items-center gap-1">
                <span class="icon-[lucide--archive-restore] size-3.5" />
                {{ $t(`${T}.basicInfo.recyclable`) }}
              </span>
            </Checkbox>
          </Tooltip>
        </div>
      </Form>
    </Card>

    <!-- 布局选择 -->
    <Card :bordered="false" class="mb-4">
      <template #title>
        <span class="flex items-center gap-2">
          <span class="icon-[lucide--layout-grid] size-4" />
          {{ $t(`${T}.layout.title`) }}
        </span>
      </template>

      <LayoutSelector
        :value="config.layout.variant"
        @change="onLayoutChange"
      />
    </Card>

    <!-- 关联关系 -->
    <Card :bordered="false">
      <template #title>
        <span class="flex items-center gap-2">
          <span class="icon-[lucide--link] size-4" />
          {{ $t(`${T}.relation.title`) }}
        </span>
      </template>

      <RelationEditor
        :relations="config.relations"
        @update:relations="(rels) => emit('update:config', { ...config, relations: rels })"
        @snapshot="emit('snapshot')"
      />
    </Card>
  </div>
</template>
