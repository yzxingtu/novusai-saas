<script setup lang="ts">
import type { VbenFormSchema } from '#/adapter/form';

import { computed } from 'vue';

import { ProfilePasswordSetting, z } from '@vben/common-ui';

import { message } from 'ant-design-vue';

import { $t } from '#/locales';

const formSchema = computed((): VbenFormSchema[] => {
  return [
    {
      fieldName: 'oldPassword',
      label: $t('demos.profile.oldPassword'),
      component: 'VbenInputPassword',
      componentProps: {
        placeholder: $t('demos.profile.inputOldPassword'),
      },
    },
    {
      fieldName: 'newPassword',
      label: $t('demos.profile.newPassword'),
      component: 'VbenInputPassword',
      componentProps: {
        passwordStrength: true,
        placeholder: $t('demos.profile.inputNewPassword'),
      },
    },
    {
      fieldName: 'confirmPassword',
      label: $t('demos.profile.confirmPassword'),
      component: 'VbenInputPassword',
      componentProps: {
        passwordStrength: true,
        placeholder: $t('demos.profile.confirmNewPassword'),
      },
      dependencies: {
        rules(values) {
          const { newPassword } = values;
          return z
            .string({ required_error: $t('demos.profile.confirmNewPassword') })
            .min(1, { message: $t('demos.profile.confirmNewPassword') })
            .refine((value) => value === newPassword, {
              message: $t('demos.profile.passwordMismatch'),
            });
        },
        triggerFields: ['newPassword'],
      },
    },
  ];
});

function handleSubmit() {
  message.success($t('demos.profile.changePasswordSuccess'));
}
</script>
<template>
  <ProfilePasswordSetting
    class="w-1/3"
    :form-schema="formSchema"
    @submit="handleSubmit"
  />
</template>
