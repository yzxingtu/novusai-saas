<script lang="ts" setup>
/**
 * 插件市场镜像源设置弹窗
 */
import { ref } from 'vue';

import { IconifyIcon } from '@vben/icons';

import {
  Button,
  Form,
  FormItem,
  Input,
  InputNumber,
  message,
  Modal,
  Radio,
  RadioGroup,
  Space,
  Tag,
} from 'ant-design-vue';

import { requestClient } from '#/utils/request';
import { $t } from '#/locales';

const emit = defineEmits<{ saved: [] }>();

const visible = ref(false);
const saving = ref(false);
const testing = ref(false);
const testResult = ref<{ ok: boolean; latency_ms: number; error?: string } | null>(null);

const form = ref({
  preferred_source: 'auto',
  github_url: '',
  gitee_url: '',
  cache_ttl: 3600,
});

async function open() {
  visible.value = true;
  testResult.value = null;
  try {
    const res = await requestClient.get('/admin/config', {
      params: {
        keys: 'marketplace_preferred_source,marketplace_github_url,marketplace_gitee_url,marketplace_cache_ttl',
      },
    }) as Record<string, unknown>;
    const data = (res as Record<string, unknown>)?.data as Record<string, string> | undefined;
    if (data) {
      form.value.preferred_source = data.marketplace_preferred_source || 'auto';
      form.value.github_url = data.marketplace_github_url || '';
      form.value.gitee_url = data.marketplace_gitee_url || '';
      form.value.cache_ttl = Number(data.marketplace_cache_ttl) || 3600;
    }
  } catch {
    //
  }
}

async function handleSave() {
  saving.value = true;
  try {
    await requestClient.put('/admin/config', {
      configs: {
        marketplace_preferred_source: form.value.preferred_source,
        marketplace_github_url: form.value.github_url,
        marketplace_gitee_url: form.value.gitee_url,
        marketplace_cache_ttl: String(form.value.cache_ttl),
      },
    });
    message.success($t('admin.plugin.config.saveSuccess'));
    visible.value = false;
    emit('saved');
  } catch {
    //
  } finally {
    saving.value = false;
  }
}

async function handleTestConnection() {
  testing.value = true;
  testResult.value = null;
  try {
    let sourceUrl = '';
    if (form.value.preferred_source === 'github') {
      sourceUrl = form.value.github_url || '';
    } else if (form.value.preferred_source === 'gitee') {
      sourceUrl = form.value.gitee_url || '';
    }

    const res = await requestClient.post('/admin/plugins/marketplace/test-connection', null, {
      params: { source_url: sourceUrl },
    }) as Record<string, unknown>;
    testResult.value = (res as Record<string, unknown>)?.data as typeof testResult.value;
  } catch {
    testResult.value = { ok: false, latency_ms: -1, error: 'Request failed' };
  } finally {
    testing.value = false;
  }
}

defineExpose({ open });
</script>

<template>
  <Modal
    v-model:open="visible"
    :title="$t('admin.plugin.marketplace.settings')"
    :ok-text="$t('admin.plugin.config.save')"
    :confirm-loading="saving"
    :width="520"
    @ok="handleSave"
  >
    <Form layout="vertical" class="py-2">
      <!-- 镜像源选择 -->
      <FormItem :label="$t('admin.plugin.marketplace.mirrorSource')">
        <RadioGroup v-model:value="form.preferred_source">
          <Space direction="vertical">
            <Radio value="auto">
              <span class="font-medium">{{ $t('admin.plugin.marketplace.sourceAuto') }}</span>
              <span class="ml-2 text-xs text-muted-foreground">{{ $t('admin.plugin.marketplace.sourceAutoDesc') }}</span>
            </Radio>
            <Radio value="github">
              <span class="font-medium">GitHub</span>
            </Radio>
            <Radio value="gitee">
              <span class="font-medium">Gitee</span>
            </Radio>
          </Space>
        </RadioGroup>
      </FormItem>

      <!-- 自定义 URL -->
      <FormItem label="GitHub URL">
        <Input
          v-model:value="form.github_url"
          placeholder="https://raw.githubusercontent.com/novusai/plugin-marketplace/main"
          allow-clear
        />
      </FormItem>
      <FormItem label="Gitee URL">
        <Input
          v-model:value="form.gitee_url"
          placeholder="https://gitee.com/novusai/plugin-marketplace/raw/main"
          allow-clear
        />
      </FormItem>

      <!-- 缓存 TTL -->
      <FormItem :label="$t('admin.plugin.marketplace.cacheTtl')">
        <InputNumber v-model:value="form.cache_ttl" :min="60" :max="86400" :step="300" addon-after="s" class="!w-40" />
      </FormItem>

      <!-- 测试连接 -->
      <FormItem>
        <div class="flex items-center gap-3">
          <Button :loading="testing" @click="handleTestConnection">
            <IconifyIcon icon="lucide:wifi" class="mr-1.5 size-4" />
            {{ $t('admin.plugin.marketplace.testConnection') }}
          </Button>
          <template v-if="testResult">
            <Tag v-if="testResult.ok" color="success">
              <IconifyIcon icon="lucide:check" class="mr-0.5 inline size-3" />
              {{ testResult.latency_ms }}ms
            </Tag>
            <Tag v-else color="error">
              <IconifyIcon icon="lucide:x" class="mr-0.5 inline size-3" />
              {{ testResult.error || 'Failed' }}
            </Tag>
          </template>
        </div>
      </FormItem>
    </Form>
  </Modal>
</template>
