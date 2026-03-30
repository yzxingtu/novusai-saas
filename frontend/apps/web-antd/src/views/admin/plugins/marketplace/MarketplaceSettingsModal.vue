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
  Tag,
} from 'ant-design-vue';

import { $t } from '#/locales';
import { requestClient } from '#/utils/request';

const emit = defineEmits<{ saved: [] }>();

const visible = ref(false);
const saving = ref(false);
const testing = ref(false);
const testingSkills = ref(false);
const testResult = ref<null | {
  error?: string;
  latency_ms: number;
  ok: boolean;
}>(null);
const skillTestResult = ref<null | {
  error?: string;
  latency_ms: number;
  ok: boolean;
}>(null);

const form = ref({
  github_url: '',
  cache_ttl: 3600,
  skill_github_url: '',
  skill_cache_ttl: 3600,
});

async function open() {
  visible.value = true;
  testResult.value = null;
  skillTestResult.value = null;
  try {
    const res = (await requestClient.get('/admin/config', {
      params: {
        keys: 'marketplace_github_url,marketplace_cache_ttl,skill_registry_github_url,skill_registry_cache_ttl',
      },
    })) as Record<string, unknown>;
    const data = (res as Record<string, unknown>)?.data as
      | Record<string, string>
      | undefined;
    if (data) {
      form.value.github_url = data.marketplace_github_url || '';
      form.value.cache_ttl = Number(data.marketplace_cache_ttl) || 3600;
      form.value.skill_github_url = data.skill_registry_github_url || '';
      form.value.skill_cache_ttl = Number(data.skill_registry_cache_ttl) || 3600;
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
        marketplace_github_url: form.value.github_url,
        marketplace_cache_ttl: String(form.value.cache_ttl),
        skill_registry_github_url: form.value.skill_github_url,
        skill_registry_cache_ttl: String(form.value.skill_cache_ttl),
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
    const sourceUrl = form.value.github_url || '';

    const res = (await requestClient.post(
      '/admin/plugins/marketplace/test-connection',
      null,
      {
        params: { source_url: sourceUrl },
      },
    )) as Record<string, unknown>;
    testResult.value = (res as Record<string, unknown>)
      ?.data as typeof testResult.value;
  } catch {
    testResult.value = { ok: false, latency_ms: -1, error: 'Request failed' };
  } finally {
    testing.value = false;
  }
}

async function handleSkillTestConnection() {
  testingSkills.value = true;
  skillTestResult.value = null;
  try {
    const sourceUrl = form.value.skill_github_url || '';

    const res = (await requestClient.post(
      '/admin/plugins/skill-registry/test-connection',
      null,
      {
        params: { source_url: sourceUrl },
      },
    )) as Record<string, unknown>;
    skillTestResult.value = (res as Record<string, unknown>)
      ?.data as typeof skillTestResult.value;
  } catch {
    skillTestResult.value = {
      ok: false,
      latency_ms: -1,
      error: 'Request failed',
    };
  } finally {
    testingSkills.value = false;
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
      <!-- 自定义 URL -->
      <FormItem label="GitHub URL">
        <Input
          v-model:value="form.github_url"
          placeholder="https://raw.githubusercontent.com/novusai/plugin-marketplace/main"
          allow-clear
        />
      </FormItem>

      <!-- 缓存 TTL -->
      <FormItem :label="$t('admin.plugin.marketplace.cacheTtl')">
        <InputNumber
          v-model:value="form.cache_ttl"
          :min="60"
          :max="86400"
          :step="300"
          addon-after="s"
          class="!w-40"
        />
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

      <div class="mb-4 mt-2 border-t border-border/60 pt-4 text-sm font-semibold">
        {{ $t('admin.plugin.marketplace.skillRegistrySettings') }}
      </div>

      <FormItem label="Skill Registry GitHub URL">
        <Input
          v-model:value="form.skill_github_url"
          placeholder="https://raw.githubusercontent.com/novusai/skill-marketplace/main"
          allow-clear
        />
      </FormItem>

      <FormItem :label="$t('admin.plugin.marketplace.cacheTtl')">
        <InputNumber
          v-model:value="form.skill_cache_ttl"
          :min="60"
          :max="86400"
          :step="300"
          addon-after="s"
          class="!w-40"
        />
      </FormItem>

      <FormItem>
        <div class="flex items-center gap-3">
          <Button :loading="testingSkills" @click="handleSkillTestConnection">
            <IconifyIcon icon="lucide:wifi" class="mr-1.5 size-4" />
            {{ $t('admin.plugin.marketplace.testConnection') }}
          </Button>
          <template v-if="skillTestResult">
            <Tag v-if="skillTestResult.ok" color="success">
              <IconifyIcon icon="lucide:check" class="mr-0.5 inline size-3" />
              {{ skillTestResult.latency_ms }}ms
            </Tag>
            <Tag v-else color="error">
              <IconifyIcon icon="lucide:x" class="mr-0.5 inline size-3" />
              {{ skillTestResult.error || 'Failed' }}
            </Tag>
          </template>
        </div>
      </FormItem>
    </Form>
  </Modal>
</template>
