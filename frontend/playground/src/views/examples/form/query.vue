<script lang="ts" setup>
import { Page } from '@vben/common-ui';

import { Card, message } from 'ant-design-vue';

import { useVbenForm } from '#/adapter/form';

const [QueryForm] = useVbenForm({
  // 默认展开 / Expanded by default
  collapsed: false,
  // 所有表单项共用，可单独在表单内覆盖 / Shared defaults; override per field
  commonConfig: {
    // 所有表单项 / All fields
    componentProps: {
      class: 'w-full',
    },
  },
  // 提交函数 / Submit handler
  handleSubmit: onSubmit,
  // 垂直布局：label 与 input 分行 / vertical layout
  // 水平布局：label 与 input 同行 / horizontal layout
  layout: 'horizontal',
  schema: [
    {
      // 组件需要在 #/adapter.ts 内注册并声明类型 / Register in adapter + types
      component: 'Input',
      // 对应组件的参数 / Props for the component
      componentProps: {
        placeholder: '请输入用户名',
      },
      // 字段名 / fieldName
      fieldName: 'username',
      // 界面显示的 label / Visible label
      label: '字符串',
    },
    {
      component: 'InputPassword',
      componentProps: {
        placeholder: '请输入密码',
      },
      fieldName: 'password',
      label: '密码',
    },
    {
      component: 'InputNumber',
      componentProps: {
        placeholder: '请输入',
      },
      fieldName: 'number',
      label: '数字(带后缀)',
      suffix: () => '¥',
    },
    {
      component: 'Select',
      componentProps: {
        allowClear: true,
        filterOption: true,
        options: [
          {
            label: '选项1',
            value: '1',
          },
          {
            label: '选项2',
            value: '2',
          },
        ],
        placeholder: '请选择',
        showSearch: true,
      },
      fieldName: 'options',
      label: '下拉选',
    },
    {
      component: 'DatePicker',
      fieldName: 'datePicker',
      label: '日期选择框',
    },
  ],
  // 是否可展开 / Collapse toggle
  showCollapseButton: true,
  submitButtonOptions: {
    content: '查询',
  },
  // 大屏 3 列、中屏 2 列、小屏 1 列 / Responsive grid columns
  wrapperClass: 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3',
});

const [InlineForm] = useVbenForm({
  layout: 'inline',
  schema: [
    {
      // 组件需要在 #/adapter.ts 内注册并声明类型 / Register in adapter + types
      component: 'Input',
      // 对应组件的参数 / Props for the component
      componentProps: {
        placeholder: '请输入用户名',
      },
      // 字段名 / fieldName
      fieldName: 'username',
      // 界面显示的 label / Visible label
      label: '字符串',
    },
    {
      component: 'InputPassword',
      componentProps: {
        placeholder: '请输入密码',
      },
      fieldName: 'password',
      label: '密码',
    },
    {
      component: 'InputNumber',
      componentProps: {
        placeholder: '请输入',
      },
      fieldName: 'number',
      label: '数字(带后缀)',
      suffix: () => '¥',
    },
    {
      component: 'Select',
      componentProps: {
        allowClear: true,
        filterOption: true,
        options: [
          {
            label: '选项1',
            value: '1',
          },
          {
            label: '选项2',
            value: '2',
          },
        ],
        placeholder: '请选择',
        showSearch: true,
      },
      fieldName: 'options',
      label: '下拉选',
    },
  ],
});

const [QueryForm1] = useVbenForm({
  // 默认展开 / Expanded by default
  collapsed: true,
  collapsedRows: 2,
  // 所有表单项共用，可单独在表单内覆盖 / Shared defaults; override per field
  commonConfig: {
    // 所有表单项 / All fields
    componentProps: {
      class: 'w-full',
    },
  },
  // 提交函数 / Submit handler
  handleSubmit: onSubmit,
  // 垂直布局：label 与 input 分行 / vertical layout
  // 水平布局：label 与 input 同行 / horizontal layout
  layout: 'horizontal',
  schema: (() => {
    const schema = [];
    for (let index = 0; index < 14; index++) {
      schema.push({
        // 组件需要在 #/adapter.ts 内注册并声明类型 / Register in adapter + types
        component: 'Input',
        // 字段名 / fieldName
        fieldName: `field${index}`,
        // 界面显示的 label / Visible label
        label: `字段${index}`,
      });
    }
    return schema;
  })(),
  // 是否可展开 / Collapse toggle
  showCollapseButton: true,
  submitButtonOptions: {
    content: '查询',
  },
  // 大屏 3 列、中屏 2 列、小屏 1 列 / Responsive grid columns
  wrapperClass: 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3',
});

const [QueryForm2] = useVbenForm({
  // 操作按钮组：newLine 新行；rowEnd 行尾右对齐；inline grid 默认 / Action bar layout
  actionLayout: 'newLine',
  actionPosition: 'left', // 操作按钮组在左侧显示 / Actions on the left
  // 默认折叠 / Collapsed by default
  collapsed: true,
  collapsedRows: 3,
  // 所有表单项共用，可单独在表单内覆盖 / Shared defaults; override per field
  commonConfig: {
    // 所有表单项 / All fields
    componentProps: {
      class: 'w-full',
    },
  },
  // 提交函数 / Submit handler
  handleSubmit: onSubmit,
  // 垂直布局：label 与 input 分行 / vertical layout
  // 水平布局：label 与 input 同行 / horizontal layout
  layout: 'vertical',
  schema: [
    {
      // 组件需要在 #/adapter.ts 内注册并声明类型 / Register in adapter + types
      component: 'Input',
      // 对应组件的参数 / Props for the component
      componentProps: {
        placeholder: '请输入用户名',
      },
      // 字段名 / fieldName
      fieldName: 'username',
      // 界面显示的 label / Visible label
      label: '字符串',
    },
    {
      component: 'InputPassword',
      componentProps: {
        placeholder: '请输入密码',
      },
      fieldName: 'password',
      label: '密码',
    },
    {
      component: 'InputNumber',
      componentProps: {
        placeholder: '请输入',
      },
      fieldName: 'number',
      label: '数字(带后缀)',
      suffix: () => '¥',
    },
    {
      component: 'DatePicker',
      fieldName: 'datePicker',
      label: '日期选择框',
    },
  ],
  // 是否可展开 / Collapse toggle
  showCollapseButton: true,
  submitButtonOptions: {
    content: '查询',
  },
  // 大屏 3 列、中屏 2 列、小屏 1 列 / Responsive grid columns
  wrapperClass: 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3',
});

function onSubmit(values: Record<string, any>) {
  message.success({
    content: `form values: ${JSON.stringify(values)}`,
  });
}
</script>

<template>
  <Page
    description="查询表单，常用语和表格组合使用，可进行收缩展开。"
    title="表单组件"
  >
    <Card class="mb-5" title="查询表单，默认展开">
      <QueryForm />
    </Card>

    <Card class="mb-5" title="查询表单，单行表单">
      <InlineForm />
    </Card>

    <Card class="mb-5" title="查询表单，默认展开，垂直布局">
      <QueryForm2 />
    </Card>

    <Card title="查询表单，默认折叠，折叠时保留2行">
      <QueryForm1 />
    </Card>
  </Page>
</template>
