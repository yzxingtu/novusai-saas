<script lang="ts" setup>
import type { VbenFormSchema } from '@vben/common-ui';

import type { CaptchaDifficulty } from '#/api/public/captcha';

import { computed, h, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

import { AuthenticationRegister, z } from '@vben/common-ui';
import { $t } from '@vben/locales';

import { notification } from 'ant-design-vue';

import { userApi } from '#/api';
import { CaptchaImage } from '#/components/business/captcha';
import { usePublicConfigStore } from '#/store';

defineOptions({ name: 'UserRegister' });

const router = useRouter();
const loading = ref(false);
const publicConfigStore = usePublicConfigStore();

const captchaRef = ref<InstanceType<typeof CaptchaImage>>();
const captchaSolution = ref('');
const showCaptcha = ref(false);

const captchaDifficulty = computed((): CaptchaDifficulty => {
  const difficulty = publicConfigStore.tenantCaptcha?.difficulty;
  if (
    difficulty === 'easy' ||
    difficulty === 'medium' ||
    difficulty === 'hard'
  ) {
    return difficulty;
  }
  return 'medium';
});

onMounted(async () => {
  await publicConfigStore.loadTenantConfig();
  showCaptcha.value = publicConfigStore.shouldShowTenantCaptcha;
});

function refreshCaptcha() {
  captchaSolution.value = '';
  captchaRef.value?.refresh();
}

const formSchema = computed((): VbenFormSchema[] => {
  return [
    {
      component: 'VbenInput',
      componentProps: {
        placeholder: $t('authentication.usernameTip'),
      },
      fieldName: 'username',
      label: $t('authentication.username'),
      rules: z
        .string()
        .min(2, { message: $t('authentication.usernameTip') }),
    },
    {
      component: 'VbenInput',
      componentProps: {
        placeholder: $t('user.auth.emailPlaceholder'),
      },
      fieldName: 'email',
      label: $t('user.auth.email'),
      rules: z
        .string()
        .min(1, { message: $t('user.auth.emailRequired') })
        .email({ message: $t('user.auth.emailInvalid') }),
    },
    {
      component: 'VbenInputPassword',
      componentProps: {
        passwordStrength: true,
        placeholder: $t('authentication.password'),
      },
      fieldName: 'password',
      label: $t('authentication.password'),
      renderComponentContent() {
        return {
          strengthText: () => $t('authentication.passwordStrength'),
        };
      },
      rules: z
        .string()
        .min(6, { message: $t('user.auth.passwordMinLength') }),
    },
    {
      component: 'VbenInputPassword',
      componentProps: {
        placeholder: $t('authentication.confirmPassword'),
      },
      dependencies: {
        rules(values) {
          const { password } = values;
          return z
            .string({ required_error: $t('authentication.passwordTip') })
            .min(1, { message: $t('authentication.passwordTip') })
            .refine((value) => value === password, {
              message: $t('authentication.confirmPasswordTip'),
            });
        },
        triggerFields: ['password'],
      },
      fieldName: 'confirmPassword',
      label: $t('authentication.confirmPassword'),
    },
    {
      component: 'VbenCheckbox',
      fieldName: 'agreePolicy',
      renderComponentContent: () => ({
        default: () => {
          const privacyUrl = publicConfigStore.tenantConfig?.privacyPolicyUrl;
          const termsUrl = publicConfigStore.tenantConfig?.termsUrl;
          const privacyNode = privacyUrl
            ? h('a', { class: 'vben-link', href: privacyUrl, target: '_blank', rel: 'noopener noreferrer' }, $t('authentication.privacyPolicy'))
            : h('span', $t('authentication.privacyPolicy'));
          const termsNode = termsUrl
            ? h('a', { class: 'vben-link ml-1', href: termsUrl, target: '_blank', rel: 'noopener noreferrer' }, $t('authentication.terms'))
            : h('span', { class: 'ml-1' }, $t('authentication.terms'));
          return h('span', [$t('authentication.agree'), ' ', privacyNode, ' & ', termsNode]);
        },
      }),
      rules: z.boolean().refine((value) => !!value, {
        message: $t('authentication.agreeTip'),
      }),
    },
  ];
});

async function handleSubmit(values: Record<string, unknown>) {
  if (showCaptcha.value && !captchaSolution.value) {
    return;
  }
  try {
    loading.value = true;

    const params: userApi.RegisterParams = {
      confirmPassword: values.confirmPassword as string,
      email: values.email as string,
      password: values.password as string,
      username: values.username as string,
    };

    if (showCaptcha.value && captchaRef.value) {
      params.captchaChallengeId = captchaRef.value.getChallengeId();
      params.captchaSolution = captchaSolution.value;
      params.captchaProviderCode =
        publicConfigStore.tenantCaptcha?.provider ?? 'image';
    }

    const result = await userApi.userRegisterApi(params);

    const isPending = result.approvalStatus === 'pending';

    notification.success({
      description: isPending
        ? $t('user.auth.registerPendingDesc')
        : $t('user.auth.registerSuccessDesc'),
      duration: isPending ? 5 : 3,
      message: $t('user.auth.registerSuccess'),
    });

    await router.push('/auth/login');
  } catch (error: unknown) {
    const err = error as {
      response?: { data?: { data?: { captcha_required?: boolean; errors?: Array<{ captcha_required?: boolean }> } } };
    };
    const captchaRequired =
      err?.response?.data?.data?.captcha_required ||
      err?.response?.data?.data?.errors?.[0]?.captcha_required;
    if (captchaRequired) {
      showCaptcha.value = true;
      refreshCaptcha();
    }
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <AuthenticationRegister
    :form-schema="formSchema"
    :loading="loading"
    @submit="handleSubmit"
  >
    <template v-if="showCaptcha" #beforeSubmit>
      <CaptchaImage
        ref="captchaRef"
        v-model="captchaSolution"
        :difficulty="captchaDifficulty"
        endpoint="tenant"
      />
    </template>
  </AuthenticationRegister>
</template>
