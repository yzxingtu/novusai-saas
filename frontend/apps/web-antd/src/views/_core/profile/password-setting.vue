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
      label: $t('shared.profile.oldPassword'),
      component: 'VbenInputPassword',
      componentProps: {
        placeholder: $t('shared.profile.placeholder.inputOldPassword'),
      },
    },
    {
      fieldName: 'newPassword',
      label: $t('shared.profile.newPassword'),
      component: 'VbenInputPassword',
      componentProps: {
        passwordStrength: true,
        placeholder: $t('shared.profile.placeholder.inputNewPassword'),
      },
    },
    {
      fieldName: 'confirmPassword',
      label: $t('shared.profile.confirmPassword'),
      component: 'VbenInputPassword',
      componentProps: {
        passwordStrength: true,
        placeholder: $t('shared.profile.placeholder.confirmNewPassword'),
      },
      dependencies: {
        rules(values) {
          const { newPassword } = values;
          return z
            .string({
              required_error: $t(
                'shared.profile.placeholder.confirmNewPassword',
              ),
            })
            .min(1, {
              message: $t('shared.profile.placeholder.confirmNewPassword'),
            })
            .refine((value) => value === newPassword, {
              message: $t('shared.profile.validation.passwordMismatch'),
            });
        },
        triggerFields: ['newPassword'],
      },
    },
  ];
});

function handleSubmit() {
  message.success($t('shared.profile.messages.changePasswordSuccess'));
}
</script>
<template>
  <ProfilePasswordSetting
    class="w-1/3"
    :form-schema="formSchema"
    @submit="handleSubmit"
  />
</template>
