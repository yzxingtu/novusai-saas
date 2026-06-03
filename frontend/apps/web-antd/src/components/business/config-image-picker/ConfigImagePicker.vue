/** * Config Image Picker * 配置项图片选择器 * * Used with ConfigForm, provides
image selection for config items with value_type='image'. * 配合 ConfigForm
使用，在系统配置中为 value_type='image' 的配置项提供图片选择功能。 * Selects
images via FilePicker attachment manager modal, stores attachment ID (string), *
通过 FilePicker 附件管理器弹窗选择图片，存储附件 ID（字符串）， * dynamically
constructs image processing URL from ID for display. * 显示时根据 ID
动态拼接图片处理 URL。 * * @example *
<ConfigImagePicker v-model="formModel[cfg.key]" />
*
<ConfigImagePicker v-model="value" accept="image/png,image/jpeg" />
*/
<script setup lang="ts">
import type { AttachmentInfo } from '#/types/attachment';

import { computed, ref } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Button, Form, Image } from 'ant-design-vue';

import { FilePicker } from '#/components/business/file-picker';
import { $t } from '#/locales';
import { toAttachmentImageUrl } from '#/utils/image';

const props = withDefaults(
  defineProps<{
    /** Allowed file types, passed to FilePicker's accept (e.g. 'image/*', 'image/png') / 允许的文件类型，传给 FilePicker 的 accept（如 'image/*', 'image/png'） */
    accept?: string;
    /** Whether to show only image type files / 是否仅显示图片类型文件 */
    imageOnly?: boolean;
    /** Current value: canonical attachment ID / 当前值：规范附件 ID */
    modelValue?: string;
  }>(),
  {
    accept: 'image/*',
    imageOnly: true,
    modelValue: '',
  },
);

const emit = defineEmits<{ (e: 'update:modelValue', v: string): void }>();

const filePickerRef = ref<InstanceType<typeof FilePicker>>();
const previewVisible = ref(false);

const thumbnailUrl = computed(() =>
  toAttachmentImageUrl(props.modelValue, { preset: 'medium' }),
);
const previewUrl = computed(() => toAttachmentImageUrl(props.modelValue));

/** Open attachment manager modal / 打开附件管理器弹窗 */
function openPicker() {
  filePickerRef.value?.open();
}

/** After selecting a file, emit attachment ID (string) via v-model / 选择文件后，将附件 ID（字符串）通过 v-model 传出 */
function handleSelect(files: AttachmentInfo[]) {
  if (files.length > 0) {
    const file = files[0]!;
    emit('update:modelValue', String(file.id));
  }
}

/** Remove selected image, clear value / 移除已选图片，清空值 */
function handleRemove() {
  emit('update:modelValue', '');
}
</script>

<template>
  <div class="flex items-start gap-3">
    <!-- Selected image preview card / 已选图片预览卡片 -->
    <div
      v-if="thumbnailUrl"
      class="group relative size-[120px] overflow-hidden rounded-lg border border-border"
    >
      <img
        :src="thumbnailUrl"
        :alt="$t('shared.common.preview')"
        class="size-full cursor-pointer object-contain"
        @click="previewVisible = true"
      />
      <!-- Hover overlay: zoom / delete buttons / hover 遮罩：放大 / 删除按钮 -->
      <div
        class="absolute inset-0 flex items-center justify-center gap-2 bg-black/40 opacity-0 transition-opacity duration-200 group-hover:opacity-100"
      >
        <Button
          type="text"
          size="small"
          class="!size-8 !min-w-0 !rounded-full !bg-white/20 !text-white hover:!bg-white/40"
          @click="previewVisible = true"
        >
          <IconifyIcon icon="lucide:zoom-in" class="text-sm" />
        </Button>
        <Button
          type="text"
          size="small"
          class="!size-8 !min-w-0 !rounded-full !bg-white/20 !text-white hover:!bg-white/40"
          @click="handleRemove"
        >
          <IconifyIcon icon="lucide:trash-2" class="text-sm" />
        </Button>
      </div>
    </div>

    <!-- Select / change button / 选择 / 更换按钮 -->
    <Button @click="openPicker">
      <template #icon>
        <IconifyIcon icon="lucide:image-plus" />
      </template>
      {{
        thumbnailUrl ? $t('shared.common.change') : $t('shared.common.select')
      }}
    </Button>

    <!--
      Wrap FilePicker and Image with Form.ItemRest,
      prevents Ant Design Form.Item from mistakenly collecting internal form controls (Upload/Input) causing warnings
      用 Form.ItemRest 包裹 FilePicker 和 Image，
      防止 Ant Design Form.Item 误收集内部表单控件（Upload/Input）导致警告
    -->
    <Form.ItemRest>
      <FilePicker
        ref="filePickerRef"
        :accept="accept"
        :image-only="imageOnly"
        visibility="public"
        @select="handleSelect"
      />

      <!-- Hidden Image component, only used to control antd image preview modal / 隐藏的 Image 组件，仅用于控制 antd 图片预览弹窗 -->
      <Image
        v-if="previewUrl"
        :src="previewUrl"
        :preview="{
          visible: previewVisible,
          onVisibleChange: (v: boolean) => (previewVisible = v),
        }"
        class="hidden"
      />
    </Form.ItemRest>
  </div>
</template>
