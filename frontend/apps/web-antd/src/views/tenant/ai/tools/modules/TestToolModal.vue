<script lang="ts" setup>
defineOptions({ name: 'TenantTestToolModal' });
/**
 * 工具测试执行弹窗
 * 输入 JSON 参数，调用 testToolApi，展示执行结果
 */
import type { ToolTestResult } from '#/api/tenant/tools';

import { ref, watch } from 'vue';

import { Alert, Button, Input, message, Modal, Spin, Tag } from 'ant-design-vue';

import { testToolApi } from '#/api/tenant/tools';
import { $t } from '#/locales';

const props = defineProps<{
  toolId: null | number;
}>();

const open = defineModel<boolean>('open', { default: false });

const argsStr = ref('{}');
const loading = ref(false);
const result = ref<null | ToolTestResult>(null);

/** 弹窗打开时重置状态 */
watch(open, (val) => {
  if (val) {
    argsStr.value = '{}';
    result.value = null;
    loading.value = false;
  }
});

async function onExecute() {
  if (!props.toolId) return;

  let args: Record<string, unknown>;
  try {
    args = JSON.parse(argsStr.value) as Record<string, unknown>;
  } catch {
    message.error($t('tenant.ai.tool.test.invalidJson'));
    return;
  }

  loading.value = true;
  result.value = null;
  try {
    result.value = await testToolApi(props.toolId, { arguments: args });
  } catch {
    message.error($t('tenant.ai.tool.test.executeFailed'));
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <Modal
    v-model:open="open"
    :title="$t('tenant.ai.tool.testExecute')"
    :footer="null"
    :width="640"
    destroy-on-close
  >
    <Spin :spinning="loading">
      <div class="flex flex-col gap-4">
        <!-- 参数输入 -->
        <div>
          <div class="mb-1.5 text-sm font-medium">
            {{ $t('tenant.ai.tool.test.arguments') }}
          </div>
          <Input.TextArea
            v-model:value="argsStr"
            :rows="6"
            :placeholder="$t('tenant.ai.tool.test.argumentsPlaceholder')"
            class="font-mono text-xs"
          />
        </div>

        <!-- 执行按钮 -->
        <div class="flex justify-end">
          <Button
            type="primary"
            :loading="loading"
            @click="onExecute"
          >
            {{ $t('tenant.ai.tool.test.run') }}
          </Button>
        </div>

        <!-- 执行结果 -->
        <div v-if="result" class="flex flex-col gap-3">
          <div class="flex items-center gap-2">
            <Tag :color="result.success ? 'success' : 'error'">
              {{ result.success ? $t('tenant.ai.tool.test.success') : $t('tenant.ai.tool.test.failed') }}
            </Tag>
            <span class="text-xs text-muted-foreground">
              {{ result.duration_ms }}ms
            </span>
          </div>

          <!-- 输出 -->
          <div v-if="result.output">
            <div class="mb-1 text-sm font-medium">
              {{ $t('tenant.ai.tool.test.output') }}
            </div>
            <pre class="max-h-60 overflow-auto rounded bg-accent/50 p-3 text-xs">{{ result.output }}</pre>
          </div>

          <!-- 错误 -->
          <Alert
            v-if="result.error"
            type="error"
            :message="$t('tenant.ai.tool.test.errorDetail')"
            :description="result.error"
            show-icon
          />
        </div>
      </div>
    </Spin>
  </Modal>
</template>
