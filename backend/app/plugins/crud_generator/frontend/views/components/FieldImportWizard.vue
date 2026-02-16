<script setup lang="ts">
import { computed, ref } from 'vue';

import {
  Alert,
  Badge,
  Button,
  Checkbox,
  Input,
  Modal,
  Radio,
  Steps,
  Table,
  Tag,
} from 'ant-design-vue';

import { $t } from '#/locales';

import type {
  MergeMode,
  ParseResult,
  ParsedField,
} from '../composables/field-import-parsers';
import {
  mergeFields,
  parseCSV,
  parseDDL,
  parseJSON,
  parseMigration,
  parsedFieldToConfig,
} from '../composables/field-import-parsers';
import type { CrudConfig, FieldConfig } from '../types';

const props = defineProps<{
  entity: CrudConfig;
  open: boolean;
}>();

const emit = defineEmits<{
  'update:open': [value: boolean];
  applied: [fields: FieldConfig[], touchedFields: string[]];
}>();

const T = 'admin.dev.crudGenerator.fieldImport';

// ---- Wizard state ----
const step = ref(0);
type ImportSource = 'ddl' | 'json' | 'csv' | 'migration';
const source = ref<ImportSource>('ddl');
const inputText = ref('');
const mergeMode = ref<MergeMode>('add_only');
const parseResult = ref<ParseResult | null>(null);
const selectedFields = ref<Set<string>>(new Set());

// ---- Step 0: Input & Source ----
const sourcePlaceholders: Record<ImportSource, string> = {
  ddl: 'CREATE TABLE orders (\n  id SERIAL PRIMARY KEY,\n  title VARCHAR(200) NOT NULL,\n  amount DECIMAL(10,2),\n  status VARCHAR(20) DEFAULT \'draft\',\n  description TEXT\n);',
  json: '[\n  { "name": "title", "type": "string", "required": true },\n  { "name": "amount", "type": "decimal" },\n  { "name": "status", "type": "enum" }\n]',
  csv: 'name,type,required,nullable\ntitle,string,true,false\namount,decimal,false,true\nstatus,enum,false,true',
  migration: "op.create_table('orders',\n    sa.Column('title', sa.String(length=200), nullable=False, comment='Title'),\n    sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=True, comment='Amount'),\n    sa.Column('status', sa.String(length=50), server_default='draft', comment='Status'),\n)",
};

// ---- Step 1: Parse & Validate ----
function doParse() {
  const text = inputText.value.trim();
  if (!text) return;

  switch (source.value) {
    case 'ddl': {
      parseResult.value = parseDDL(text);
      break;
    }
    case 'json': {
      parseResult.value = parseJSON(text);
      break;
    }
    case 'csv': {
      parseResult.value = parseCSV(text);
      break;
    }
    case 'migration': {
      parseResult.value = parseMigration(text);
      break;
    }
  }

  // Select all by default
  selectedFields.value = new Set(
    (parseResult.value?.fields ?? []).map((f) => f.name),
  );

  step.value = 1;
}

// ---- Step 2: Preview & Apply ----
const previewColumns = computed(() => [
  { title: '', dataIndex: 'selected', width: 40 },
  { title: $t(`${T}.fieldName`), dataIndex: 'name', width: 120 },
  { title: $t(`${T}.fieldType`), dataIndex: 'type', width: 90 },
  { title: $t(`${T}.labelZh`), dataIndex: 'label_zh', width: 100 },
  { title: $t(`${T}.labelEn`), dataIndex: 'label_en', width: 100 },
  { title: $t(`${T}.required`), dataIndex: 'required', width: 70 },
  { title: $t(`${T}.nullable`), dataIndex: 'nullable', width: 70 },
  { title: $t(`${T}.status`), dataIndex: 'status', width: 90 },
]);

const existingFieldNames = computed(() =>
  new Set(props.entity.fields.map((f) => f.name)),
);

function getFieldStatus(field: ParsedField): 'new' | 'exists' | 'system' {
  if (field.primary_key) return 'system';
  if (existingFieldNames.value.has(field.name)) return 'exists';
  return 'new';
}

function toggleField(name: string) {
  if (selectedFields.value.has(name)) {
    selectedFields.value.delete(name);
  } else {
    selectedFields.value.add(name);
  }
  // Trigger reactivity
  selectedFields.value = new Set(selectedFields.value);
}

const selectedCount = computed(() => selectedFields.value.size);

// ---- Apply ----
function applyImport() {
  if (!parseResult.value) return;

  const selectedParsed = parseResult.value.fields.filter(
    (f) => selectedFields.value.has(f.name) && !f.primary_key,
  );
  const incoming = selectedParsed.map(parsedFieldToConfig);

  const { merged, added, overwritten } = mergeFields(
    props.entity.fields,
    incoming,
    mergeMode.value,
  );

  const touchedFields = [...added, ...overwritten];

  emit('applied', merged, touchedFields);
  emit('update:open', false);
  resetState();
}

function resetState() {
  step.value = 0;
  inputText.value = '';
  parseResult.value = null;
  selectedFields.value = new Set();
}

function onCancel() {
  emit('update:open', false);
  resetState();
}
</script>

<template>
  <Modal
    :open="open"
    :title="$t(`${T}.title`)"
    :width="800"
    @cancel="onCancel"
    @ok="step < 1 ? doParse() : applyImport()"
  >
    <template #footer>
      <div class="flex items-center justify-between">
        <div>
          <Button v-if="step > 0" @click="step = 0">
            {{ $t(`${T}.back`) }}
          </Button>
        </div>
        <div class="flex gap-2">
          <Button @click="onCancel">
            {{ $t(`${T}.cancel`) }}
          </Button>
          <Button
            v-if="step === 0"
            :disabled="!inputText.trim()"
            type="primary"
            @click="doParse"
          >
            {{ $t(`${T}.parse`) }}
          </Button>
          <Button
            v-else
            :disabled="selectedCount === 0"
            type="primary"
            @click="applyImport"
          >
            {{ $t(`${T}.apply`) }} ({{ selectedCount }})
          </Button>
        </div>
      </div>
    </template>

    <!-- Steps indicator -->
    <Steps :current="step" class="mb-4" size="small">
      <Steps.Step :title="$t(`${T}.stepInput`)" />
      <Steps.Step :title="$t(`${T}.stepPreview`)" />
    </Steps>

    <!-- Step 0: Source + Input -->
    <div v-if="step === 0" class="space-y-4">
      <!-- Source selector -->
      <div>
        <label class="mb-2 block text-sm font-medium">{{ $t(`${T}.source`) }}</label>
        <Radio.Group v-model:value="source" button-style="solid" size="small">
          <Radio.Button value="ddl">DDL</Radio.Button>
          <Radio.Button value="json">JSON</Radio.Button>
          <Radio.Button value="csv">CSV</Radio.Button>
          <Radio.Button value="migration">Migration</Radio.Button>
        </Radio.Group>
      </div>

      <!-- Merge mode -->
      <div>
        <label class="mb-2 block text-sm font-medium">{{ $t(`${T}.mergeMode`) }}</label>
        <Radio.Group v-model:value="mergeMode" size="small">
          <Radio value="add_only">{{ $t(`${T}.addOnly`) }}</Radio>
          <Radio value="overwrite_same">{{ $t(`${T}.overwriteSame`) }}</Radio>
          <Radio value="replace_all">{{ $t(`${T}.replaceAll`) }}</Radio>
        </Radio.Group>
      </div>

      <!-- Input area -->
      <div>
        <label class="mb-2 block text-sm font-medium">{{ $t(`${T}.inputLabel`) }}</label>
        <Input.TextArea
          v-model:value="inputText"
          :placeholder="sourcePlaceholders[source]"
          :rows="12"
          class="font-mono text-sm"
        />
      </div>
    </div>

    <!-- Step 1: Preview & Select -->
    <div v-else-if="step === 1 && parseResult" class="space-y-4">
      <!-- Errors -->
      <Alert
        v-if="parseResult.errors.length > 0"
        :message="$t(`${T}.parseErrors`, { count: parseResult.errors.length })"
        show-icon
        type="warning"
      >
        <template #description>
          <ul class="list-inside list-disc text-xs">
            <li v-for="(err, idx) in parseResult.errors" :key="idx">
              {{ $t(`${T}.errorLine`, { line: err.line }) }}: {{ $t(`${T}.errors.${err.reason}`) }}
              <span v-if="err.field" class="font-mono">({{ err.field }})</span>
            </li>
          </ul>
        </template>
      </Alert>

      <!-- Stats -->
      <div class="flex gap-3 text-sm">
        <Badge :count="parseResult.fields.length" :number-style="{ backgroundColor: 'var(--ant-color-primary)' }">
          <span class="pr-6">{{ $t(`${T}.totalFields`) }}</span>
        </Badge>
        <Badge :count="selectedCount" :number-style="{ backgroundColor: 'var(--ant-color-success)' }">
          <span class="pr-6">{{ $t(`${T}.selected`) }}</span>
        </Badge>
      </div>

      <!-- Preview table -->
      <Table
        :columns="previewColumns"
        :data-source="parseResult.fields"
        :pagination="false"
        :scroll="{ y: 350 }"
        bordered
        row-key="name"
        size="small"
      >
        <template #bodyCell="{ column, record: rawRecord }">
          <template v-if="column.dataIndex === 'selected'">
            <Checkbox
              :checked="selectedFields.has((rawRecord as ParsedField).name)"
              :disabled="(rawRecord as ParsedField).primary_key"
              @change="toggleField((rawRecord as ParsedField).name)"
            />
          </template>

          <template v-else-if="column.dataIndex === 'name'">
            <span class="font-mono text-xs">{{ (rawRecord as ParsedField).name }}</span>
          </template>

          <template v-else-if="column.dataIndex === 'type'">
            <Tag size="small">{{ $t(`admin.dev.crudGenerator.field.fieldType.${(rawRecord as ParsedField).type}`) }}</Tag>
          </template>

          <template v-else-if="column.dataIndex === 'required'">
            <span v-if="(rawRecord as ParsedField).required" class="icon-[lucide--check] size-4 text-success" />
          </template>

          <template v-else-if="column.dataIndex === 'nullable'">
            <span v-if="(rawRecord as ParsedField).nullable" class="icon-[lucide--check] size-4 text-muted-foreground" />
          </template>

          <template v-else-if="column.dataIndex === 'status'">
            <Tag
              :color="{ new: 'green', exists: 'orange', system: 'default' }[getFieldStatus(rawRecord as ParsedField)]"
              size="small"
            >
              {{ $t(`${T}.status_${getFieldStatus(rawRecord as ParsedField)}`) }}
            </Tag>
          </template>
        </template>
      </Table>
    </div>
  </Modal>
</template>
