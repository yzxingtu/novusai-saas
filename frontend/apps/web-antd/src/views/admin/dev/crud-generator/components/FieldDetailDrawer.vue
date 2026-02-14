<script setup lang="ts">
import { computed } from 'vue';

import {
  Checkbox,
  Col,
  Divider,
  Drawer,
  Form,
  Input,
  InputNumber,
  Radio,
  Row,
  Select,
} from 'ant-design-vue';

import { $t } from '#/locales';

import type { FieldConfig, FormComponent, ListRenderPreset } from '../types';

import {
  FORM_COMPONENT_OPTIONS,
  getAlignOptions,
  getFixedOptions,
  getRenderPresetOptions,
} from '../constants';
import { createDefaultField } from '../composables/field-inference';

const props = defineProps<{
  field: FieldConfig | null;
  open: boolean;
}>();

const emit = defineEmits<{
  close: [];
  snapshot: [];
}>();

const T = 'admin.dev.crudGenerator.field.detailDrawer';

/** Non-null field ref for template binding (guarded by v-if) */
const f = computed(() => props.field ?? createDefaultField());

const searchOpOptions = [
  { label: 'ILIKE', value: 'ilike' },
  { label: '=', value: 'eq' },
  { label: 'IN', value: 'in' },
  { label: '>=', value: 'gte' },
  { label: '<=', value: 'lte' },
  { label: 'BETWEEN', value: 'between' },
];

const listRenderOptions = getRenderPresetOptions();

const formComponentOptions = FORM_COMPONENT_OPTIONS;

const listAlignOptions = getAlignOptions();

const listFixedOptions = getFixedOptions();

function setNum(key: 'form_col_span' | 'list_width' | 'max_length', v: unknown) {
  if (!props.field) return;
  props.field[key] = typeof v === 'number' ? v : null;
}

function setStr(key: 'enum_ref' | 'form_group' | 'form_help' | 'form_placeholder' | 'list_fixed', v: unknown) {
  if (!props.field) return;
  props.field[key] = typeof v === 'string' && v ? v : null;
}

function setListRender(v: unknown) {
  if (!props.field) return;
  props.field.list_render = (typeof v === 'string' && v ? v : null) as ListRenderPreset | null;
}

function setFormComponent(v: unknown) {
  if (!props.field) return;
  props.field.form_component = (typeof v === 'string' && v ? v : 'Input') as FormComponent;
}

function onClose() {
  emit('snapshot');
  emit('close');
}
</script>

<template>
  <Drawer
    :open="open"
    :title="$t(`${T}.title`)"
    :width="520"
    @close="onClose"
  >
    <template v-if="field">
      <Form layout="vertical">
        <!-- 基础属性 -->
        <Divider orientation="left" plain>
          {{ $t(`${T}.basicSection`) }}
        </Divider>

        <Row :gutter="12">
          <Col :span="12">
            <Form.Item :label="$t(`${T}.nullable`)">
              <Checkbox v-model:checked="f.nullable" />
            </Form.Item>
          </Col>
          <Col :span="12">
            <Form.Item :label="$t(`${T}.index`)">
              <Checkbox v-model:checked="f.index" />
            </Form.Item>
          </Col>
        </Row>

        <Row :gutter="12">
          <Col :span="12">
            <Form.Item :label="$t(`${T}.maxLength`)">
              <InputNumber
                :min="1"
                :placeholder="'-'"
                :value="f.max_length ?? undefined"
                style="width: 100%"
                @change="(v: unknown) => setNum('max_length', v)"
              />
            </Form.Item>
          </Col>
          <Col :span="12">
            <Form.Item :label="$t(`${T}.enumRef`)">
              <Input
                :value="f.enum_ref ?? ''"
                placeholder="EnumName"
                @change="(e: Event) => setStr('enum_ref', (e.target as HTMLInputElement).value)"
              />
            </Form.Item>
          </Col>
        </Row>

        <!-- 搜索配置 -->
        <Divider orientation="left" plain>
          {{ $t(`${T}.searchSection`) }}
        </Divider>

        <Row :gutter="12">
          <Col :span="12">
            <Form.Item :label="$t(`${T}.searchOp`)">
              <Select
                v-model:value="f.search_op"
                :options="searchOpOptions"
                style="width: 100%"
              />
            </Form.Item>
          </Col>
        </Row>

        <!-- 列表配置 -->
        <Divider orientation="left" plain>
          {{ $t(`${T}.listSection`) }}
        </Divider>

        <Row :gutter="12">
          <Col :span="8">
            <Form.Item :label="$t(`${T}.listWidth`)">
              <InputNumber
                :min="40"
                :placeholder="'auto'"
                :value="f.list_width ?? undefined"
                style="width: 100%"
                @change="(v: unknown) => setNum('list_width', v)"
              />
            </Form.Item>
          </Col>
          <Col :span="8">
            <Form.Item :label="$t(`${T}.listAlign`)">
              <Radio.Group
                v-model:value="f.list_align"
                :options="listAlignOptions"
                option-type="button"
                size="small"
              />
            </Form.Item>
          </Col>
          <Col :span="8">
            <Form.Item :label="$t(`${T}.listSortable`)">
              <Checkbox v-model:checked="f.list_sortable" />
            </Form.Item>
          </Col>
        </Row>

        <Row :gutter="12">
          <Col :span="12">
            <Form.Item :label="$t(`${T}.listRender`)">
              <Select
                :allow-clear="true"
                :options="listRenderOptions"
                :value="f.list_render ?? undefined"
                placeholder="-"
                style="width: 100%"
                @change="setListRender"
              />
            </Form.Item>
          </Col>
          <Col :span="12">
            <Form.Item :label="$t(`${T}.listFixed`)">
              <Select
                :allow-clear="true"
                :options="listFixedOptions"
                :value="f.list_fixed ?? undefined"
                placeholder="-"
                style="width: 100%"
                @change="(v: unknown) => setStr('list_fixed', v)"
              />
            </Form.Item>
          </Col>
        </Row>

        <!-- 表单配置 -->
        <Divider orientation="left" plain>
          {{ $t(`${T}.formSection`) }}
        </Divider>

        <Row :gutter="12">
          <Col :span="12">
            <Form.Item :label="$t(`${T}.formComponent`)">
              <Select
                :options="formComponentOptions"
                :value="f.form_component"
                style="width: 100%"
                @change="setFormComponent"
              />
            </Form.Item>
          </Col>
          <Col :span="12">
            <Form.Item :label="$t(`${T}.formColSpan`)">
              <InputNumber
                :max="24"
                :min="1"
                :placeholder="'auto'"
                :value="f.form_col_span ?? undefined"
                style="width: 100%"
                @change="(v: unknown) => setNum('form_col_span', v)"
              />
            </Form.Item>
          </Col>
        </Row>

        <Row :gutter="12">
          <Col :span="12">
            <Form.Item :label="$t(`${T}.formGroup`)">
              <Input
                :value="f.form_group ?? ''"
                placeholder="-"
                @change="(e: Event) => setStr('form_group', (e.target as HTMLInputElement).value)"
              />
            </Form.Item>
          </Col>
          <Col :span="12">
            <Form.Item :label="$t(`${T}.formPlaceholder`)">
              <Input
                :value="f.form_placeholder ?? ''"
                placeholder="-"
                @change="(e: Event) => setStr('form_placeholder', (e.target as HTMLInputElement).value)"
              />
            </Form.Item>
          </Col>
        </Row>

        <Row :gutter="12">
          <Col :span="24">
            <Form.Item :label="$t(`${T}.formHelp`)">
              <Input
                :value="f.form_help ?? ''"
                placeholder="-"
                @change="(e: Event) => setStr('form_help', (e.target as HTMLInputElement).value)"
              />
            </Form.Item>
          </Col>
        </Row>
      </Form>
    </template>
  </Drawer>
</template>
