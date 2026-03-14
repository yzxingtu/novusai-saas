<script lang="ts" setup>
/**
 * 手动发送邮件抽屉
 */
import { ref } from 'vue';

import { useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Button, Input, message, Spin, Textarea } from 'ant-design-vue';

import { sendEmailApi } from '#/api/admin/email-log';
import { $t } from '#/locales';

defineOptions({ name: 'SendEmailDrawer' });

const emit = defineEmits<{ success: [] }>();

const [Drawer, drawerApi] = useVbenDrawer();

const loading = ref(false);
const toAddress = ref('');
const subject = ref('');
const htmlBody = ref('');
const textBody = ref('');

async function handleSend() {
  if (!toAddress.value || !subject.value) {
    message.warning($t('admin.system.emailLog.send.requiredFields'));
    return;
  }
  loading.value = true;
  try {
    const recipients = toAddress.value
      .split(',')
      .map((s: string) => s.trim())
      .filter(Boolean);
    const result = await sendEmailApi({
      to: recipients,
      subject: subject.value,
      html_body: htmlBody.value || null,
      text_body: textBody.value || null,
    });
    if (result.success) {
      message.success($t('admin.system.emailLog.send.success'));
      toAddress.value = '';
      subject.value = '';
      htmlBody.value = '';
      textBody.value = '';
      emit('success');
      drawerApi.close();
    } else {
      message.error(result.error || result.message);
    }
  } catch {
    // handled by request interceptor / 错误由请求拦截器处理
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <Drawer :title="$t('admin.system.emailLog.send.title')" class="w-[560px]">
    <Spin :spinning="loading">
      <div class="flex flex-col gap-4">
        <div>
          <label class="mb-1 block text-sm font-medium">
            {{ $t('admin.system.emailLog.toAddress') }}
            <span class="text-destructive">*</span>
          </label>
          <Input
            v-model:value="toAddress"
            :placeholder="$t('admin.system.emailLog.send.toPlaceholder')"
          />
          <span class="mt-0.5 block text-xs text-muted-foreground">
            {{ $t('admin.system.emailLog.send.toHint') }}
          </span>
        </div>

        <div>
          <label class="mb-1 block text-sm font-medium">
            {{ $t('admin.system.emailLog.subject') }}
            <span class="text-destructive">*</span>
          </label>
          <Input
            v-model:value="subject"
            :placeholder="$t('admin.system.emailLog.send.subjectPlaceholder')"
          />
        </div>

        <div>
          <label class="mb-1 block text-sm font-medium">
            {{ $t('admin.system.emailLog.send.htmlBody') }}
          </label>
          <Textarea
            v-model:value="htmlBody"
            :rows="6"
            :placeholder="$t('admin.system.emailLog.send.htmlPlaceholder')"
          />
        </div>

        <div>
          <label class="mb-1 block text-sm font-medium">
            {{ $t('admin.system.emailLog.send.textBody') }}
          </label>
          <Textarea
            v-model:value="textBody"
            :rows="3"
            :placeholder="$t('admin.system.emailLog.send.textPlaceholder')"
          />
        </div>
      </div>
    </Spin>

    <template #footer>
      <div class="flex justify-end gap-2">
        <Button @click="drawerApi.close()">
          {{ $t('common.cancel') }}
        </Button>
        <Button type="primary" :loading="loading" @click="handleSend">
          <IconifyIcon icon="lucide:send" class="mr-1 size-3.5" />
          {{ $t('admin.system.emailLog.send.submit') }}
        </Button>
      </div>
    </template>
  </Drawer>
</template>
