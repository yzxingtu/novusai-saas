<script setup lang="ts">
import { ref } from 'vue';

import {
  Button,
  Input,
  Popconfirm,
  Select,
  Switch,
  Table,
  Tooltip,
} from 'ant-design-vue';

import { $t } from '#/locales';

import type { CrudConfig, FieldConfig, FieldType } from '../types';

import FieldImportWizard from './FieldImportWizard.vue';

const props = defineProps<{
  entity: CrudConfig;
}>();

const emit = defineEmits<{
  touched: [path: string];
}>();

const T = 'admin.dev.crudGenerator.field';

const showImportWizard = ref(false);

function onImportApplied(fields: FieldConfig[], _touchedFields: string[]) {
  props.entity.fields.length = 0;
  props.entity.fields.push(...fields);
  emit('touched', 'fields');
}

const fieldTypeOptions: Array<{ value: FieldType; label: string }> = [
  { value: 'string', label: 'String' },
  { value: 'text', label: 'Text' },
  { value: 'integer', label: 'Integer' },
  { value: 'float', label: 'Float' },
  { value: 'decimal', label: 'Decimal' },
  { value: 'boolean', label: 'Boolean' },
  { value: 'datetime', label: 'DateTime' },
  { value: 'date', label: 'Date' },
  { value: 'json', label: 'JSON' },
  { value: 'enum', label: 'Enum' },
  { value: 'file', label: 'File' },
];

function addField() {
  const field: FieldConfig = {
    name: '',
    type: 'string',
    label_zh: '',
    label_en: '',
    required: false,
    nullable: true,
    unique: false,
    max_length: null,
    default: null,
    index: false,
    enum_ref: null,
    enum_values: null,
    relation_ref: null,
    filterable: false,
    sortable: false,
    searchable: false,
    search_op: 'ilike',
    in_list: true,
    list_width: null,
    list_align: 'left',
    list_render: null,
    list_slot: null,
    list_fixed: null,
    list_sortable: false,
    in_form: true,
    form_component: 'Input',
    form_group: null,
    form_placeholder: null,
    form_rules: null,
    form_depends_on: null,
    form_col_span: null,
    form_help: null,
    upload: null,
  };
  props.entity.fields.push(field);
  emit('touched', 'fields');
}

function removeField(index: number) {
  props.entity.fields.splice(index, 1);
  emit('touched', 'fields');
}

function onFieldChange() {
  emit('touched', 'fields');
}

const columns = [
  { title: $t(`${T}.name`), dataIndex: 'name', width: 140 },
  { title: $t(`${T}.type`), dataIndex: 'type', width: 110 },
  { title: $t(`${T}.labelZh`), dataIndex: 'label_zh', width: 120 },
  { title: $t(`${T}.labelEn`), dataIndex: 'label_en', width: 120 },
  { title: $t(`${T}.required`), dataIndex: 'required', width: 70, align: 'center' as const },
  { title: $t(`${T}.searchable`), dataIndex: 'searchable', width: 70, align: 'center' as const },
  { title: $t(`${T}.inList`), dataIndex: 'in_list', width: 70, align: 'center' as const },
  { title: $t(`${T}.inForm`), dataIndex: 'in_form', width: 70, align: 'center' as const },
  { title: '', dataIndex: 'actions', width: 50, fixed: 'right' as const },
];
</script>

<template>
  <div>
    <div class="mb-3 flex items-center justify-between">
      <span class="text-sm font-medium">
        {{ $t(`${T}.title`) }} ({{ entity.fields.length }})
      </span>
      <div class="flex gap-2">
        <Button size="small" @click="showImportWizard = true">
          <template #icon>
            <span class="icon-[lucide--upload] size-3.5" />
          </template>
          {{ $t('admin.dev.crudGenerator.fieldImport.title') }}
        </Button>
        <Button size="small" type="primary" @click="addField">
          <template #icon>
            <span class="icon-[lucide--plus] size-3.5" />
          </template>
          {{ $t(`${T}.add`) }}
        </Button>
      </div>
    </div>

    <Table
      :columns="columns"
      :data-source="entity.fields"
      :pagination="false"
      :scroll="{ x: 900 }"
      bordered
      row-key="name"
      size="small"
    >
      <template #bodyCell="{ column, record, index }">
        <template v-if="column.dataIndex === 'name'">
          <Input
            v-model:value="(record as FieldConfig).name"
            :placeholder="$t(`${T}.namePlaceholder`)"
            size="small"
            @change="onFieldChange"
          />
        </template>

        <template v-else-if="column.dataIndex === 'type'">
          <Select
            v-model:value="(record as FieldConfig).type"
            :options="fieldTypeOptions"
            class="w-full"
            size="small"
            @change="onFieldChange"
          />
        </template>

        <template v-else-if="column.dataIndex === 'label_zh'">
          <Input
            v-model:value="(record as FieldConfig).label_zh"
            :placeholder="$t(`${T}.labelZhPlaceholder`)"
            size="small"
            @change="onFieldChange"
          />
        </template>

        <template v-else-if="column.dataIndex === 'label_en'">
          <Input
            v-model:value="(record as FieldConfig).label_en"
            :placeholder="$t(`${T}.labelEnPlaceholder`)"
            size="small"
            @change="onFieldChange"
          />
        </template>

        <template v-else-if="column.dataIndex === 'required'">
          <Switch
            v-model:checked="(record as FieldConfig).required"
            size="small"
            @change="onFieldChange"
          />
        </template>

        <template v-else-if="column.dataIndex === 'searchable'">
          <Switch
            v-model:checked="(record as FieldConfig).searchable"
            size="small"
            @change="onFieldChange"
          />
        </template>

        <template v-else-if="column.dataIndex === 'in_list'">
          <Switch
            v-model:checked="(record as FieldConfig).in_list"
            size="small"
            @change="onFieldChange"
          />
        </template>

        <template v-else-if="column.dataIndex === 'in_form'">
          <Switch
            v-model:checked="(record as FieldConfig).in_form"
            size="small"
            @change="onFieldChange"
          />
        </template>

        <template v-else-if="column.dataIndex === 'actions'">
          <Popconfirm
            :title="$t('common.confirmDelete')"
            @confirm="removeField(index)"
          >
            <Tooltip :title="$t('common.delete')">
              <Button danger size="small" type="text">
                <template #icon>
                  <span class="icon-[lucide--trash-2] size-3.5" />
                </template>
              </Button>
            </Tooltip>
          </Popconfirm>
        </template>
      </template>
    </Table>

    <!-- Field Import Wizard -->
    <FieldImportWizard
      v-model:open="showImportWizard"
      :entity="entity"
      @applied="onImportApplied"
    />
  </div>
</template>
