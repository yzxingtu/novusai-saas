<script setup lang="ts">
/**
 * Platform global preferences page / 平台全局偏好设置页面
 *
 * Super admin can set default preferences for all platform admins.
 * 超级管理员可为所有平台管理员设置默认偏好。
 */
import type { PreferencesData } from '#/api/admin/preferences';

import { onMounted, ref } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Alert, Button, Card, message, Spin } from 'ant-design-vue';

import NotificationSettings from '#/components/business/notification-panel/NotificationSettings.vue';
import { PreferenceForm } from '#/components/business/preference-form';
import { $t } from '#/locales';
import { useUserPreferenceStore } from '#/store/shared';

defineOptions({ name: 'AdminGlobalPreferences' });

const preferenceStore = useUserPreferenceStore();
const notifSettingsRef = ref<InstanceType<typeof NotificationSettings>>();

const formData = ref<PreferencesData>({});
const loading = ref(false);
const saving = ref(false);
const notifSaving = ref(false);

async function loadData() {
  loading.value = true;
  try {
    const data = await preferenceStore.loadGlobalPreferences('admin');
    if (data) {
      formData.value = { ...data };
    }
  } finally {
    loading.value = false;
  }
}

async function onSave() {
  saving.value = true;
  try {
    const result = await preferenceStore.updateGlobalPreferences(
      'admin',
      formData.value,
    );
    if (result) {
      formData.value = { ...result };
      message.success($t('common.preference.saveSuccess'));
    }
  } finally {
    saving.value = false;
  }
}

async function onSaveNotif() {
  notifSaving.value = true;
  try {
    await notifSettingsRef.value?.save();
  } finally {
    notifSaving.value = false;
  }
}

onMounted(() => {
  loadData();
});
</script>

<template>
  <Page auto-content-height>
    <div class="flex h-full flex-col gap-4 overflow-auto">
      <Card :body-style="{ padding: '16px 24px' }">
        <template #title>
          <div class="flex items-center gap-2">
            <IconifyIcon
              icon="lucide:settings-2"
              class="h-4 w-4 text-primary"
            />
            <span>{{ $t('common.preference.globalTitle') }}</span>
          </div>
        </template>
        <template #extra>
          <Button type="primary" :loading="saving" @click="onSave">
            <template #icon>
              <IconifyIcon icon="lucide:save" />
            </template>
            {{ $t('common.save') }}
          </Button>
        </template>

        <Spin :spinning="loading">
          <Alert
            :message="$t('common.preference.globalSaveHint')"
            type="info"
            show-icon
            class="mb-4"
          />
          <PreferenceForm v-model="formData" mode="global" />
        </Spin>
      </Card>

      <Card :body-style="{ padding: '16px 24px' }">
        <template #title>
          <div class="flex items-center gap-2">
            <IconifyIcon icon="lucide:bell" class="h-4 w-4 text-primary" />
            <span>{{ $t('common.notification.globalTitle') }}</span>
          </div>
        </template>
        <template #extra>
          <Button type="primary" :loading="notifSaving" @click="onSaveNotif">
            <template #icon>
              <IconifyIcon icon="lucide:save" />
            </template>
            {{ $t('common.save') }}
          </Button>
        </template>

        <NotificationSettings
          ref="notifSettingsRef"
          mode="global"
          api-prefix="/admin"
        />
      </Card>
    </div>
  </Page>
</template>
