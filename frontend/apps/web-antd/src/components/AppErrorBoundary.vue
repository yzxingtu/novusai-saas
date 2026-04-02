<script lang="ts" setup>
import { onErrorCaptured, ref } from 'vue';

import { Button, Result } from 'ant-design-vue';

import { $t } from '#/locales';

defineOptions({ name: 'AppErrorBoundary' });

const isDev = import.meta.env.DEV;

const capturedError = ref<unknown>(null);
const errorInfo = ref('');

onErrorCaptured((err, _instance, info) => {
  capturedError.value = err;
  errorInfo.value = info;
  console.error('[AppErrorBoundary]', info, err);
  return false;
});

function reload() {
  window.location.reload();
}
</script>

<template>
  <template v-if="capturedError">
    <div class="app-error-boundary">
      <Result
        status="error"
        :title="$t('common.errorBoundaryTitle')"
        :sub-title="$t('common.errorBoundaryHint')"
      >
        <template #extra>
          <Button type="primary" @click="reload">
            {{ $t('common.reloadPage') }}
          </Button>
        </template>
      </Result>
      <pre v-if="errorInfo && isDev" class="app-error-boundary__debug">
        {{ String(capturedError) }}
{{ errorInfo }}
      </pre>
    </div>
  </template>
  <slot v-else></slot>
</template>

<style scoped>
.app-error-boundary {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 40vh;
  padding: 24px;
}

.app-error-boundary__debug {
  max-width: 720px;
  padding: 12px;
  margin-top: 16px;
  overflow: auto;
  font-size: 12px;
  text-align: left;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
  background: var(--ant-color-fill-quaternary, #f5f5f5);
  border-radius: 6px;
}
</style>
