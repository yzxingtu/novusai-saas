<script setup lang="ts">
import { computed, ref } from 'vue';

import {
  Button,
  Card,
  Checkbox,
  Empty,
  Input,
  Radio,
  Select,
  Table,
  Tag,
  Tooltip,
} from 'ant-design-vue';

import { $t } from '#/locales';

import type { CrudConfig, FieldConfig } from '../types';

import {
  createDefaultField,
  getDefaultsByType,
  getFieldTypeOptions,
  inferFieldByName,
} from '../composables/field-inference';

import FieldDetailDrawer from './FieldDetailDrawer.vue';

const props = defineProps<{
  config: CrudConfig;
}>();

const emit = defineEmits<{
  (e: 'update:config', config: CrudConfig): void;
  (e: 'snapshot'): void;
}>();

const T = 'admin.dev.crudGenerator.field';
const _FT = 'admin.dev.crudGenerator.field.fieldType';

const viewMode = ref<'card' | 'table'>('card');
const editingField = ref<FieldConfig | null>(null);
const drawerVisible = ref(false);

/** Type icon mapping */
const TYPE_ICONS: Record<string, string> = {
  string: 'icon-[lucide--type]',
  text: 'icon-[lucide--text]',
  integer: 'icon-[lucide--hash]',
  float: 'icon-[lucide--percent]',
  decimal: 'icon-[lucide--circle-dollar-sign]',
  boolean: 'icon-[lucide--toggle-left]',
  datetime: 'icon-[lucide--calendar-clock]',
  date: 'icon-[lucide--calendar]',
  json: 'icon-[lucide--braces]',
  enum: 'icon-[lucide--list]',
  file: 'icon-[lucide--paperclip]',
};

function toggleFieldProp(index: number, prop: 'in_form' | 'in_list' | 'required' | 'searchable') {
  const field = props.config.fields[index];
  if (!field) return;
  const updated = { ...field, [prop]: !field[prop] };
  const fields = props.config.fields.map((f, i) => (i === index ? updated : f));
  emit('update:config', { ...props.config, fields });
}

function updateFieldProp(index: number, prop: keyof FieldConfig, value: unknown) {
  const field = props.config.fields[index];
  if (!field) return;
  const updated = { ...field, [prop]: value };
  const fields = props.config.fields.map((f, i) => (i === index ? updated : f));
  emit('update:config', { ...props.config, fields });
}

function addField() {
  const fields = [...props.config.fields, createDefaultField()];
  emit('update:config', { ...props.config, fields });
  emit('snapshot');
}

function removeField(index: number) {
  const fields = props.config.fields.filter((_, i) => i !== index);
  emit('update:config', { ...props.config, fields });
  emit('snapshot');
}

function openDetail(field: FieldConfig) {
  editingField.value = field;
  drawerVisible.value = true;
}

function closeDetail() {
  drawerVisible.value = false;
  editingField.value = null;
}

function onFieldDetailUpdate(updated: FieldConfig) {
  if (!editingField.value) return;
  const idx = props.config.fields.indexOf(editingField.value);
  if (idx < 0) return;
  const fields = props.config.fields.map((f, i) => (i === idx ? updated : f));
  emit('update:config', { ...props.config, fields });
}

function onFieldNameChange(index: number, val: string) {
  const field = props.config.fields[index];
  if (!field) return;

  let updated: FieldConfig = { ...field, name: val };
  if (val) {
    const inferred = inferFieldByName(val);
    if (inferred) {
      updated = { ...updated, ...inferred, name: val };
    }
  }

  const fields = props.config.fields.map((f, i) => (i === index ? updated : f));
  emit('update:config', { ...props.config, fields });
}

function onFieldTypeChange(index: number, newType: unknown) {
  const field = props.config.fields[index];
  if (!field) return;
  const type = newType as FieldConfig['type'];
  const defaults = getDefaultsByType(type);
  const updated = { ...field, type, ...defaults };
  const fields = props.config.fields.map((f, i) => (i === index ? updated : f));
  emit('update:config', { ...props.config, fields });
}

function moveField(fromIndex: number, direction: -1 | 1) {
  const toIndex = fromIndex + direction;
  if (toIndex < 0 || toIndex >= props.config.fields.length) return;
  const fields = [...props.config.fields];
  const temp = fields[fromIndex]!;
  fields[fromIndex] = fields[toIndex]!;
  fields[toIndex] = temp;
  emit('update:config', { ...props.config, fields });
  emit('snapshot');
}

const columns = computed(() => [
  {
    title: '#',
    dataIndex: 'sort',
    width: 60,
    align: 'center' as const,
  },
  {
    title: $t(`${T}.name`),
    dataIndex: 'name',
    width: 150,
  },
  {
    title: $t(`${T}.type`),
    dataIndex: 'type',
    width: 120,
  },
  {
    title: $t(`${T}.labelZh`),
    dataIndex: 'label_zh',
    width: 120,
  },
  {
    title: $t(`${T}.labelEn`),
    dataIndex: 'label_en',
    width: 120,
  },
  {
    title: $t(`${T}.required`),
    dataIndex: 'required',
    width: 60,
    align: 'center' as const,
  },
  {
    title: $t(`${T}.searchable`),
    dataIndex: 'searchable',
    width: 70,
    align: 'center' as const,
  },
  {
    title: $t(`${T}.inList`),
    dataIndex: 'in_list',
    width: 60,
    align: 'center' as const,
  },
  {
    title: $t(`${T}.inForm`),
    dataIndex: 'in_form',
    width: 60,
    align: 'center' as const,
  },
  {
    title: '',
    dataIndex: 'actions',
    width: 90,
    align: 'center' as const,
  },
]);
</script>

<template>
  <div class="step-field-define">
    <!-- Toolbar -->
    <div class="mb-3 flex items-center justify-between">
      <div class="text-muted-foreground text-sm">
        {{ config.fields.length }} {{ $t(`${T}.title`).toLowerCase() }}
      </div>
      <div class="flex items-center gap-2">
        <Radio.Group v-model:value="viewMode" size="small">
          <Tooltip :title="$t(`${T}.viewTable`)">
            <Radio.Button value="table">
              <span class="icon-[lucide--table] size-3.5" />
            </Radio.Button>
          </Tooltip>
          <Tooltip :title="$t(`${T}.viewCard`)">
            <Radio.Button value="card">
              <span class="icon-[lucide--layout-grid] size-3.5" />
            </Radio.Button>
          </Tooltip>
        </Radio.Group>
        <Button size="small" type="dashed" @click="addField">
          <template #icon>
            <span class="icon-[lucide--plus] size-3.5" />
          </template>
          {{ $t(`${T}.add`) }}
        </Button>
      </div>
    </div>

    <!-- Card View -->
    <div v-if="config.fields.length > 0 && viewMode === 'card'" class="space-y-2">
      <Card
        v-for="(field, idx) in config.fields"
        :key="idx"
        class="group transition-shadow hover:shadow-md"
        size="small"
      >
        <div class="flex items-start gap-3">
          <!-- Left: Type icon + info -->
          <div class="flex min-w-0 flex-1 items-start gap-3">
            <Tooltip :title="$t(`${_FT}.${field.type}`)">
              <div class="bg-primary/10 text-primary flex size-9 flex-shrink-0 items-center justify-center rounded-lg">
                <span :class="[TYPE_ICONS[field.type] || 'icon-[lucide--type]', 'size-4']" />
              </div>
            </Tooltip>
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <span class="font-mono text-sm font-medium">{{ field.name || $t(`${T}.namePlaceholder`) }}</span>
                <Tag size="small" class="!text-xs">{{ $t(`${_FT}.${field.type}`) }}</Tag>
                <Tag v-if="field.required" color="red" size="small" class="!text-xs">{{ $t(`${T}.required`) }}</Tag>
              </div>
              <div class="text-muted-foreground mt-0.5 flex items-center gap-3 text-xs">
                <span v-if="field.label_zh">{{ field.label_zh }}</span>
                <span v-if="field.label_en" class="opacity-60">{{ field.label_en }}</span>
                <span v-if="!field.label_zh && !field.label_en" class="opacity-40">{{ $t(`${T}.labelZhPlaceholder`) }}</span>
              </div>
            </div>
          </div>

          <!-- Middle: Property toggles -->
          <div class="flex items-center gap-1">
            <Tooltip :title="$t(`${T}.required`)">
              <Button
                :type="field.required ? 'primary' : 'text'"
                size="small"
                :ghost="field.required"
                @click="toggleFieldProp(idx, 'required')"
              >
                <template #icon>
                  <span class="icon-[lucide--asterisk] size-3.5" />
                </template>
              </Button>
            </Tooltip>
            <Tooltip :title="$t(`${T}.searchable`)">
              <Button
                :type="field.searchable ? 'primary' : 'text'"
                size="small"
                :ghost="field.searchable"
                @click="toggleFieldProp(idx, 'searchable')"
              >
                <template #icon>
                  <span class="icon-[lucide--search] size-3.5" />
                </template>
              </Button>
            </Tooltip>
            <Tooltip :title="$t(`${T}.inList`)">
              <Button
                :type="field.in_list ? 'primary' : 'text'"
                size="small"
                :ghost="field.in_list"
                @click="toggleFieldProp(idx, 'in_list')"
              >
                <template #icon>
                  <span class="icon-[lucide--table-2] size-3.5" />
                </template>
              </Button>
            </Tooltip>
            <Tooltip :title="$t(`${T}.inForm`)">
              <Button
                :type="field.in_form ? 'primary' : 'text'"
                size="small"
                :ghost="field.in_form"
                @click="toggleFieldProp(idx, 'in_form')"
              >
                <template #icon>
                  <span class="icon-[lucide--file-edit] size-3.5" />
                </template>
              </Button>
            </Tooltip>
          </div>

          <!-- Right: Sort + actions -->
          <div class="flex items-center gap-0.5">
            <Button :disabled="idx === 0" size="small" type="text" @click="moveField(idx, -1)">
              <template #icon><span class="icon-[lucide--chevron-up] size-3" /></template>
            </Button>
            <Button :disabled="idx === config.fields.length - 1" size="small" type="text" @click="moveField(idx, 1)">
              <template #icon><span class="icon-[lucide--chevron-down] size-3" /></template>
            </Button>
            <Tooltip :title="$t(`${T}.detail`)">
              <Button size="small" type="text" @click="openDetail(field)">
                <template #icon><span class="icon-[lucide--settings-2] size-3.5" /></template>
              </Button>
            </Tooltip>
            <Tooltip :title="$t(`${T}.delete`)">
              <Button danger size="small" type="text" @click="removeField(idx)">
                <template #icon><span class="icon-[lucide--trash-2] size-3.5" /></template>
              </Button>
            </Tooltip>
          </div>
        </div>
      </Card>
    </div>

    <!-- Table View -->
    <Table
      v-else-if="config.fields.length > 0 && viewMode === 'table'"
      :columns="columns"
      :data-source="config.fields"
      :pagination="false"
      :row-key="(_r: FieldConfig, idx?: number) => idx ?? 0"
      bordered
      size="small"
    >
      <template #headerCell="{ column }">
        <template v-if="column.dataIndex === 'required'">
          <Tooltip :title="$t(`${T}.required`)">
            <span class="icon-[lucide--asterisk] size-3.5" />
          </Tooltip>
        </template>
        <template v-else-if="column.dataIndex === 'searchable'">
          <Tooltip :title="$t(`${T}.searchable`)">
            <span class="icon-[lucide--search] size-3.5" />
          </Tooltip>
        </template>
        <template v-else-if="column.dataIndex === 'in_list'">
          <Tooltip :title="$t(`${T}.inList`)">
            <span class="icon-[lucide--table-2] size-3.5" />
          </Tooltip>
        </template>
        <template v-else-if="column.dataIndex === 'in_form'">
          <Tooltip :title="$t(`${T}.inForm`)">
            <span class="icon-[lucide--file-edit] size-3.5" />
          </Tooltip>
        </template>
      </template>
      <template #bodyCell="{ column, index }">
        <!-- Sort buttons -->
        <template v-if="column.dataIndex === 'sort'">
          <div class="flex items-center justify-center gap-0.5">
            <Button
              :disabled="index === 0"
              size="small"
              type="text"
              @click="moveField(index, -1)"
            >
              <template #icon>
                <span class="icon-[lucide--chevron-up] size-3" />
              </template>
            </Button>
            <Button
              :disabled="index === config.fields.length - 1"
              size="small"
              type="text"
              @click="moveField(index, 1)"
            >
              <template #icon>
                <span class="icon-[lucide--chevron-down] size-3" />
              </template>
            </Button>
          </div>
        </template>

        <!-- Name -->
        <template v-else-if="column.dataIndex === 'name'">
          <Input
            :placeholder="$t(`${T}.namePlaceholder`)"
            :value="config.fields[index]!.name"
            size="small"
            @change="(e: Event) => onFieldNameChange(index, (e.target as HTMLInputElement).value)"
          />
        </template>

        <!-- Type -->
        <template v-else-if="column.dataIndex === 'type'">
          <Select
            :options="getFieldTypeOptions()"
            :value="config.fields[index]!.type"
            size="small"
            style="width: 100%"
            @change="(v: unknown) => onFieldTypeChange(index, v)"
          />
        </template>

        <!-- Label ZH -->
        <template v-else-if="column.dataIndex === 'label_zh'">
          <Input
            :value="config.fields[index]!.label_zh"
            :placeholder="$t(`${T}.labelZhPlaceholder`)"
            size="small"
            @change="(e: Event) => updateFieldProp(index, 'label_zh', (e.target as HTMLInputElement).value)"
          />
        </template>

        <!-- Label EN -->
        <template v-else-if="column.dataIndex === 'label_en'">
          <Input
            :value="config.fields[index]!.label_en"
            :placeholder="$t(`${T}.labelEnPlaceholder`)"
            size="small"
            @change="(e: Event) => updateFieldProp(index, 'label_en', (e.target as HTMLInputElement).value)"
          />
        </template>

        <!-- Required -->
        <template v-else-if="column.dataIndex === 'required'">
          <Checkbox :checked="config.fields[index]!.required" @update:checked="() => toggleFieldProp(index, 'required')" />
        </template>

        <!-- Searchable -->
        <template v-else-if="column.dataIndex === 'searchable'">
          <Checkbox :checked="config.fields[index]!.searchable" @update:checked="() => toggleFieldProp(index, 'searchable')" />
        </template>

        <!-- In List -->
        <template v-else-if="column.dataIndex === 'in_list'">
          <Checkbox :checked="config.fields[index]!.in_list" @update:checked="() => toggleFieldProp(index, 'in_list')" />
        </template>

        <!-- In Form -->
        <template v-else-if="column.dataIndex === 'in_form'">
          <Checkbox :checked="config.fields[index]!.in_form" @update:checked="() => toggleFieldProp(index, 'in_form')" />
        </template>

        <!-- Actions -->
        <template v-else-if="column.dataIndex === 'actions'">
          <div class="flex items-center justify-center gap-1">
            <Tooltip :title="$t(`${T}.detail`)">
              <Button
                size="small"
                type="text"
                @click="openDetail(config.fields[index]!)"
              >
                <template #icon>
                  <span class="icon-[lucide--settings-2] size-3.5" />
                </template>
              </Button>
            </Tooltip>
            <Button
              danger
              size="small"
              type="text"
              @click="removeField(index)"
            >
              <template #icon>
                <span class="icon-[lucide--trash-2] size-3.5" />
              </template>
            </Button>
          </div>
        </template>
      </template>
    </Table>

    <Empty
      v-else
      :description="$t(`${T}.empty`)"
      class="py-12"
    />

    <!-- Field Detail Drawer -->
    <FieldDetailDrawer
      :field="editingField"
      :open="drawerVisible"
      @close="closeDetail"
      @update:field="onFieldDetailUpdate"
      @snapshot="emit('snapshot')"
    />
  </div>
</template>
