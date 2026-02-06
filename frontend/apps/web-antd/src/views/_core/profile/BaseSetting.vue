<script setup lang="ts">
import type { VbenFormSchema } from '#/adapter/form';

import { computed, onMounted } from 'vue';

import { ProfileBaseSetting } from '@vben/common-ui';

import { $t } from '#/locales';

// TODO: 根据当前登录端动态获取用户信息 API
// import { getUserInfoApi } from '#/api';

const formSchema = computed((): VbenFormSchema[] => {
  return [
    {
      fieldName: 'realName',
      component: 'Input',
      label: $t('shared.profile.realName'),
    },
    {
      fieldName: 'username',
      component: 'Input',
      label: $t('shared.profile.username'),
    },
    {
      fieldName: 'introduction',
      component: 'Textarea',
      label: $t('shared.profile.introduction'),
    },
  ];
});

onMounted(async () => {
  // TODO: 根据当前登录端获取用户信息
  // const data = await getUserInfoApi();
  // profileBaseSettingRef.value.getFormApi().setValues(data);
});
</script>
<template>
  <ProfileBaseSetting :form-schema="formSchema" />
</template>
