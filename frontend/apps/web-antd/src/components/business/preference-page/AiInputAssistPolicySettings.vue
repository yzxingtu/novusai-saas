<script setup lang="ts">
import type { PlainTextInputAiPolicy } from '#/api/shared/plain-text-input-ai-policy';

import { computed, onMounted, reactive, ref } from 'vue';

import { IconifyIcon } from '@vben/icons';

import { Alert, Button, Spin, Switch } from 'ant-design-vue';

import {
  getAdminConfigGroupDetailApi,
  updateAdminConfigGroupApi,
} from '#/api/admin/configs';
import { getPlainTextInputAiPolicyApi } from '#/api/shared/plain-text-input-ai-policy';
import {
  getTenantConfigGroupDetailApi,
  updateTenantConfigGroupApi,
} from '#/api/tenant/configs';
import { $t } from '#/locales';

const props = defineProps<{
  apiPrefix: '/admin' | '/tenant';
  side: 'admin' | 'tenant';
}>();

const loading = ref(false);
const saving = ref(false);
const policy = ref<null | PlainTextInputAiPolicy>(null);
const formState = reactive({
  platformAdminEnabled: true,
  platformAllowTenantEnable: true,
  platformTenantDefaultEnabled: true,
  tenantEnabled: true,
});

const isTenantSide = computed(() => props.side === 'tenant');
const tenantSwitchDisabled = computed(
  () =>
    isTenantSide.value && policy.value?.platform_allow_tenant_enable === false,
);

function toBoolean(value: unknown, fallback = true): boolean {
  return typeof value === 'boolean' ? value : fallback;
}

function configValue(
  configs: Array<{ key: string; value?: unknown }>,
  key: string,
  fallback = true,
): boolean {
  return toBoolean(configs.find((item) => item.key === key)?.value, fallback);
}

async function loadPolicy() {
  loading.value = true;
  try {
    policy.value = await getPlainTextInputAiPolicyApi(props.apiPrefix);
    if (props.side === 'admin') {
      const group = await getAdminConfigGroupDetailApi('platform_ai_toolkit');
      formState.platformAdminEnabled = configValue(
        group.configs,
        'platform_plain_text_input_ai_admin_enabled',
      );
      formState.platformAllowTenantEnable = configValue(
        group.configs,
        'platform_plain_text_input_ai_allow_tenant_enable',
      );
      formState.platformTenantDefaultEnabled = configValue(
        group.configs,
        'platform_plain_text_input_ai_tenant_default_enabled',
      );
    } else {
      const group = await getTenantConfigGroupDetailApi('tenant_ai');
      formState.tenantEnabled = toBoolean(
        policy.value.tenant_enabled,
        configValue(group.configs, 'tenant_plain_text_input_ai_enabled'),
      );
    }
  } finally {
    loading.value = false;
  }
}

async function savePolicy() {
  saving.value = true;
  try {
    await (props.side === 'admin'
      ? updateAdminConfigGroupApi('platform_ai_toolkit', {
          platform_plain_text_input_ai_admin_enabled:
            formState.platformAdminEnabled,
          platform_plain_text_input_ai_allow_tenant_enable:
            formState.platformAllowTenantEnable,
          platform_plain_text_input_ai_tenant_default_enabled:
            formState.platformTenantDefaultEnabled,
        })
      : updateTenantConfigGroupApi('tenant_ai', {
          tenant_plain_text_input_ai_enabled: formState.tenantEnabled,
        }));
    await loadPolicy();
  } finally {
    saving.value = false;
  }
}

onMounted(() => {
  void loadPolicy();
});
</script>

<template>
  <section
    class="rounded-[28px] border border-border/70 bg-card p-5 shadow-sm sm:p-6"
  >
    <Spin :spinning="loading">
      <div class="mb-5 flex items-start justify-between gap-3">
        <div class="flex items-start gap-3">
          <div
            class="flex size-11 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary"
          >
            <IconifyIcon icon="lucide:sparkles" class="size-5" />
          </div>
          <div>
            <div class="text-lg font-semibold text-foreground">
              {{ $t('common.preference.aiInputAssist.title') }}
            </div>
            <p class="mt-1 text-sm leading-6 text-muted-foreground">
              {{ $t('common.preference.aiInputAssist.desc') }}
            </p>
          </div>
        </div>

        <Button type="primary" :loading="saving" @click="savePolicy">
          <template #icon>
            <IconifyIcon icon="lucide:save" />
          </template>
          {{ $t('common.save') }}
        </Button>
      </div>

      <div v-if="side === 'admin'" class="space-y-3">
        <div
          class="flex items-center justify-between gap-4 rounded-2xl border border-border/60 bg-background/80 px-4 py-3"
        >
          <div>
            <div class="text-sm font-medium text-foreground">
              {{ $t('common.preference.aiInputAssist.adminEnabled') }}
            </div>
            <div class="mt-1 text-xs text-muted-foreground">
              {{ $t('common.preference.aiInputAssist.adminEnabledDesc') }}
            </div>
          </div>
          <Switch v-model:checked="formState.platformAdminEnabled" />
        </div>

        <div
          class="flex items-center justify-between gap-4 rounded-2xl border border-border/60 bg-background/80 px-4 py-3"
        >
          <div>
            <div class="text-sm font-medium text-foreground">
              {{ $t('common.preference.aiInputAssist.allowTenant') }}
            </div>
            <div class="mt-1 text-xs text-muted-foreground">
              {{ $t('common.preference.aiInputAssist.allowTenantDesc') }}
            </div>
          </div>
          <Switch v-model:checked="formState.platformAllowTenantEnable" />
        </div>

        <div
          class="flex items-center justify-between gap-4 rounded-2xl border border-border/60 bg-background/80 px-4 py-3"
        >
          <div>
            <div class="text-sm font-medium text-foreground">
              {{ $t('common.preference.aiInputAssist.tenantDefault') }}
            </div>
            <div class="mt-1 text-xs text-muted-foreground">
              {{ $t('common.preference.aiInputAssist.tenantDefaultDesc') }}
            </div>
          </div>
          <Switch v-model:checked="formState.platformTenantDefaultEnabled" />
        </div>
      </div>

      <div v-else class="space-y-3">
        <Alert
          v-if="tenantSwitchDisabled"
          type="warning"
          show-icon
          :message="$t('common.preference.aiInputAssist.tenantBlocked')"
          class="!rounded-2xl"
        />
        <div
          class="flex items-center justify-between gap-4 rounded-2xl border border-border/60 bg-background/80 px-4 py-3"
          :class="{ 'opacity-60': tenantSwitchDisabled }"
        >
          <div>
            <div class="text-sm font-medium text-foreground">
              {{ $t('common.preference.aiInputAssist.tenantEnabled') }}
            </div>
            <div class="mt-1 text-xs text-muted-foreground">
              {{ $t('common.preference.aiInputAssist.tenantEnabledDesc') }}
            </div>
          </div>
          <Switch
            v-model:checked="formState.tenantEnabled"
            :disabled="tenantSwitchDisabled"
          />
        </div>
      </div>
    </Spin>
  </section>
</template>
