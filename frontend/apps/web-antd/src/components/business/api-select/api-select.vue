<script lang="ts" setup>
/**
 * ApiSelect - 远程下拉选择组件
 *
 * 功能：
 * - 支持静态选项 (options prop)
 * - 支持远程加载 (api prop)
 * - 支持远程搜索 (showSearch + filterOption: false)
 * - 支持分页 (pagination prop)
 * - 支持点击翻页 (clickPagination prop)
 * - 骨架屏加载效果
 * - 支持选项右侧显示额外内容 (optionRightField / option slot)
 * - 完整分页控件（总条数/总页数/每页条数/页码跳转）
 */
import type { SelectProps } from 'ant-design-vue';

import { computed, ref, watch, useSlots } from 'vue';

import { ChevronDown, ChevronLeft, ChevronRight, LoaderCircle } from '@vben/icons';

import { Select, SelectOption, Skeleton, Tooltip } from 'ant-design-vue';
import { useDebounceFn } from '@vueuse/core';

// 选项类型
interface OptionItem {
  label: string;
  value: number | string;
  disabled?: boolean;
  extra?: Record<string, any> | null;
  [key: string]: any;
}

// API 响应类型
interface ApiResponse {
  items?: OptionItem[];
  total?: number;
  page?: number;
  page_size?: number;
  has_more?: boolean;
  [key: string]: any;
}

// 每页条数选项
const PAGE_SIZE_OPTIONS = [5, 10, 20, 50];

interface Props {
  /** 静态选项 */
  options?: OptionItem[];
  /** 远程 API 函数 */
  api?: (params: Record<string, any>) => Promise<ApiResponse | OptionItem[]>;
  /** API 额外参数 */
  params?: Record<string, any>;
  /** 从响应中提取 items 的字段路径 */
  resultField?: string;
  /** label 字段名 */
  labelField?: string;
  /** value 字段名 */
  valueField?: string;
  /** 选项右侧显示的字段路径，支持点表语法如 'extra.code' */
  optionRightField?: string;
  /** 是否立即加载 */
  immediate?: boolean;
  /** 是否启用分页 */
  pagination?: boolean;
  /** 是否显示点击分页控件 */
  clickPagination?: boolean;
  /** 每页数量 */
  pageSize?: number;
  /** 搜索参数名 */
  searchParamName?: string;
  /** 页码参数名 */
  pageParamName?: string;
  /** 每页数量参数名 */
  pageSizeParamName?: string;
  /** 搜索防抖延迟(ms) */
  debounceTime?: number;
  /** 是否显示每页条数选择器 */
  showSizeChanger?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  options: () => [],
  api: undefined,
  params: () => ({}),
  resultField: 'items',
  labelField: 'label',
  valueField: 'value',
  optionRightField: '',
  immediate: true,
  pagination: false,
  clickPagination: false,
  pageSize: 10,
  searchParamName: 'search',
  pageParamName: 'page',
  pageSizeParamName: 'page_size',
  debounceTime: 300,
  showSizeChanger: true,
});

const emit = defineEmits<{
  optionsLoaded: [OptionItem[]];
  'update:value': [number | string | undefined];
}>();

const slots = useSlots();

// v-model:value 兼容 Ant Design Vue 的 value 属性
const modelValue = defineModel<number | string | undefined>('value');

// 状态
const loading = ref(false);
const remoteOptions = ref<OptionItem[]>([]);
const currentPage = ref(1);
const currentPageSize = ref(props.pageSize);
const totalCount = ref(0);
const hasMore = ref(false);
const searchValue = ref('');
const isDropdownOpen = ref(false);
const isFirstLoad = ref(true);

// 计算总页数
const totalPages = computed(() => {
  if (totalCount.value === 0) return 1;
  return Math.ceil(totalCount.value / currentPageSize.value);
});

// 从对象中获取嵌套属性值，支持点表语法如 'extra.code'
function getNestedValue(obj: any, path: string): any {
  if (!path) return undefined;
  return path.split('.').reduce((acc, key) => acc?.[key], obj);
}

// 计算最终选项（保留完整原始数据）
const finalOptions = computed(() => {
  if (props.api) {
    return remoteOptions.value.map((item) => ({
      ...item, // 保留所有原始数据（包括 extra）
      label: item[props.labelField] as string,
      value: item[props.valueField] as number | string,
      disabled: item.disabled,
    }));
  }
  return props.options;
});

// 是否需要自定义渲染选项（有 optionRightField 或有 option 插槽）
const needCustomOption = computed(() => {
  return !!props.optionRightField || !!slots.option;
});

// 是否显示分页控件
const showPagination = computed(() => {
  return props.clickPagination && props.pagination && props.api;
});

// 上一页禁用状态
const isPrevDisabled = computed(() => loading.value || currentPage.value <= 1);

// 下一页禁用状态
const isNextDisabled = computed(() => loading.value || !hasMore.value);

// 从响应中提取数据
function extractItems(response: ApiResponse | OptionItem[]): OptionItem[] {
  if (Array.isArray(response)) {
    return response;
  }
  if (props.resultField && response[props.resultField]) {
    return response[props.resultField] as OptionItem[];
  }
  return [];
}

// 从响应中提取分页信息
function extractPaginationInfo(response: ApiResponse | OptionItem[], itemCount: number) {
  if (Array.isArray(response)) {
    hasMore.value = itemCount >= currentPageSize.value;
    totalCount.value = 0;
    return;
  }

  // 提取总数
  if (typeof response.total === 'number') {
    totalCount.value = response.total;
  }

  // 优先使用 has_more 字段
  if (typeof response.has_more === 'boolean') {
    hasMore.value = response.has_more;
    return;
  }

  // 使用 total/page/page_size 计算
  if (
    typeof response.total === 'number' &&
    typeof response.page === 'number' &&
    typeof response.page_size === 'number'
  ) {
    hasMore.value = response.page * response.page_size < response.total;
    return;
  }

  // 兖底：根据返回数量判断
  hasMore.value = itemCount >= currentPageSize.value;
}

// 加载数据
async function fetchData(page: number = 1, append: boolean = false, newPageSize?: number) {
  if (!props.api || loading.value) return;

  try {
    loading.value = true;

    const params: Record<string, any> = {
      ...props.params,
    };

    // 添加搜索参数
    if (searchValue.value) {
      params[props.searchParamName] = searchValue.value;
    }

    // 添加分页参数
    const pageSizeToUse = newPageSize ?? currentPageSize.value;
    if (props.pagination) {
      params[props.pageParamName] = page;
      params[props.pageSizeParamName] = pageSizeToUse;
    }

    const response = await props.api(params);
    const items = extractItems(response);

    // 处理分页信息
    if (props.pagination) {
      extractPaginationInfo(response, items.length);
      currentPage.value = page;
      if (newPageSize !== undefined) {
        currentPageSize.value = newPageSize;
      }
    }

    // 更新选项
    if (append && page > 1) {
      remoteOptions.value = [...remoteOptions.value, ...items];
    } else {
      remoteOptions.value = items;
    }

    emit('optionsLoaded', remoteOptions.value);
  } catch (error) {
    console.error('[ApiSelect] Failed to fetch data:', error);
  } finally {
    loading.value = false;
    isFirstLoad.value = false;
  }
}

// 防抖搜索
const debouncedSearch = useDebounceFn((value: string) => {
  searchValue.value = value;
  currentPage.value = 1;
  fetchData(1, false);
}, props.debounceTime);

// 搜索处理
function handleSearch(value: string) {
  debouncedSearch(value);
}

// 下拉框展开/关闭
function handleDropdownVisibleChange(open: boolean) {
  isDropdownOpen.value = open;
  if (open && props.api && remoteOptions.value.length === 0) {
    fetchData(1, false);
  }
}

// 上一页
function handlePrevPage(e: MouseEvent) {
  e.preventDefault();
  e.stopPropagation();
  if (isPrevDisabled.value) return;
  fetchData(currentPage.value - 1, false);
}

// 下一页
function handleNextPage(e: MouseEvent) {
  e.preventDefault();
  e.stopPropagation();
  if (isNextDisabled.value) return;
  fetchData(currentPage.value + 1, false);
}

// 每页条数变化
function handlePageSizeChange(size: number) {
  currentPageSize.value = size;
  currentPage.value = 1;
  fetchData(1, false, size);
}

// 滚动加载更多
function handlePopupScroll(e: Event) {
  if (!props.pagination || props.clickPagination || loading.value || !hasMore.value) return;

  const target = e.target as HTMLElement;
  if (!target) return;

  const nearBottom = target.scrollTop + target.clientHeight >= target.scrollHeight - 24;
  if (nearBottom) {
    fetchData(currentPage.value + 1, true);
  }
}

// 初始加载
watch(
  () => props.params,
  () => {
    if (props.api && props.immediate) {
      currentPage.value = 1;
      fetchData(1, false);
    }
  },
  { immediate: props.immediate, deep: true },
);

// 透传的 Select 属性
const selectProps = computed<SelectProps>(() => ({
  // 如果需要自定义渲染选项，不传 options，改用 SelectOption 子组件
  options: needCustomOption.value ? undefined : finalOptions.value,
  loading: loading.value,
  showSearch: true,
  filterOption: props.api ? false : undefined,
  onSearch: props.api ? handleSearch : undefined,
  onDropdownVisibleChange: handleDropdownVisibleChange,
  onPopupScroll: handlePopupScroll,
}));

defineExpose({
  /** 刷新数据 */
  refresh: () => fetchData(1, false),
  /** 获取当前选项 */
  getOptions: () => finalOptions.value,
});
</script>

<template>
  <Select
    v-model:value="modelValue"
    v-bind="{ ...$attrs, ...selectProps }"
  >
    <!-- 自定义选项渲染（当有 optionRightField 或 option 插槽时） -->
    <template v-if="needCustomOption">
      <SelectOption
        v-for="option in finalOptions"
        :key="option.value"
        :value="option.value"
        :disabled="option.disabled"
        :label="option.label"
      >
        <!-- 使用 option 插槽自定义渲染 -->
        <slot name="option" :option="option">
          <div class="api-select-option">
            <Tooltip :title="option.label" placement="topLeft" :mouse-enter-delay="0.5">
              <span class="api-select-option__label">{{ option.label }}</span>
            </Tooltip>
            <span v-if="optionRightField" class="api-select-option__right">
              {{ getNestedValue(option, optionRightField) }}
            </span>
          </div>
        </slot>
      </SelectOption>
    </template>

    <!-- 后缀图标：加载时显示旋转图标，否则显示下拉箭头 -->
    <template #suffixIcon>
      <LoaderCircle v-if="loading" class="api-select-loading-icon" />
      <slot v-else name="suffixIcon">
        <ChevronDown class="api-select-arrow-icon" />
      </slot>
    </template>

    <!-- 自定义下拉内容 -->
    <template #dropdownRender="{ menuNode }">
      <div class="api-select-dropdown">
        <!-- 骨架屏加载 -->
        <div v-if="loading && (isFirstLoad || clickPagination)" class="api-select-skeleton">
          <Skeleton
            v-for="i in 5"
            :key="i"
            :active="true"
            :title="false"
            :paragraph="{ rows: 1, width: '100%' }"
            class="api-select-skeleton__item"
          />
        </div>

        <!-- 原始菜单 -->
        <div v-show="!loading || (!isFirstLoad && !clickPagination)">
          <component :is="menuNode" />
        </div>

        <!-- 分页控件 -->
        <div v-if="showPagination" class="api-select-pagination">
          <!-- 左侧：总条数 + 每页条数 -->
          <div class="api-select-pagination__left">
            <span class="api-select-pagination__total">
              共 <b>{{ totalCount }}</b> 条
            </span>
            <Select
              v-if="showSizeChanger"
              :value="currentPageSize"
              :options="PAGE_SIZE_OPTIONS.map(s => ({ value: s, label: `${s} 条/页` }))"
              size="small"
              :bordered="true"
              :get-popup-container="(trigger: HTMLElement) => trigger.parentNode as HTMLElement"
              class="api-select-pagination__size"
              @change="(val: any) => handlePageSizeChange(val as number)"
              @mousedown.stop
              @click.stop
            />
          </div>

          <!-- 右侧：分页按钮 -->
          <div class="api-select-pagination__right">
            <button
              type="button"
              class="api-select-pagination__btn"
              :class="{ 'is-disabled': isPrevDisabled }"
              :disabled="isPrevDisabled"
              title="上一页"
              @mousedown="handlePrevPage"
            >
              <ChevronLeft class="api-select-pagination__icon" />
            </button>

            <span class="api-select-pagination__info">
              {{ currentPage }}<span class="api-select-pagination__sep">/</span>{{ totalPages }}
            </span>

            <button
              type="button"
              class="api-select-pagination__btn"
              :class="{ 'is-disabled': isNextDisabled }"
              :disabled="isNextDisabled"
              title="下一页"
              @mousedown="handleNextPage"
            >
              <ChevronRight class="api-select-pagination__icon" />
            </button>
          </div>
        </div>
      </div>
    </template>
  </Select>
</template>

<style scoped>
/* 加载图标旋转 */
.api-select-loading-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

/* 下拉容器 */
.api-select-dropdown {
  position: relative;
}

/* 骨架屏 */
.api-select-skeleton {
  padding: 8px 12px;
}

.api-select-skeleton__item {
  margin-bottom: 8px;
}

.api-select-skeleton__item:last-child {
  margin-bottom: 0;
}

.api-select-skeleton :deep(.ant-skeleton-paragraph) {
  margin: 0 !important;
}

.api-select-skeleton :deep(.ant-skeleton-paragraph > li) {
  height: 22px !important;
  border-radius: 4px;
}

/* 分页控件 - 使用 container query 支持窄屏自适应 */
.api-select-pagination {
  container-type: inline-size;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 6px 8px;
  padding: 6px 12px;
  border-top: 1px solid var(--ant-color-border);
  background: var(--ant-color-bg-elevated);
  font-size: 12px;
}

.api-select-pagination__left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.api-select-pagination__right {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.api-select-pagination__total {
  color: var(--ant-color-text-secondary);
  white-space: nowrap;
}

.api-select-pagination__total b {
  color: var(--ant-color-text);
  font-weight: 500;
}

.api-select-pagination__size {
  width: 88px;
}

.api-select-pagination__size :deep(.ant-select-selector) {
  font-size: 12px !important;
}

/* 窄屏时隐藏每页条数选择器，保留核心分页功能 */
@container (max-width: 200px) {
  .api-select-pagination__size {
    display: none;
  }
}

.api-select-pagination__btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  padding: 0;
  border: 1px solid var(--ant-color-border);
  border-radius: 4px;
  background: var(--ant-color-bg-container);
  color: var(--ant-color-text-secondary);
  cursor: pointer;
  transition: all 0.15s;
}

.api-select-pagination__btn:hover:not(.is-disabled) {
  border-color: var(--ant-color-primary);
  color: var(--ant-color-primary);
}

.api-select-pagination__btn.is-disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.api-select-pagination__icon {
  width: 14px;
  height: 14px;
}

.api-select-pagination__info {
  min-width: 36px;
  padding: 0 2px;
  font-size: 12px;
  text-align: center;
  color: var(--ant-color-text);
  white-space: nowrap;
}

.api-select-pagination__sep {
  color: var(--ant-color-text-quaternary);
  margin: 0 1px;
}

/* 下拉箭头图标 */
.api-select-arrow-icon {
  width: 12px;
  height: 12px;
  color: var(--ant-color-text-quaternary);
  transition: transform 0.3s;
}

/* 选项样式 */
.api-select-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: 8px;
}

.api-select-option__label {
  flex: 1;
  min-width: 0; /* 确保 flex 子元素可以收缩 */
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.api-select-option__right {
  flex-shrink: 0;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  color: var(--ant-color-text-secondary);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}
</style>
