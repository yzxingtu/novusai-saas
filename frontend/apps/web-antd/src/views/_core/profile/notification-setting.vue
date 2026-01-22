<script setup lang="ts">
import { computed } from 'vue';

import { ProfileNotificationSetting } from '@vben/common-ui';

import { $t } from '#/locales';

const formSchema = computed(() => {
  return [
    {
      value: true,
      fieldName: 'userMessage',
      label: $t('shared.profile.notification.userMessage'),
      description: $t('shared.profile.notification.userMessageDesc'),
    },
    {
      value: true,
      fieldName: 'systemMessage',
      label: $t('shared.profile.notification.systemMessage'),
      description: $t('shared.profile.notification.systemMessageDesc'),
    },
    {
      value: true,
      fieldName: 'todoTask',
      label: $t('shared.profile.notification.todoTask'),
      description: $t('shared.profile.notification.todoTaskDesc'),
    },
  ];
});
</script>
<template>
  <ProfileNotificationSetting :form-schema="formSchema" />
</template>
