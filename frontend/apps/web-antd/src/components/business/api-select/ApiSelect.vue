<script lang="ts" setup>
/**
 * ApiSelect - Remote Dropdown Select Component
 * ApiSelect - 远程下拉选择组件
 *
 * Features / 功能：
 * - Static options (options prop) / 支持静态选项
 * - Remote loading (api prop) / 支持远程加载
 * - Remote search (showSearch + filterOption: false) / 支持远程搜索
 * - Pagination (pagination prop) / 支持分页
 * - Click pagination (clickPagination prop) / 支持点击翻页
 * - Skeleton loading effect / 骨架屏加载效果
 * - Custom dropdown option rendering / 支持自定义下拉项渲染
 * - Custom selected value and multi-tag rendering / 支持已选值和多选 tag 富渲染
 * - Selected option cache across pagination and search / 支持翻页和搜索后的已选缓存
 */
import type { SelectProps } from 'ant-design-vue';

import { computed, ref, useSlots, watch } from 'vue';

import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  LoaderCircle,
} from '@vben/icons';

import { useDebounceFn } from '@vueuse/core';
import { Select, SelectOption, Skeleton, Tooltip } from 'ant-design-vue';

export interface OptionItem {
  disabled?: boolean;
  extra?: null | Record<string, unknown>;
  label: string;
  value: number | string;
  [key: string]: unknown;
}

type OptionSource = object;
type OptionValue = number | string;
type SelectModelValue = OptionValue | OptionValue[] | undefined;

interface ApiResponse {
  has_more?: boolean;
  items?: OptionSource[];
  page?: number;
  page_size?: number;
  total?: number;
  [key: string]: unknown;
}

interface Props {
  api?: (
    params: Record<string, unknown>,
  ) => Promise<ApiResponse | OptionSource[]>;
  clickPagination?: boolean;
  debounceTime?: number;
  immediate?: boolean;
  labelField?: string;
  optionRightField?: string;
  options?: OptionSource[];
  pageParamName?: string;
  pageSize?: number;
  pageSizeParamName?: string;
  pagination?: boolean;
  params?: Record<string, unknown>;
  resultField?: string;
  searchParamName?: string;
  selectedOptions?: OptionSource[];
  showSizeChanger?: boolean;
  valueField?: string;
}

const props = withDefaults(defineProps<Props>(), {
  options: () => [],
  selectedOptions: () => [],
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
  'update:value': [SelectModelValue];
}>();

const PAGE_SIZE_OPTIONS = [5, 10, 20, 50];
const slots = useSlots();
const modelValue = defineModel<SelectModelValue>('value');

const loading = ref(false);
const remoteOptions = ref<OptionItem[]>([]);
const cachedOptions = ref<Map<string, OptionItem>>(new Map());
const currentPage = ref(1);
const currentPageSize = ref(props.pageSize);
const totalCount = ref(0);
const hasMore = ref(false);
const searchValue = ref('');
const isDropdownOpen = ref(false);
const isFirstLoad = ref(true);

function normalizeOptionItem(item: OptionSource): OptionItem {
  const source = item as Record<string, unknown>;
  const labelCandidate = source[props.labelField];
  const valueCandidate = source[props.valueField];
  const fallbackLabel =
    typeof source.label === 'string' && source.label.trim() ? source.label : '';
  const disabled =
    typeof source.disabled === 'boolean' ? source.disabled : undefined;
  const label =
    typeof labelCandidate === 'string' && labelCandidate.trim()
      ? labelCandidate
      : fallbackLabel;
  let value: number | string = label || '';
  if (typeof source.value === 'number' || typeof source.value === 'string') {
    value = source.value;
  }
  if (
    typeof valueCandidate === 'number' ||
    typeof valueCandidate === 'string'
  ) {
    value = valueCandidate;
  }

  return {
    ...source,
    label: label || String(value ?? ''),
    value,
    disabled,
  };
}

function mergeOptions(sources: OptionItem[][]): OptionItem[] {
  const optionMap = new Map<string, OptionItem>();

  for (const source of sources) {
    for (const item of source) {
      const normalized = normalizeOptionItem(item);
      if (normalized.value === undefined || normalized.value === null) {
        continue;
      }
      optionMap.set(String(normalized.value), normalized);
    }
  }

  return [...optionMap.values()];
}

function getNestedValue(obj: Record<string, unknown>, path: string): unknown {
  if (!path) return undefined;

  let result: unknown = obj;
  for (const key of path.split('.')) {
    result = (result as Record<string, unknown>)?.[key];
  }
  return result;
}

function updateCachedOptions(options: OptionSource[]) {
  if (options.length === 0) return;

  const nextCache = new Map(cachedOptions.value);
  for (const item of options) {
    const normalized = normalizeOptionItem(item);
    if (normalized.value === undefined || normalized.value === null) {
      continue;
    }
    nextCache.set(String(normalized.value), normalized);
  }
  cachedOptions.value = nextCache;
}

function getOptionByValue(value: null | OptionValue | undefined) {
  if (value === undefined || value === null) {
    return undefined;
  }
  return cachedOptions.value.get(String(value));
}

function getModelValues(value: SelectModelValue): OptionValue[] {
  if (Array.isArray(value)) {
    return value.filter(
      (item): item is OptionValue =>
        typeof item === 'number' || typeof item === 'string',
    );
  }
  return typeof value === 'number' || typeof value === 'string' ? [value] : [];
}

function resolveSlotOption(source: unknown): OptionItem | undefined {
  if (!source || typeof source !== 'object') {
    return undefined;
  }

  const sourceRecord = source as Record<string, unknown>;
  const candidate =
    sourceRecord.option && typeof sourceRecord.option === 'object'
      ? (sourceRecord.option as Record<string, unknown>)
      : sourceRecord;

  const valueCandidate = candidate[props.valueField] ?? candidate.value;
  if (
    typeof valueCandidate === 'number' ||
    typeof valueCandidate === 'string'
  ) {
    const cached = getOptionByValue(valueCandidate);
    if (cached) {
      return cached;
    }
  }

  const normalized = normalizeOptionItem(candidate as OptionSource);
  if (
    typeof normalized.value !== 'number' &&
    typeof normalized.value !== 'string'
  ) {
    return undefined;
  }
  if (normalized.value !== undefined && normalized.value !== null) {
    updateCachedOptions([normalized]);
  }
  return normalized;
}

const totalPages = computed(() => {
  if (totalCount.value === 0) return 1;
  return Math.ceil(totalCount.value / currentPageSize.value);
});

const selectedCachedOptions = computed<OptionItem[]>(
  () =>
    getModelValues(modelValue.value)
      .map((value) => getOptionByValue(value))
      .filter(Boolean) as OptionItem[],
);

const finalOptions = computed<OptionItem[]>(() => {
  const localOptions = props.options.map((item) => normalizeOptionItem(item));
  const preloadedSelected = props.selectedOptions.map((item) =>
    normalizeOptionItem(item),
  );

  return mergeOptions([
    localOptions,
    preloadedSelected,
    selectedCachedOptions.value,
    remoteOptions.value,
  ]);
});

const needCustomOption = computed(() => {
  return !!props.optionRightField || !!slots.option;
});

const needCustomOptionLabel = computed(() => !!slots.optionLabel);
const needCustomTag = computed(() => !!slots.tag);

const showPagination = computed(() => {
  return props.clickPagination && props.pagination && props.api;
});

const isPrevDisabled = computed(() => loading.value || currentPage.value <= 1);
const isNextDisabled = computed(() => loading.value || !hasMore.value);

function extractItems(response: ApiResponse | OptionSource[]): OptionSource[] {
  if (Array.isArray(response)) {
    return response;
  }
  if (props.resultField && response[props.resultField]) {
    return response[props.resultField] as OptionSource[];
  }
  return [];
}

function extractPaginationInfo(
  response: ApiResponse | OptionSource[],
  itemCount: number,
) {
  if (Array.isArray(response)) {
    hasMore.value = itemCount >= currentPageSize.value;
    totalCount.value = 0;
    return;
  }

  if (typeof response.total === 'number') {
    totalCount.value = response.total;
  }

  if (typeof response.has_more === 'boolean') {
    hasMore.value = response.has_more;
    return;
  }

  if (
    typeof response.total === 'number' &&
    typeof response.page === 'number' &&
    typeof response.page_size === 'number'
  ) {
    hasMore.value = response.page * response.page_size < response.total;
    return;
  }

  hasMore.value = itemCount >= currentPageSize.value;
}

async function fetchData(
  page: number = 1,
  append: boolean = false,
  newPageSize?: number,
) {
  if (!props.api || loading.value) return;

  try {
    loading.value = true;

    const params: Record<string, unknown> = {
      ...props.params,
    };

    if (searchValue.value) {
      params[props.searchParamName] = searchValue.value;
    }

    const pageSizeToUse = newPageSize ?? currentPageSize.value;
    if (props.pagination) {
      params[props.pageParamName] = page;
      params[props.pageSizeParamName] = pageSizeToUse;
    }

    const response = await props.api(params);
    const items = extractItems(response).map((item) =>
      normalizeOptionItem(item),
    );

    if (props.pagination) {
      extractPaginationInfo(response, items.length);
      currentPage.value = page;
      if (newPageSize !== undefined) {
        currentPageSize.value = newPageSize;
      }
    }

    updateCachedOptions(items);
    remoteOptions.value =
      append && page > 1 ? mergeOptions([remoteOptions.value, items]) : items;

    emit('optionsLoaded', remoteOptions.value);
  } catch {
    // requestClient already owns request failure UX for remote select APIs
  } finally {
    loading.value = false;
    isFirstLoad.value = false;
  }
}

const debouncedSearch = useDebounceFn((value: string) => {
  searchValue.value = value;
  currentPage.value = 1;
  fetchData(1, false);
}, props.debounceTime);

function handleSearch(value: string) {
  debouncedSearch(value);
}

function handleDropdownVisibleChange(open: boolean) {
  isDropdownOpen.value = open;
  if (open && props.api && remoteOptions.value.length === 0) {
    fetchData(1, false);
  }
}

function handlePrevPage(e: MouseEvent) {
  e.preventDefault();
  e.stopPropagation();
  if (isPrevDisabled.value) return;
  fetchData(currentPage.value - 1, false);
}

function handleNextPage(e: MouseEvent) {
  e.preventDefault();
  e.stopPropagation();
  if (isNextDisabled.value) return;
  fetchData(currentPage.value + 1, false);
}

function handlePageSizeChange(size: number) {
  currentPageSize.value = size;
  currentPage.value = 1;
  fetchData(1, false, size);
}

function handlePopupScroll(e: Event) {
  if (
    !props.pagination ||
    props.clickPagination ||
    loading.value ||
    !hasMore.value
  ) {
    return;
  }

  const target = e.target as HTMLElement;
  if (!target) return;

  const nearBottom =
    target.scrollTop + target.clientHeight >= target.scrollHeight - 24;
  if (nearBottom) {
    fetchData(currentPage.value + 1, true);
  }
}

watch(
  () => props.options,
  (options) => {
    updateCachedOptions(options.map((item) => normalizeOptionItem(item)));
  },
  { immediate: true, deep: true },
);

watch(
  () => props.selectedOptions,
  (options) => {
    updateCachedOptions(options.map((item) => normalizeOptionItem(item)));
  },
  { immediate: true, deep: true },
);

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

const selectProps = computed<SelectProps>(() => ({
  options: needCustomOption.value ? undefined : finalOptions.value,
  loading: loading.value,
  showSearch: true,
  filterOption: props.api ? false : undefined,
  onSearch: props.api ? handleSearch : undefined,
  onDropdownVisibleChange: handleDropdownVisibleChange,
  onPopupScroll: handlePopupScroll,
}));

defineExpose({
  refresh: () => fetchData(1, false),
  getOptions: () => finalOptions.value,
});
</script>

<template>
  <Select v-model:value="modelValue" v-bind="{ ...$attrs, ...selectProps }">
    <template v-if="needCustomOption">
      <SelectOption
        v-for="option in finalOptions"
        :key="option.value"
        :value="option.value"
        :disabled="option.disabled"
        :label="option.label"
      >
        <slot name="option" :option="option">
          <div class="api-select-option">
            <Tooltip
              :title="option.label"
              placement="topLeft"
              :mouse-enter-delay="0.5"
            >
              <span class="api-select-option__label">{{ option.label }}</span>
            </Tooltip>
            <span v-if="optionRightField" class="api-select-option__right">
              {{ getNestedValue(option, optionRightField) }}
            </span>
          </div>
        </slot>
      </SelectOption>
    </template>

    <template v-if="needCustomOptionLabel" #optionLabel="slotProps">
      <slot
        name="optionLabel"
        :option="resolveSlotOption(slotProps)"
        :raw="slotProps"
      ></slot>
    </template>

    <template v-if="needCustomTag" #tagRender="tagProps">
      <slot
        name="tag"
        :option="resolveSlotOption(tagProps)"
        :raw="tagProps"
        :tag-props="tagProps"
      ></slot>
    </template>

    <template #suffixIcon>
      <LoaderCircle v-if="loading" class="api-select-loading-icon" />
      <slot v-else name="suffixIcon">
        <ChevronDown class="api-select-arrow-icon" />
      </slot>
    </template>

    <template #dropdownRender="{ menuNode }">
      <div class="api-select-dropdown">
        <div
          v-if="loading && (isFirstLoad || clickPagination)"
          class="api-select-skeleton"
        >
          <Skeleton
            v-for="i in 5"
            :key="i"
            :active="true"
            :title="false"
            :paragraph="{ rows: 1, width: '100%' }"
            class="api-select-skeleton__item"
          />
        </div>

        <div v-show="!loading || (!isFirstLoad && !clickPagination)">
          <component :is="menuNode" />
        </div>

        <div v-if="showPagination" class="api-select-pagination">
          <div class="api-select-pagination__left">
            <span class="api-select-pagination__total">
              {{ $t('shared.common.totalCount', { count: totalCount }) }}
            </span>
            <Select
              v-if="showSizeChanger"
              :value="currentPageSize"
              :options="
                PAGE_SIZE_OPTIONS.map((s) => ({
                  value: s,
                  label: `${s} ${$t('shared.common.page.perPage')}`,
                }))
              "
              size="small"
              :bordered="true"
              :get-popup-container="
                (trigger: HTMLElement) => trigger.parentNode as HTMLElement
              "
              class="api-select-pagination__size"
              @change="(val: unknown) => handlePageSizeChange(Number(val))"
              @mousedown.stop
              @click.stop
            />
          </div>

          <div class="api-select-pagination__right">
            <button
              type="button"
              class="api-select-pagination__btn"
              :class="{ 'is-disabled': isPrevDisabled }"
              :disabled="isPrevDisabled"
              :title="$t('shared.common.page.prev')"
              @mousedown="handlePrevPage"
            >
              <ChevronLeft class="api-select-pagination__icon" />
            </button>

            <span class="api-select-pagination__info">
              {{ currentPage }}<span class="api-select-pagination__sep">/</span
              >{{ totalPages }}
            </span>

            <button
              type="button"
              class="api-select-pagination__btn"
              :class="{ 'is-disabled': isNextDisabled }"
              :disabled="isNextDisabled"
              :title="$t('shared.common.page.next')"
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
@keyframes spin {
  from {
    transform: rotate(0deg);
  }

  to {
    transform: rotate(360deg);
  }
}

@container (max-width: 200px) {
  .api-select-pagination__size {
    display: none;
  }
}

.api-select-loading-icon {
  animation: spin 1s linear infinite;
}

.api-select-dropdown {
  position: relative;
}

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

.api-select-pagination {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 8px;
  align-items: center;
  justify-content: space-between;
  padding: 6px 12px;
  container-type: inline-size;
  font-size: 12px;
  background: var(--ant-color-bg-elevated);
  border-top: 1px solid var(--ant-color-border);
}

.api-select-pagination__left {
  display: flex;
  flex-shrink: 0;
  gap: 8px;
  align-items: center;
}

.api-select-pagination__right {
  display: flex;
  flex-shrink: 0;
  gap: 4px;
  align-items: center;
}

.api-select-pagination__total {
  color: var(--ant-color-text-secondary);
  white-space: nowrap;
}

.api-select-pagination__total b {
  font-weight: 500;
  color: var(--ant-color-text);
}

.api-select-pagination__size {
  width: 88px;
}

.api-select-pagination__size :deep(.ant-select-selector) {
  font-size: 12px !important;
}

.api-select-pagination__btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  padding: 0;
  color: var(--ant-color-text-secondary);
  cursor: pointer;
  background: var(--ant-color-bg-container);
  border: 1px solid var(--ant-color-border);
  border-radius: 4px;
  transition: all 0.15s;
}

.api-select-pagination__btn:hover:not(.is-disabled) {
  color: var(--ant-color-primary);
  border-color: var(--ant-color-primary);
}

.api-select-pagination__btn.is-disabled {
  cursor: not-allowed;
  opacity: 0.35;
}

.api-select-pagination__icon {
  width: 14px;
  height: 14px;
}

.api-select-pagination__info {
  min-width: 36px;
  padding: 0 2px;
  font-size: 12px;
  color: var(--ant-color-text);
  text-align: center;
  white-space: nowrap;
}

.api-select-pagination__sep {
  margin: 0 1px;
  color: var(--ant-color-text-quaternary);
}

.api-select-arrow-icon {
  width: 12px;
  height: 12px;
  color: var(--ant-color-text-quaternary);
  transition: transform 0.3s;
}

.api-select-option {
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.api-select-option__label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.api-select-option__right {
  flex-shrink: 0;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  color: var(--ant-color-text-secondary);
  white-space: nowrap;
}
</style>
