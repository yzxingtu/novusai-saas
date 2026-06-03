<script lang="ts" setup>
/**
 * Config form field: HTML string backed by TipTap (compact), no AI/upload.
 * 配置表单 HTML 字段：TipTap 紧凑模式，字符串存库。
 *
 * Form.Item 会对子树做注入/收集，导致 TipTap 的 ProseMirror 无法聚焦。
 * 使用 Form.ItemRest 隔离编辑器，与 ConfigImagePicker 一致。
 */
import type { JSONContent } from '@tiptap/core';

import { computed, nextTick, onMounted, ref, watch } from 'vue';

import { Form } from 'ant-design-vue';

import RichTextEditor from '#/components/business/rich-text-editor/RichTextEditor.vue';

defineOptions({ name: 'ConfigHtmlEditor', inheritAttrs: false });

const props = withDefaults(
  defineProps<{
    /** Ant Design Form / Form.Item 可能注入 */
    disabled?: boolean;
  }>(),
  { disabled: undefined },
);

const model = defineModel<string>({ default: '' });

const editorEditable = computed(() => props.disabled !== true);

const inner = ref<JSONContent | null>({
  type: 'doc',
  content: [{ type: 'paragraph' }],
});

const rteRef = ref<InstanceType<typeof RichTextEditor> | null>(null);
/** Avoid pushing setContent when the change came from the editor itself */
const lastEmittedHtml = ref('');

function pushHtmlToEditor(html: string) {
  nextTick(() => {
    rteRef.value?.setContent(html.trim() ? html : '<p></p>');
  });
}

onMounted(() => {
  lastEmittedHtml.value = model.value ?? '';
  pushHtmlToEditor(model.value ?? '');
});

watch(
  () => model.value,
  (value = '') => {
    if (value === lastEmittedHtml.value) return;
    lastEmittedHtml.value = value;
    pushHtmlToEditor(value);
  },
);

function onEditorChange(_json: JSONContent, html: string) {
  lastEmittedHtml.value = html;
  model.value = html;
}
</script>

<template>
  <div
    class="config-html-editor rounded-md border border-border"
    v-bind="$attrs"
  >
    <Form.ItemRest>
      <RichTextEditor
        ref="rteRef"
        v-model="inner"
        mode="compact"
        :toolbar="true"
        :ai="false"
        :upload="false"
        :editable="editorEditable"
        :min-height="220"
        @change="onEditorChange"
      />
    </Form.ItemRest>
  </div>
</template>

<style scoped>
/* 确保可编辑区可点、有足够命中高度（避免 Form 层样式影响） */
.config-html-editor :deep(.ProseMirror) {
  min-height: 200px;
  pointer-events: auto;
  caret-color: hsl(var(--foreground));
}

.config-html-editor :deep(.rte-compact .overflow-y-auto) {
  position: relative;
  z-index: 1;
}
</style>
