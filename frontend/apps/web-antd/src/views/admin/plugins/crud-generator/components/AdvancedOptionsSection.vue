<script setup lang="ts">
import {
  Checkbox,
  Col,
  Divider,
  Form,
  Input,
  InputNumber,
  Radio,
  Row,
  Select,
} from 'ant-design-vue';

import { $t } from '#/locales';

import type { CrudConfig, FormType, LayoutVariant } from '../types';

import LayoutSelector from './LayoutSelector.vue';

const T = 'admin.dev.crudGenerator';

const props = defineProps<{
  config: CrudConfig;
}>();

const emit = defineEmits<{
  'update:config': [config: CrudConfig];
  snapshot: [];
}>();

function updateConfig(patch: Partial<CrudConfig>) {
  emit('update:config', { ...props.config, ...patch });
}

function updateListConfig(patch: Partial<CrudConfig['list_config']>) {
  emit('update:config', {
    ...props.config,
    list_config: { ...props.config.list_config, ...patch },
  });
}

function updateFormConfig(patch: Partial<CrudConfig['form_config']>) {
  emit('update:config', {
    ...props.config,
    form_config: { ...props.config.form_config, ...patch },
  });
}

function onLayoutChange(variant: LayoutVariant) {
  emit('update:config', {
    ...props.config,
    layout: { ...props.config.layout, variant },
  });
  emit('snapshot');
}

function toggleOperation(op: string) {
  const ops = [...props.config.operations];
  const idx = ops.indexOf(op);
  if (idx >= 0) {
    ops.splice(idx, 1);
  } else {
    ops.push(op);
  }
  updateConfig({ operations: ops });
}
</script>

<template>
  <div class="advanced-options-section">
    <Form layout="vertical" size="small">
      <!-- Layout Variant -->
      <Divider orientation="left" plain class="!my-2 !text-xs">
        {{ $t(`${T}.layout.title`) }}
      </Divider>
      <LayoutSelector
        :value="config.layout.variant"
        @change="onLayoutChange"
      />

      <!-- Table Options -->
      <Divider orientation="left" plain class="!my-2 !text-xs">
        {{ $t(`${T}.listConfig.tableOptions`) }}
      </Divider>

      <div class="mb-3 flex flex-wrap gap-x-6 gap-y-2">
        <Checkbox
          :checked="config.list_config.show_checkbox"
          @update:checked="(v: boolean) => updateListConfig({ show_checkbox: v })"
        >
          <span class="text-xs">{{ $t(`${T}.listConfig.showCheckbox`) }}</span>
        </Checkbox>
        <Checkbox
          :checked="config.list_config.show_index"
          @update:checked="(v: boolean) => updateListConfig({ show_index: v })"
        >
          <span class="text-xs">{{ $t(`${T}.listConfig.showIndex`) }}</span>
        </Checkbox>
        <Checkbox
          :checked="config.list_config.stripe"
          @update:checked="(v: boolean) => updateListConfig({ stripe: v })"
        >
          <span class="text-xs">{{ $t(`${T}.listConfig.stripe`) }}</span>
        </Checkbox>
        <Checkbox
          :checked="config.list_config.pager"
          @update:checked="(v: boolean) => updateListConfig({ pager: v })"
        >
          <span class="text-xs">{{ $t(`${T}.listConfig.pager`) }}</span>
        </Checkbox>
        <Checkbox
          :checked="config.list_config.toolbar_search"
          @update:checked="(v: boolean) => updateListConfig({ toolbar_search: v })"
        >
          <span class="text-xs">{{ $t(`${T}.listConfig.toolbarSearch`) }}</span>
        </Checkbox>
        <Checkbox
          :checked="config.list_config.toolbar_export"
          @update:checked="(v: boolean) => updateListConfig({ toolbar_export: v })"
        >
          <span class="text-xs">{{ $t(`${T}.listConfig.toolbarExport`) }}</span>
        </Checkbox>
      </div>

      <Row :gutter="12">
        <Col :span="12">
          <Form.Item :label="$t(`${T}.listConfig.defaultSort`)" class="!mb-2">
            <Input
              :value="config.list_config.default_sort"
              :placeholder="$t(`${T}.listConfig.defaultSortPlaceholder`)"
              @update:value="(v: string) => updateListConfig({ default_sort: v })"
            />
          </Form.Item>
        </Col>
      </Row>

      <!-- Operations -->
      <Divider orientation="left" plain class="!my-2 !text-xs">
        {{ $t(`${T}.listConfig.operationConfig`) }}
      </Divider>

      <div class="mb-3 flex flex-wrap gap-x-6 gap-y-2">
        <Checkbox
          :checked="config.operations.includes('edit')"
          @update:checked="() => toggleOperation('edit')"
        >
          <span class="text-xs">{{ $t(`${T}.listConfig.operationEdit`) }}</span>
        </Checkbox>
        <Checkbox
          :checked="config.operations.includes('delete')"
          @update:checked="() => toggleOperation('delete')"
        >
          <span class="text-xs">{{ $t(`${T}.listConfig.operationDelete`) }}</span>
        </Checkbox>
        <Checkbox
          :checked="config.operations.includes('view')"
          @update:checked="() => toggleOperation('view')"
        >
          <span class="text-xs">{{ $t(`${T}.listConfig.operationView`) }}</span>
        </Checkbox>
      </div>

      <!-- Form Options -->
      <Divider orientation="left" plain class="!my-2 !text-xs">
        {{ $t(`${T}.formConfig.formOptions`) }}
      </Divider>

      <Row :gutter="12">
        <Col :span="8">
          <Form.Item :label="$t(`${T}.formConfig.formType`)" class="!mb-2">
            <Radio.Group
              :value="config.form_config.form_type"
              button-style="solid"
              size="small"
              @change="(e: { target: { value?: string } }) => updateFormConfig({ form_type: (e.target.value ?? 'drawer') as FormType })"
            >
              <Radio.Button value="drawer">
                {{ $t(`${T}.formConfig.formTypeDrawer`) }}
              </Radio.Button>
              <Radio.Button value="modal">
                {{ $t(`${T}.formConfig.formTypeModal`) }}
              </Radio.Button>
            </Radio.Group>
          </Form.Item>
        </Col>
        <Col :span="8">
          <Form.Item :label="$t(`${T}.formConfig.columns`)" class="!mb-2">
            <Select
              :value="config.form_config.columns"
              :options="[{ label: '1', value: 1 }, { label: '2', value: 2 }, { label: '3', value: 3 }]"
              @change="(v: unknown) => updateFormConfig({ columns: Number(v) || 1 })"
            />
          </Form.Item>
        </Col>
        <Col :span="8">
          <Form.Item :label="$t(`${T}.formConfig.labelWidth`)" class="!mb-2">
            <InputNumber
              :min="60"
              :max="200"
              :value="config.form_config.label_width"
              style="width: 100%"
              @change="(v: unknown) => updateFormConfig({ label_width: Number(v) || 120 })"
            />
          </Form.Item>
        </Col>
      </Row>
    </Form>
  </div>
</template>
