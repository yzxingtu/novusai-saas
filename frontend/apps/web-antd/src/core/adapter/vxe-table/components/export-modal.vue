<script lang="ts" setup>
/**
 * Excel export modal component
 * Excel 导出弹窗组件
 *
 * Uses Vben Modal + Ant Design Vue, replaces vxe-table native export dialog.
 * Supports: current page data, selected data.
 * 使用 Vben Modal + Ant Design Vue 组件，替代 vxe-table 原生导出弹窗。
 * 支持：当前页数据、已选数据。
 */
import type { VxeGridInstance } from 'vxe-table';

import { computed, ref } from 'vue';

import { useVbenModal } from '@vben/common-ui';

import {
  Checkbox,
  CheckboxGroup,
  Form,
  FormItem,
  Input,
  message,
  RadioGroup,
} from 'ant-design-vue';

import { $t } from '#/locales';

import { writeRecordsToExcel } from '../excel-export';

interface ColumnOption {
  disabled?: boolean;
  field: string;
  label: string;
  value: string;
}

const props = defineProps<{
  /** Grid instance getter function / Grid 实例获取函数 */
  gridGetter: () => undefined | VxeGridInstance;
  /** Callback to register open method / 注册打开方法的回调 */
  onRegister?: (openFn: () => void) => void;
}>();

const emits = defineEmits<{
  success: [];
}>();

// Form data / 表单数据
const filename = ref(`export_${new Date().toISOString().slice(0, 10)}`);
const sheetName = ref('Sheet1');
const exportScope = ref<'current' | 'selected'>('current');
const selectedColumns = ref<string[]>([]);

// Column options / 列选项
const columnOptions = ref<ColumnOption[]>([]);

// Whether there are selected rows (for showing "selected data" option) / 是否有选中的行（用于显示“已选数据”选项）
const hasSelectedRows = ref(false);
const selectedRowCount = ref(0);

// Modal / 弹窗
const [Modal, modalApi] = useVbenModal({
  onOpenChange(isOpen) {
    if (isOpen) {
      initColumns();
      checkSelectedRows();
    }
  },
  async onConfirm() {
    await handleExport();
  },
});

/** Check for selected rows / 检查是否有选中的行 */
function checkSelectedRows() {
  const grid = props.gridGetter();
  if (!grid) {
    hasSelectedRows.value = false;
    selectedRowCount.value = 0;
    exportScope.value = 'current';
    return;
  }

  const rows = grid.getCheckboxRecords();
  hasSelectedRows.value = rows.length > 0;
  selectedRowCount.value = rows.length;

  // Default to "selected data" if rows selected, otherwise "current page" / 如果有选中的行，默认选择“已选数据”；否则默认选择“当前页数据”
  exportScope.value = hasSelectedRows.value ? 'selected' : 'current';
}

/** Initialize exportable columns / 初始化可导出的列 */
function initColumns() {
  const grid = props.gridGetter();
  if (!grid) return;

  const tableColumns = grid.getTableColumn().fullColumn;
  const options: ColumnOption[] = [];
  const selected: string[] = [];

  tableColumns.forEach((col) => {
    // Exclude special columns / 排除特殊列
    if (!col.field) return;
    if (col.type === 'checkbox' || col.type === 'seq' || col.type === 'expand')
      return;
    if (col.field === '_drag') return;

    // Operation column not selected by default / 操作列默认不选中
    const isOperation = col.field === 'operation';
    const option: ColumnOption = {
      field: col.field,
      label: String(col.title || col.field),
      value: col.field,
      disabled: false,
    };

    options.push(option);
    if (!isOperation) {
      selected.push(col.field);
    }
  });

  columnOptions.value = options;
  selectedColumns.value = selected;
}

/** Execute export / 执行导出 */
async function handleExport() {
  const grid = props.gridGetter();
  if (!grid) {
    message.warning($t('shared.common.noData'));
    return;
  }

  // Get data based on export scope / 根据导出范围获取数据
  let tableData: any[];
  if (exportScope.value === 'selected') {
    tableData = grid.getCheckboxRecords();
  } else {
    const { tableData: currentPageData } = grid.getTableData();
    tableData = currentPageData;
  }

  if (!tableData || tableData.length === 0) {
    message.warning($t('shared.common.noData'));
    return;
  }

  // Get selected column config / 获取选中的列配置
  const tableColumns = grid.getTableColumn().fullColumn;
  const exportColumns = tableColumns.filter(
    (col) => col.field && selectedColumns.value.includes(col.field),
  );

  if (exportColumns.length === 0) {
    message.warning($t('shared.common.exportModal.selectAtLeastOneColumn'));
    return;
  }

  const headers = exportColumns.map((col) => String(col.title || col.field));
  const rows = tableData.map((row: any) =>
    exportColumns.map((col) => {
      const field = col.field;
      return field ? (row[field] ?? '') : '';
    }),
  );

  await writeRecordsToExcel({
    filename: filename.value,
    headers,
    rows,
    sheetName: sheetName.value,
  });

  message.success($t('shared.common.exportSuccess'));
  emits('success');
  modalApi.close();
}

/** Select/deselect all columns / 全选/取消全选列 */
const isAllSelected = computed(() => {
  const selectableColumns = columnOptions.value.filter((c) => !c.disabled);
  return (
    selectableColumns.length > 0 &&
    selectableColumns.every((c) => selectedColumns.value.includes(c.value))
  );
});

const isIndeterminate = computed(() => {
  const selectableColumns = columnOptions.value.filter((c) => !c.disabled);
  const selectedCount = selectableColumns.filter((c) =>
    selectedColumns.value.includes(c.value),
  ).length;
  return selectedCount > 0 && selectedCount < selectableColumns.length;
});

function toggleSelectAll(checked: boolean) {
  selectedColumns.value = checked
    ? columnOptions.value.filter((c) => !c.disabled).map((c) => c.value)
    : [];
}

// Export scope options (always shown, "selected data" disabled when unchecked) / 导出范围选项
const scopeOptions = computed(() => {
  return [
    {
      label: hasSelectedRows.value
        ? `${$t('shared.common.exportModal.selectedData')} (${selectedRowCount.value})`
        : $t('shared.common.exportModal.selectedData'),
      value: 'selected',
      disabled: !hasSelectedRows.value,
    },
    { label: $t('shared.common.exportModal.currentPage'), value: 'current' },
  ];
});

// Expose open method / 暴露打开方法
function open() {
  modalApi.open();
}

// Call register callback, pass open method / 调用注册回调，传递 open 方法
if (props.onRegister) {
  props.onRegister(open);
}

defineExpose({ open });
</script>

<template>
  <Modal
    :title="$t('shared.common.exportModal.title')"
    :confirm-text="$t('shared.common.export')"
    :cancel-text="$t('shared.common.cancel')"
  >
    <Form layout="vertical" class="pt-2">
      <!-- Filename / 文件名 -->
      <FormItem :label="$t('shared.common.exportModal.filename')">
        <Input v-model:value="filename" />
      </FormItem>

      <!-- Sheet name / 工作表名 -->
      <FormItem :label="$t('shared.common.exportModal.sheetName')">
        <Input v-model:value="sheetName" />
      </FormItem>

      <!-- Export scope / 导出范围 -->
      <FormItem :label="$t('shared.common.exportModal.scope')">
        <RadioGroup v-model:value="exportScope" :options="scopeOptions" />
      </FormItem>

      <!-- Select columns / 选择列 -->
      <FormItem :label="$t('shared.common.exportModal.columns')">
        <div class="mb-2">
          <Checkbox
            :checked="isAllSelected"
            :indeterminate="isIndeterminate"
            @change="(e: any) => toggleSelectAll(e.target.checked)"
          >
            {{ $t('shared.common.selectAll') }}
          </Checkbox>
        </div>
        <CheckboxGroup
          v-model:value="selectedColumns"
          class="flex flex-wrap gap-2"
        >
          <Checkbox
            v-for="col in columnOptions"
            :key="col.value"
            :value="col.value"
            :disabled="col.disabled"
          >
            {{ col.label }}
          </Checkbox>
        </CheckboxGroup>
      </FormItem>
    </Form>
  </Modal>
</template>
