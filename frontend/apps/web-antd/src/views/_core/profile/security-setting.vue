<script setup lang="ts">
import { computed } from 'vue';

import { ProfileSecuritySetting } from '@vben/common-ui';

import { $t } from '#/locales';

const formSchema = computed(() => {
  return [
    {
      value: true,
      fieldName: 'accountPassword',
      label: $t('shared.profile.security.accountPassword'),
      description: $t('shared.profile.security.passwordStrength'),
    },
    {
      value: true,
      fieldName: 'securityPhone',
      label: $t('shared.profile.security.securityPhone'),
      description: $t('shared.profile.security.phoneBound'),
    },
    {
      value: true,
      fieldName: 'securityQuestion',
      label: $t('shared.profile.security.securityQuestion'),
      description: $t('shared.profile.security.questionNotSet'),
    },
    {
      value: true,
      fieldName: 'securityEmail',
      label: $t('shared.profile.security.securityEmail'),
      description: $t('shared.profile.security.emailBound'),
    },
    {
      value: false,
      fieldName: 'securityMfa',
      label: $t('shared.profile.security.mfaDevice'),
      description: $t('shared.profile.security.mfaNotBound'),
    },
  ];
});
</script>
<template>
  <ProfileSecuritySetting :form-schema="formSchema" />
</template>
