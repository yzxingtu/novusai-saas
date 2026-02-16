<script setup lang="ts">
import type { RadioChangeEvent } from 'ant-design-vue/es/radio/interface';

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

import type { FieldConfig, FormComponent, ListRenderPreset } from '../types';

import {
  FORM_COMPONENT_OPTIONS,
  SEARCH_COMPONENT_OPTIONS,
  getAlignOptions,
  getFixedOptions,
  getRenderPresetOptions,
  getSearchOperatorOptions,
} from '../constants';

const T = 'admin.dev.crudGenerator.field.detailDrawer';
const TL = 'admin.dev.crudGenerator.listConfig';

const props = defineProps<{
  field: FieldConfig;
}>();

const emit = defineEmits<{
  'update:field': [field: FieldConfig];
}>();

function update<K extends keyof FieldConfig>(key: K, value: FieldConfig[K]) {
  emit('update:field', { ...props.field, [key]: value });
}

function setNum(key: 'form_col_span' | 'list_width' | 'max_length', v: unknown) {
  update(key, (typeof v === 'number' ? v : null) as FieldConfig[typeof key]);
}

function setStr(key: 'enum_ref' | 'form_group' | 'form_help' | 'form_placeholder' | 'list_fixed', v: unknown) {
  update(key, (typeof v === 'string' && v ? v : null) as FieldConfig[typeof key]);
}

function setListRender(v: unknown) {
  update('list_render', (typeof v === 'string' && v ? v : null) as ListRenderPreset | null);
}

function setFormComponent(v: unknown) {
  update('form_component', (typeof v === 'string' && v ? v : 'Input') as FormComponent);
}
</script>

<template>
  <div class="field-expanded border-t bg-accent/30 px-4 py-3">
    <Form layout="vertical" size="small">
      <!-- DB Constraints -->
      <Divider orientation="left" plain class="!my-2 !text-xs">
        {{ $t(`${T}.basicSection`) }}
      </Divider>

      <Row :gutter="12">
        <Col :span="6">
          <Form.Item :label="$t(`${T}.nullable`)" class="!mb-2">
            <Checkbox
              :checked="field.nullable"
              @update:checked="(v: boolean) => update('nullable', v)"
            />
          </Form.Item>
        </Col>
        <Col :span="6">
          <Form.Item :label="$t(`${T}.index`)" class="!mb-2">
            <Checkbox
              :checked="field.index"
              @update:checked="(v: boolean) => update('index', v)"
            />
          </Form.Item>
        </Col>
        <Col v-if="field.type === 'string' || field.type === 'text'" :span="6">
          <Form.Item :label="$t(`${T}.maxLength`)" class="!mb-2">
            <InputNumber
              :min="1"
              :placeholder="'-'"
              :value="field.max_length ?? undefined"
              style="width: 100%"
              @change="(v: unknown) => setNum('max_length', v)"
            />
          </Form.Item>
        </Col>
        <Col v-if="field.type === 'enum'" :span="6">
          <Form.Item :label="$t(`${T}.enumRef`)" class="!mb-2">
            <Input
              :value="field.enum_ref ?? ''"
              :placeholder="$t(`${T}.enumRefPlaceholder`)"
              @change="(e: Event) => setStr('enum_ref', (e.target as HTMLInputElement).value)"
            />
          </Form.Item>
        </Col>
      </Row>

      <!-- Search config (only when searchable) -->
      <template v-if="field.searchable">
        <Divider orientation="left" plain class="!my-2 !text-xs">
          {{ $t(`${T}.searchSection`) }}
        </Divider>

        <Row :gutter="12">
          <Col :span="12">
            <Form.Item :label="$t(`${T}.searchOp`)" class="!mb-2">
              <Select
                :value="field.search_op"
                :options="getSearchOperatorOptions()"
                style="width: 100%"
                @change="(v: unknown) => update('search_op', v as FieldConfig['search_op'])"
              />
            </Form.Item>
          </Col>
          <Col :span="12">
            <Form.Item :label="$t(`${T}.searchComponent`)" class="!mb-2">
              <Select
                :value="field.search_component"
                :options="SEARCH_COMPONENT_OPTIONS"
                style="width: 100%"
                @change="(v: unknown) => update('search_component', v as FieldConfig['search_component'])"
              />
            </Form.Item>
          </Col>
        </Row>
      </template>

      <!-- List config -->
      <Divider orientation="left" plain class="!my-2 !text-xs">
        {{ $t(`${T}.listSection`) }}
      </Divider>

      <Row :gutter="12">
        <Col :span="6">
          <Form.Item :label="$t(`${T}.listWidth`)" class="!mb-2">
            <InputNumber
              :min="40"
              :placeholder="$t(`${TL}.widthAuto`)"
              :value="field.list_width ?? undefined"
              style="width: 100%"
              @change="(v: unknown) => setNum('list_width', v)"
            />
          </Form.Item>
        </Col>
        <Col :span="6">
          <Form.Item :label="$t(`${T}.listAlign`)" class="!mb-2">
            <Radio.Group
              :value="field.list_align"
              :options="getAlignOptions()"
              option-type="button"
              size="small"
              @change="(e: RadioChangeEvent) => update('list_align', String(e.target.value ?? 'left'))"
            />
          </Form.Item>
        </Col>
        <Col :span="6">
          <Form.Item :label="$t(`${T}.listRender`)" class="!mb-2">
            <Select
              :allow-clear="true"
              :options="getRenderPresetOptions()"
              :value="field.list_render ?? undefined"
              placeholder="-"
              style="width: 100%"
              @change="setListRender"
            />
          </Form.Item>
        </Col>
        <Col :span="6">
          <Form.Item :label="$t(`${T}.listFixed`)" class="!mb-2">
            <Select
              :allow-clear="true"
              :options="getFixedOptions()"
              :value="field.list_fixed ?? undefined"
              placeholder="-"
              style="width: 100%"
              @change="(v: unknown) => setStr('list_fixed', v)"
            />
          </Form.Item>
        </Col>
      </Row>

      <!-- Form config -->
      <Divider orientation="left" plain class="!my-2 !text-xs">
        {{ $t(`${T}.formSection`) }}
      </Divider>

      <Row :gutter="12">
        <Col :span="8">
          <Form.Item :label="$t(`${T}.formComponent`)" class="!mb-2">
            <Select
              :options="FORM_COMPONENT_OPTIONS"
              :value="field.form_component"
              style="width: 100%"
              @change="setFormComponent"
            />
          </Form.Item>
        </Col>
        <Col :span="8">
          <Form.Item :label="$t(`${T}.formColSpan`)" class="!mb-2">
            <InputNumber
              :max="24"
              :min="1"
              :placeholder="$t(`${TL}.widthAuto`)"
              :value="field.form_col_span ?? undefined"
              style="width: 100%"
              @change="(v: unknown) => setNum('form_col_span', v)"
            />
          </Form.Item>
        </Col>
        <Col :span="8">
          <Form.Item :label="$t(`${T}.formGroup`)" class="!mb-2">
            <Input
              :value="field.form_group ?? ''"
              placeholder="-"
              @change="(e: Event) => setStr('form_group', (e.target as HTMLInputElement).value)"
            />
          </Form.Item>
        </Col>
      </Row>

      <Row :gutter="12">
        <Col :span="12">
          <Form.Item :label="$t(`${T}.formPlaceholder`)" class="!mb-2">
            <Input
              :value="field.form_placeholder ?? ''"
              placeholder="-"
              @change="(e: Event) => setStr('form_placeholder', (e.target as HTMLInputElement).value)"
            />
          </Form.Item>
        </Col>
        <Col :span="12">
          <Form.Item :label="$t(`${T}.formHelp`)" class="!mb-2">
            <Input
              :value="field.form_help ?? ''"
              placeholder="-"
              @change="(e: Event) => setStr('form_help', (e.target as HTMLInputElement).value)"
            />
          </Form.Item>
        </Col>
      </Row>
    </Form>
  </div>
</template>
