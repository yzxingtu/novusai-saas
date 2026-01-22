<script lang="ts" setup>
import type { Component } from 'vue';

import type { AnyPromiseFunction } from '@vben/types';

import { computed, h, nextTick, ref, unref, useAttrs, watch } from 'vue';

import { ChevronLeft, ChevronRight, LoaderCircle } from '@vben/icons';

import { cloneDeep, get, isEqual, isFunction } from '@vben-core/shared/utils';

import { objectOmit } from '@vueuse/core';

type OptionsItem = {
  [name: string]: any;
  children?: OptionsItem[];
  disabled?: boolean;
  label?: string;
  value?: string;
};

interface Props {
  /** 组件 */
  component: Component;
  /** 是否将value从数字转为string */
  numberToString?: boolean;
  /** 获取options数据的函数 */
  api?: (arg?: any) => Promise<OptionsItem[] | Record<string, any>>;
  /** 传递给api的参数 */
  params?: Record<string, any>;
  /** 从api返回的结果中提取options数组的字段名 */
  resultField?: string;
  /** label字段名 */
  labelField?: string;
  /** children字段名，需要层级数据的组件可用 */
  childrenField?: string;
  /** value字段名 */
  valueField?: string;
  /** disabled字段名 */
  disabledField?: string;
  /** 组件接收options数据的属性名 */
  optionsPropName?: string;
  /** 是否立即调用api */
  immediate?: boolean;
  /** 每次`visibleEvent`事件发生时都重新请求数据 */
  alwaysLoad?: boolean;
  /** 在api请求之前的回调函数 */
  beforeFetch?: AnyPromiseFunction<any, any>;
  /** 在api请求之后的回调函数 */
  afterFetch?: AnyPromiseFunction<any, any>;
  /** 直接传入选项数据，也作为api返回空数据时的后备数据 */
  options?: OptionsItem[];
  /** 组件的插槽名称，用来显示一个"加载中"的图标 */
  loadingSlot?: string;
  /** 触发api请求的事件名 */
  visibleEvent?: string;
  /** 组件的v-model属性名，默认为modelValue。部分组件可能为value */
  modelPropName?: string;
  /**
   * 自动选择
   * - `first`：自动选择第一个选项
   * - `last`：自动选择最后一个选项
   * - `one`: 当请求的结果只有一个选项时，自动选择该选项
   * - 函数：自定义选择逻辑，函数的参数为请求的结果数组，返回值为选择的选项
   * - false：不自动选择(默认)
   */
  autoSelect?:
    | 'first'
    | 'last'
    | 'one'
    | ((item: OptionsItem[]) => OptionsItem)
    | false;
  /** 搜索参数名（远程搜索） */
  searchParamName?: string;
  /** 是否启用分页（下拉滚动加载更多） */
  pagination?: boolean;
  /** 是否启用点击翻页（在下拉底部渲染加载更多/上一页-下一页） */
  clickPagination?: boolean;
  /** 点击翻页模式：'load-more' 或 'prev-next' */
  pagerMode?: 'load-more' | 'prev-next';
  /** 分页参数名 */
  pageParamName?: string;
  /** 分页大小参数名 */
  pageSizeParamName?: string;
  /** 每页数量 */
  pageSize?: number;
  /** 是否还有更多数据字段名（从响应中解析） */
  hasMoreField?: string;
  /** 总数字段名（用于兜底计算 hasMore） */
  totalField?: string;
  /** 当前页字段名（用于兜底计算 hasMore） */
  pageFieldInResponse?: string;
  /** 每页数量字段名（用于兜底计算 hasMore） */
  pageSizeFieldInResponse?: string;
}

defineOptions({ name: 'ApiComponent', inheritAttrs: false });

const props = withDefaults(defineProps<Props>(), {
  labelField: 'label',
  valueField: 'value',
  disabledField: 'disabled',
  childrenField: '',
  optionsPropName: 'options',
  resultField: '',
  visibleEvent: '',
  numberToString: false,
  params: () => ({}),
  immediate: true,
  alwaysLoad: false,
  loadingSlot: '',
  beforeFetch: undefined,
  afterFetch: undefined,
  modelPropName: 'modelValue',
  api: undefined,
  autoSelect: false,
  options: () => [],
  searchParamName: 'search',
  pagination: false,
  pageParamName: 'page',
  pageSizeParamName: 'page_size',
  pageSize: 10,
  hasMoreField: 'has_more',
  clickPagination: false,
  pagerMode: 'load-more',
  totalField: 'total',
  pageFieldInResponse: 'page',
  pageSizeFieldInResponse: 'page_size',
});

const emit = defineEmits<{
  optionsChange: [OptionsItem[]];
}>();

const modelValue = defineModel<any>({ default: undefined });

const attrs = useAttrs();
const innerParams = ref<Record<string, any>>({});
const refOptions = ref<OptionsItem[]>([]);
const loading = ref(false);
// 首次是否加载过了
const isFirstLoaded = ref(false);
// 标记是否有待处理的请求
const hasPendingRequest = ref(false);
// 分页状态
const currentPage = ref(1);
const hasMore = ref(false);

const getOptions = computed(() => {
  const {
    labelField,
    valueField,
    disabledField,
    childrenField,
    numberToString,
  } = props;

  const refOptionsData = unref(refOptions);

  function transformData(data: OptionsItem[]): OptionsItem[] {
    return data.map((item) => {
      const value = get(item, valueField);
      const result: OptionsItem = {
        label: get(item, labelField),
        value: numberToString ? `${value}` : value,
        disabled: get(item, disabledField),
      };

      // 只有在有 children 时才添加 children 字段
      if (childrenField && item[childrenField]) {
        result.children = transformData(item[childrenField]);
      }

      return result;
    });
  }

  const data: OptionsItem[] = transformData(refOptionsData);

  return data.length > 0 ? data : props.options;
});

const bindProps = computed(() => {
  // 保留用户自定义 onSearch/onPopupScroll
  const userOnSearch = (attrs as any)?.onSearch as
    | ((val: string) => void)
    | undefined;
  const userOnPopupScroll = (attrs as any)?.onPopupScroll as
    | ((e: any) => void)
    | undefined;

  // 构建带分页的下拉渲染函数
  const buildDropdownRender = (menu: any) => {
    const isPrevDisabled = loading.value || unref(currentPage) <= 1;
    const isNextDisabled = loading.value || !unref(hasMore);
    const pageText = loading.value ? '...' : String(unref(currentPage) || 1);

    const handlePrev = (e: Event) => {
      e.preventDefault();
      e.stopPropagation();
      if (isPrevDisabled) return;
      const prev = Math.max(1, (unref(currentPage) || 1) - 1);
      currentPage.value = prev;
      innerParams.value = {
        ...unref(innerParams),
        [props.pageParamName!]: prev,
        [props.pageSizeParamName!]: props.pageSize,
      };
    };

    const handleNext = (e: Event) => {
      e.preventDefault();
      e.stopPropagation();
      if (isNextDisabled) return;
      const next = (unref(currentPage) || 1) + 1;
      currentPage.value = next;
      innerParams.value = {
        ...unref(innerParams),
        [props.pageParamName!]: next,
        [props.pageSizeParamName!]: props.pageSize,
      };
    };

    // 分页控制栏
    const pager = h(
      'div',
      {
        style: {
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '4px',
          padding: '6px 8px',
          borderTop: '1px solid #d9d9d9',
        },
      },
      [
        h(
          'button',
          {
            type: 'button',
            disabled: isPrevDisabled,
            style: {
              padding: '4px',
              cursor: isPrevDisabled ? 'not-allowed' : 'pointer',
              opacity: isPrevDisabled ? '0.4' : '1',
              border: 'none',
              background: 'transparent',
              display: 'flex',
              alignItems: 'center',
            },
            title: '上一页',
            onMousedown: handlePrev,
          },
          [h(ChevronLeft, { style: { width: '16px', height: '16px' } })],
        ),
        h(
          'span',
          {
            style: {
              fontSize: '12px',
              color: '#999',
              minWidth: '2rem',
              textAlign: 'center',
            },
          },
          pageText,
        ),
        h(
          'button',
          {
            type: 'button',
            disabled: isNextDisabled,
            style: {
              padding: '4px',
              cursor: isNextDisabled ? 'not-allowed' : 'pointer',
              opacity: isNextDisabled ? '0.4' : '1',
              border: 'none',
              background: 'transparent',
              display: 'flex',
              alignItems: 'center',
            },
            title: '下一页',
            onMousedown: handleNext,
          },
          [h(ChevronRight, { style: { width: '16px', height: '16px' } })],
        ),
      ],
    );

    // 返回包含原始菜单和分页器的容器
    // 注意：在 Vue 3 中，h() 第三个参数可以是数组或对象
    return h('div', null, [menu, pager]);
  };

  const finalOptions = unref(getOptions);

  return {
    [props.modelPropName]: unref(modelValue),
    [props.optionsPropName]: finalOptions,
    [`onUpdate:${props.modelPropName}`]: (val: string) => {
      modelValue.value = val;
    },
    // 远程搜索：拦截 onSearch 更新内部参数（并透传给用户回调）
    onSearch: (val: string) => {
      if (props.searchParamName) {
        // 重置到第 1 页
        currentPage.value = props.pagination ? 1 : 0;
        innerParams.value = {
          ...unref(innerParams),
          [props.searchParamName]: val,
          ...(props.pagination
            ? {
                [props.pageParamName]: 1,
                [props.pageSizeParamName]: props.pageSize,
              }
            : {}),
        };
      }
      userOnSearch?.(val);
    },
    // 下拉滚动加载更多
    onPopupScroll: (e: any) => {
      if (!props.pagination) return userOnPopupScroll?.(e);
      const target = e?.target as HTMLElement | undefined;
      if (!target || loading.value) return userOnPopupScroll?.(e);
      const nearBottom =
        target.scrollTop + target.clientHeight >= target.scrollHeight - 24;
      if (nearBottom && unref(hasMore)) {
        const nextPage = (unref(currentPage) || 1) + 1;
        currentPage.value = nextPage;
        innerParams.value = {
          ...unref(innerParams),
          [props.pageParamName]: nextPage,
          [props.pageSizeParamName]: props.pageSize,
        };
      }
      userOnPopupScroll?.(e);
    },
    ...(props.clickPagination
      ? { dropdownRender: (origin: any) => buildDropdownRender(origin) }
      : {}),
    ...objectOmit(attrs, [
      `onUpdate:${props.modelPropName}`,
      'onSearch',
      'onPopupScroll',
      'dropdownRender',
    ]),
    ...(props.visibleEvent
      ? {
          [props.visibleEvent]: handleFetchForVisible,
        }
      : {}),
  };
});

async function fetchApi() {
  const { api, beforeFetch, afterFetch, resultField } = props;

  if (!api || !isFunction(api)) {
    return;
  }

  // 如果正在加载，标记有待处理的请求并返回
  if (loading.value) {
    hasPendingRequest.value = true;
    return;
  }

  try {
    loading.value = true;
    let finalParams = unref(mergedParams);
    if (beforeFetch && isFunction(beforeFetch)) {
      finalParams = (await beforeFetch(cloneDeep(finalParams))) || finalParams;
    }
    const isAppend =
      !!props.pagination && (finalParams?.[props.pageParamName!] ?? 1) > 1;
    let res = await api(finalParams);
    if (afterFetch && isFunction(afterFetch)) {
      res = (await afterFetch(res)) || res;
    }
    isFirstLoaded.value = true;

    let items: OptionsItem[] = [];
    if (Array.isArray(res)) {
      items = res as OptionsItem[];
    } else if (resultField) {
      items = (get(res as any, resultField) as OptionsItem[]) || [];
    }

    // 处理 hasMore（优先 hasMoreField，其次用 total/page/page_size 推导）
    if (props.pagination) {
      const total = (res as any)?.[props.totalField!];
      const respPage = (res as any)?.[props.pageFieldInResponse!];
      const respPageSize = (res as any)?.[props.pageSizeFieldInResponse!];
      const hm = (res as any)?.[props.hasMoreField!];
      if (typeof hm === 'boolean') {
        hasMore.value = hm;
      } else if (
        typeof total === 'number' &&
        typeof respPage === 'number' &&
        typeof respPageSize === 'number'
      ) {
        hasMore.value = respPage * respPageSize < total;
      } else {
        hasMore.value =
          items?.length >=
          (finalParams?.[props.pageSizeParamName!] ?? props.pageSize);
      }
    } else {
      hasMore.value = false;
    }

    // 合并或替换选项
    refOptions.value = isAppend
      ? [...unref(refOptions), ...(items || [])]
      : items || [];

    emitChange();
  } catch (error) {
    console.warn(error);
    // reset status
    isFirstLoaded.value = false;
  } finally {
    loading.value = false;
    // 如果有待处理的请求，立即触发新的请求
    if (hasPendingRequest.value) {
      hasPendingRequest.value = false;
      // 使用 nextTick 确保状态更新完成后再触发新请求
      await nextTick();
      fetchApi();
    }
  }
}

async function handleFetchForVisible(visible: boolean) {
  if (visible) {
    // 首次展开时，重置分页
    if (props.pagination) {
      currentPage.value = 1;
      innerParams.value = {
        ...unref(innerParams),
        [props.pageParamName!]: 1,
        [props.pageSizeParamName!]: props.pageSize,
      };
    }
    if (props.alwaysLoad) {
      await fetchApi();
    } else if (!props.immediate && !unref(isFirstLoaded)) {
      await fetchApi();
    }
  }
}

const mergedParams = computed(() => {
  return {
    ...props.params,
    ...unref(innerParams),
  };
});

watch(
  mergedParams,
  (value, oldValue) => {
    if (isEqual(value, oldValue)) {
      return;
    }
    fetchApi();
  },
  { deep: true, immediate: props.immediate },
);

function emitChange() {
  if (
    modelValue.value === undefined &&
    props.autoSelect &&
    unref(getOptions).length > 0
  ) {
    let firstOption;
    if (isFunction(props.autoSelect)) {
      firstOption = props.autoSelect(unref(getOptions));
    } else {
      switch (props.autoSelect) {
        case 'first': {
          firstOption = unref(getOptions)[0];
          break;
        }
        case 'last': {
          firstOption = unref(getOptions)[unref(getOptions).length - 1];
          break;
        }
        case 'one': {
          if (unref(getOptions).length === 1) {
            firstOption = unref(getOptions)[0];
          }
          break;
        }
      }
    }

    if (firstOption) modelValue.value = firstOption.value;
  }
  emit('optionsChange', unref(getOptions));
}
const componentRef = ref();
defineExpose({
  /** 获取options数据 */
  getOptions: () => unref(getOptions),
  /** 获取当前值 */
  getValue: () => unref(modelValue),
  /** 获取被包装的组件实例 */
  getComponentRef: <T = any,>() => componentRef.value as T,
  /** 更新Api参数 */
  updateParam(newParams: Record<string, any>) {
    innerParams.value = newParams;
  },
});
</script>
<template>
  <component
    :is="component"
    v-bind="bindProps"
    :placeholder="$attrs.placeholder"
    ref="componentRef"
  >
    <template v-for="item in Object.keys($slots)" #[item]="data">
      <slot :name="item" v-bind="data || {}"></slot>
    </template>
    <template v-if="loadingSlot && loading" #[loadingSlot]>
      <LoaderCircle class="animate-spin" />
    </template>
  </component>
</template>
