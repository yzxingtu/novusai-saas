<script lang="ts" setup>
/**
 * Knowledge Document Picker
 * 知识库文档输入器
 *
 * Provides three document input methods:
 * 提供三种文档录入方式：
 * 1. File upload (supports PDF/DOCX/TXT/MD/CSV/XLSX/HTML/PPTX/images) / 文件上传
 * 2. Direct text paste / 直接文本粘贴
 * 3. Q&A pair manual input / Q&A 问答对手动输入
 *
 * Props:
 *  - uploadFn: File upload function / 文件上传函数
 *  - textFn: Text submit function / 文本提交函数
 *  - qaFn: Q&A submit function / Q&A 提交函数
 */
import { ref } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Button, Input, message, Modal, Upload } from 'ant-design-vue';

import { $t } from '#/locales';

const props = defineProps<{
  accept?: string;
  qaBatchFn?: (file: File) => Promise<unknown>;
  qaFn?: (data: { answer: string; question: string }) => Promise<unknown>;
  textFn?: (data: { content: string; title: string }) => Promise<unknown>;
  uploadFn: (file: File) => Promise<unknown>;
  urlFn?: (urls: string[]) => Promise<unknown>;
}>();

const emit = defineEmits<{ success: [] }>();

const KB_ACCEPT =
  '.pdf,.docx,.txt,.md,.csv,.xlsx,.html,.htm,.pptx,.jpg,.jpeg,.png,.webp,.gif';

// ========== Modal visibility ==========
const textModalVisible = ref(false);
const qaModalVisible = ref(false);
const urlModalVisible = ref(false);

// ========== File Upload ==========
const uploading = ref(false);

async function handleUpload(file: File) {
  uploading.value = true;
  try {
    await props.uploadFn(file);
    emit('success');
  } catch {
    // handled by global interceptor / 错误由请求拦截器处理
  } finally {
    uploading.value = false;
  }
  return false;
}

// ========== Text Input ==========
const textTitle = ref('');
const textContent = ref('');
const textSubmitting = ref(false);

async function handleSubmitText() {
  if (!props.textFn) return;
  if (!textTitle.value.trim() || !textContent.value.trim()) {
    message.warning($t('shared.knowledgeDocPicker.text.requiredHint'));
    return;
  }
  textSubmitting.value = true;
  try {
    await props.textFn({
      title: textTitle.value.trim(),
      content: textContent.value.trim(),
    });
    textTitle.value = '';
    textContent.value = '';
    textModalVisible.value = false;
    emit('success');
  } catch {
    // handled by global interceptor / 错误由请求拦截器处理
  } finally {
    textSubmitting.value = false;
  }
}

// ========== Q&A ==========
const qaQuestion = ref('');
const qaAnswer = ref('');
const qaSubmitting = ref(false);

async function handleSubmitQA() {
  if (!props.qaFn) return;
  if (!qaQuestion.value.trim() || !qaAnswer.value.trim()) {
    message.warning($t('shared.knowledgeDocPicker.qa.requiredHint'));
    return;
  }
  qaSubmitting.value = true;
  try {
    await props.qaFn({
      question: qaQuestion.value.trim(),
      answer: qaAnswer.value.trim(),
    });
    qaQuestion.value = '';
    qaAnswer.value = '';
    qaModalVisible.value = false;
    emit('success');
  } catch {
    // handled by global interceptor / 错误由请求拦截器处理
  } finally {
    qaSubmitting.value = false;
  }
}

// ========== URL Import ==========
const urlInput = ref('');
const urlSubmitting = ref(false);

async function handleSubmitUrls() {
  if (!props.urlFn) return;
  const urls = urlInput.value
    .split('\n')
    .map((u) => u.trim())
    .filter((u) => u.startsWith('http://') || u.startsWith('https://'));
  if (urls.length === 0) {
    message.warning($t('shared.knowledgeDocPicker.url.requiredHint'));
    return;
  }
  urlSubmitting.value = true;
  try {
    const result = (await props.urlFn(urls)) as { created?: number };
    message.success(
      $t('shared.knowledgeDocPicker.url.result', {
        count: result?.created ?? urls.length,
      }),
    );
    urlInput.value = '';
    urlModalVisible.value = false;
    emit('success');
  } catch {
    // handled by global interceptor / 错误由请求拦截器处理
  } finally {
    urlSubmitting.value = false;
  }
}

// ========== Q&A Batch Import ==========
const qaBatchUploading = ref(false);

async function handleQABatchUpload(file: File) {
  if (!props.qaBatchFn) return false;
  qaBatchUploading.value = true;
  try {
    const result = (await props.qaBatchFn(file)) as {
      imported?: number;
      skipped?: number;
    };
    const imported = result?.imported ?? 0;
    const skipped = result?.skipped ?? 0;
    message.success(
      $t('shared.knowledgeDocPicker.qa.batchResult', { imported, skipped }),
    );
    emit('success');
  } catch {
    // handled by global interceptor / 错误由请求拦截器处理
  } finally {
    qaBatchUploading.value = false;
  }
  return false;
}
</script>

<template>
  <div class="flex flex-wrap items-center gap-2">
    <!-- Upload file button / 上传文件按钮 -->
    <Upload
      :before-upload="handleUpload"
      :show-upload-list="false"
      :multiple="true"
      :accept="accept || KB_ACCEPT"
    >
      <Button :loading="uploading" size="small">
        <IconifyIcon icon="lucide:upload" class="mr-1 size-3.5" />
        {{ $t('shared.knowledgeDocPicker.upload.tab') }}
      </Button>
    </Upload>

    <!-- Paste text button / 粘贴文本按钮 -->
    <Button v-if="textFn" size="small" @click="textModalVisible = true">
      <IconifyIcon icon="lucide:file-text" class="mr-1 size-3.5" />
      {{ $t('shared.knowledgeDocPicker.text.tab') }}
    </Button>

    <!-- Q&A button / Q&A 按钮 -->
    <Button v-if="qaFn" size="small" @click="qaModalVisible = true">
      <IconifyIcon icon="lucide:message-square-plus" class="mr-1 size-3.5" />
      {{ $t('shared.knowledgeDocPicker.qa.tab') }}
    </Button>

    <!-- URL import button / URL 导入按钮 -->
    <Button v-if="urlFn" size="small" @click="urlModalVisible = true">
      <IconifyIcon icon="lucide:globe" class="mr-1 size-3.5" />
      {{ $t('shared.knowledgeDocPicker.url.tab') }}
    </Button>

    <!-- Q&A batch import / Q&A 批量导入 -->
    <Upload
      v-if="qaBatchFn"
      :before-upload="handleQABatchUpload"
      :show-upload-list="false"
      accept=".csv,.xlsx"
    >
      <Button size="small" :loading="qaBatchUploading">
        <IconifyIcon icon="lucide:file-spreadsheet" class="mr-1 size-3.5" />
        {{ $t('shared.knowledgeDocPicker.qa.batchImport') }}
      </Button>
    </Upload>
  </div>

  <!-- ========== Text paste modal / 文本粘贴弹窗 ========== -->
  <Modal
    v-if="textFn"
    v-model:open="textModalVisible"
    :title="$t('shared.knowledgeDocPicker.text.tab')"
    :ok-text="$t('shared.knowledgeDocPicker.text.submit')"
    :confirm-loading="textSubmitting"
    :ok-button-props="{ disabled: !textTitle.trim() || !textContent.trim() }"
    @ok="handleSubmitText"
    width="560px"
  >
    <div class="flex flex-col gap-3 py-2">
      <div>
        <div class="mb-1 text-sm font-medium">
          {{ $t('shared.knowledgeDocPicker.text.title') }}
        </div>
        <Input
          v-model:value="textTitle"
          :placeholder="$t('shared.knowledgeDocPicker.text.titlePlaceholder')"
        />
      </div>
      <div>
        <div class="mb-1 text-sm font-medium">
          {{ $t('shared.knowledgeDocPicker.text.content') }}
        </div>
        <Input.TextArea
          v-model:value="textContent"
          :rows="8"
          :placeholder="$t('shared.knowledgeDocPicker.text.contentPlaceholder')"
        />
      </div>
    </div>
  </Modal>

  <!-- ========== Q&A modal / Q&A 弹窗 ========== -->
  <Modal
    v-if="qaFn"
    v-model:open="qaModalVisible"
    :title="$t('shared.knowledgeDocPicker.qa.tab')"
    :ok-text="$t('shared.knowledgeDocPicker.qa.submit')"
    :confirm-loading="qaSubmitting"
    :ok-button-props="{ disabled: !qaQuestion.trim() || !qaAnswer.trim() }"
    @ok="handleSubmitQA"
    width="560px"
  >
    <div class="flex flex-col gap-3 py-2">
      <div>
        <div class="mb-1 text-sm font-medium">
          {{ $t('shared.knowledgeDocPicker.qa.question') }}
        </div>
        <Input.TextArea
          v-model:value="qaQuestion"
          :rows="3"
          :placeholder="$t('shared.knowledgeDocPicker.qa.questionPlaceholder')"
        />
      </div>
      <div>
        <div class="mb-1 text-sm font-medium">
          {{ $t('shared.knowledgeDocPicker.qa.answer') }}
        </div>
        <Input.TextArea
          v-model:value="qaAnswer"
          :rows="5"
          :placeholder="$t('shared.knowledgeDocPicker.qa.answerPlaceholder')"
        />
      </div>
    </div>
  </Modal>

  <!-- ========== URL import modal / URL 导入弹窗 ========== -->
  <Modal
    v-if="urlFn"
    v-model:open="urlModalVisible"
    :title="$t('shared.knowledgeDocPicker.url.tab')"
    :ok-text="$t('shared.knowledgeDocPicker.url.submit')"
    :confirm-loading="urlSubmitting"
    :ok-button-props="{ disabled: !urlInput.trim() }"
    @ok="handleSubmitUrls"
    width="560px"
  >
    <div class="py-2">
      <div class="mb-1 text-sm font-medium">
        {{ $t('shared.knowledgeDocPicker.url.label') }}
      </div>
      <Input.TextArea
        v-model:value="urlInput"
        :rows="6"
        :placeholder="$t('shared.knowledgeDocPicker.url.placeholder')"
      />
    </div>
  </Modal>
</template>
