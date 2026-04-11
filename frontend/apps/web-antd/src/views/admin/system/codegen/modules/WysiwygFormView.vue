<script lang="ts" setup>
/**
 * WYSIWYG 新建表单预览 / WYSIWYG Form View
 *
 * 使用直接 Ant Design 组件渲染，支持密码掩码、字段点击选中、多列布局。
 * 表单可编辑、可提交，提交后弹窗显示 JSON。
 */
import { provide } from 'vue';

import { Modal } from 'ant-design-vue';

import { $t } from '#/locales';

import WysiwygFormBody from './WysiwygFormBody.vue';
import WysiwygFormHeader from './WysiwygFormHeader.vue';
import { useWysiwygFormPreview } from './useWysiwygFormPreview';
import { wysiwygFormContextKey } from './wysiwyg-form-context';

defineOptions({ name: 'WysiwygFormView' });

const preview = useWysiwygFormPreview();
const { submitResultJson, submitResultVisible } = preview;
provide(wysiwygFormContextKey, preview);
</script>

<template>
  <div
    class="overflow-hidden rounded-[24px] border border-border/70 bg-card shadow-sm"
  >
    <WysiwygFormHeader />
    <WysiwygFormBody />

    <Modal
      v-model:open="submitResultVisible"
      :title="$t('admin.system.codegen.preview.submitData')"
      :footer="null"
      width="560"
    >
      <pre
        class="max-h-[400px] overflow-auto rounded bg-muted/30 p-3 text-xs"
        >{{ submitResultJson }}</pre
      >
    </Modal>
  </div>
</template>
