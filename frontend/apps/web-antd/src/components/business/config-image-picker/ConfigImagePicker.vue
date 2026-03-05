/** * 配置项图片选择器 * * 配合 ConfigForm 使用，在系统配置中为
value_type='image' 的配置项提供图片选择功能。 * 通过 FilePicker
附件管理器弹窗选择图片，存储附件 ID（字符串）， * 显示时根据 ID 动态拼接图片处理
URL。 * * @example *
<ConfigImagePicker v-model="formModel[cfg.key]" />
*
<ConfigImagePicker v-model="value" accept="image/png,image/jpeg" />
*/
<script setup lang="ts">
import type { AttachmentInfo } from '#/types/attachment';

import { ref } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Button, Form, Image } from 'ant-design-vue';

import { FilePicker } from '#/components/business/file-picker';
import { $t } from '#/locales';
import { getProcessedImageUrl } from '#/utils/image';

withDefaults(
  defineProps<{
    /** 允许的文件类型，传给 FilePicker 的 accept（如 'image/*', 'image/png'） */
    accept?: string;
    /** 是否仅显示图片类型文件 */
    imageOnly?: boolean;
    /** 当前值：附件 ID（字符串形式），也兼容旧的 URL 格式 */
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

/**
 * 将存储的附件 ID 转换为缩略图 URL（用于列表/卡片预览）
 * 如果值是旧格式的完整 URL，直接返回
 */
function toDisplayUrl(val: string | undefined): string {
  if (!val) return '';
  const id = Number(val);
  if (Number.isFinite(id) && id > 0) {
    return getProcessedImageUrl(id, { preset: 'medium' });
  }
  // 兼容旧的 URL 格式
  return val;
}

/**
 * 将存储的附件 ID 转换为原图 URL（用于放大镜查看大图）
 * 不传 preset 参数，返回原始尺寸图片
 */
function toPreviewUrl(val: string | undefined): string {
  if (!val) return '';
  const id = Number(val);
  if (Number.isFinite(id) && id > 0) {
    return getProcessedImageUrl(id);
  }
  return val;
}

/** 打开附件管理器弹窗 */
function openPicker() {
  filePickerRef.value?.open();
}

/** 选择文件后，将附件 ID（字符串）通过 v-model 传出 */
function handleSelect(files: AttachmentInfo[]) {
  if (files.length > 0) {
    const file = files[0]!;
    emit('update:modelValue', String(file.id));
  }
}

/** 移除已选图片，清空值 */
function handleRemove() {
  emit('update:modelValue', '');
}
</script>

<template>
  <div class="flex items-start gap-3">
    <!-- 已选图片预览卡片 -->
    <div
      v-if="modelValue"
      class="group relative size-[120px] overflow-hidden rounded-lg border border-border"
    >
      <img
        :src="toDisplayUrl(modelValue)"
        :alt="$t('shared.common.preview')"
        class="size-full cursor-pointer object-contain"
        @click="previewVisible = true"
      />
      <!-- hover 遮罩：放大 / 删除按钮 -->
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

    <!-- 选择 / 更换按钮 -->
    <Button @click="openPicker">
      <template #icon>
        <IconifyIcon icon="lucide:image-plus" />
      </template>
      {{ modelValue ? $t('shared.common.change') : $t('shared.common.select') }}
    </Button>

    <!--
      用 Form.ItemRest 包裹 FilePicker 和 Image，
      防止 Ant Design Form.Item 误收集内部表单控件（Upload/Input）导致警告
    -->
    <Form.ItemRest>
      <FilePicker
        ref="filePickerRef"
        :accept="accept"
        :image-only="imageOnly"
        @select="handleSelect"
      />

      <!-- 隐藏的 Image 组件，仅用于控制 antd 图片预览弹窗 -->
      <Image
        v-if="modelValue"
        :src="toPreviewUrl(modelValue)"
        :preview="{
          visible: previewVisible,
          onVisibleChange: (v: boolean) => (previewVisible = v),
        }"
        class="hidden"
      />
    </Form.ItemRest>
  </div>
</template>
