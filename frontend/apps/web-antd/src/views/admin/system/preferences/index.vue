<script setup lang="ts">
import { ref } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Alert, Button, Card, Spin } from 'ant-design-vue';

import NotificationSettings from '#/components/business/notification-panel/NotificationSettings.vue';
import { PreferenceForm } from '#/components/business/preference-form';
import { useGlobalPreferencePage } from '#/composables/use-global-preference-page';
import { $t } from '#/locales';

defineOptions({ name: 'AdminGlobalPreferences' });

const { formData, loading, saving, onSave } = useGlobalPreferencePage('admin');

const notifSettingsRef = ref<InstanceType<typeof NotificationSettings>>();
const notifSaving = ref(false);

async function onSaveNotif() {
  notifSaving.value = true;
  try {
    await notifSettingsRef.value?.save();
  } finally {
    notifSaving.value = false;
  }
}
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
          <PreferenceForm v-model="formData" />
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
