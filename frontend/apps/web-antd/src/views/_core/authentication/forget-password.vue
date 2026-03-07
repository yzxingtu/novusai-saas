<script lang="ts" setup>
import type { VbenFormSchema } from '@vben/common-ui';

import { computed, ref } from 'vue';
import { useRouter } from 'vue-router';

import { AuthenticationForgetPassword, z } from '@vben/common-ui';
import { $t } from '@vben/locales';

import { Input, notification } from 'ant-design-vue';

import { userApi } from '#/api';

defineOptions({ name: 'UserForgetPassword' });

const router = useRouter();
const loading = ref(false);
const codeSent = ref(false);
const emailValue = ref('');
const showTenantCode = ref(false);
const tenantCode = ref('');

const formSchema = computed((): VbenFormSchema[] => {
  const schemas: VbenFormSchema[] = [
    {
      component: 'VbenInput',
      componentProps: {
        disabled: codeSent.value,
        placeholder: 'example@example.com',
      },
      fieldName: 'email',
      label: $t('authentication.email'),
      rules: z
        .string()
        .min(1, { message: $t('authentication.emailTip') })
        .email($t('authentication.emailValidErrorTip')),
    },
  ];

  if (codeSent.value) {
    schemas.push(
      {
        component: 'VbenInput',
        componentProps: {
          placeholder: $t('user.auth.codePlaceholder'),
        },
        fieldName: 'code',
        label: $t('user.auth.verificationCode'),
        rules: z
          .string()
          .min(4, { message: $t('user.auth.codeRequired') }),
      },
      {
        component: 'VbenInputPassword',
        componentProps: {
          placeholder: $t('user.auth.newPasswordPlaceholder'),
        },
        fieldName: 'newPassword',
        label: $t('user.auth.newPassword'),
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
            const { newPassword } = values;
            return z
              .string()
              .min(1, { message: $t('authentication.passwordTip') })
              .refine((value) => value === newPassword, {
                message: $t('authentication.confirmPasswordTip'),
              });
          },
          triggerFields: ['newPassword'],
        },
        fieldName: 'confirmPassword',
        label: $t('authentication.confirmPassword'),
      },
    );
  }

  return schemas;
});

async function handleSubmit(values: Record<string, unknown>) {
  try {
    loading.value = true;

    if (!codeSent.value) {
      await userApi.userForgotPasswordApi({
        email: values.email as string,
        tenantCode: showTenantCode.value ? tenantCode.value : undefined,
      });

      emailValue.value = values.email as string;
      codeSent.value = true;

      notification.success({
        description: $t('user.auth.codeSentDesc'),
        duration: 5,
        message: $t('user.auth.codeSent'),
      });
    } else {
      await userApi.userResetPasswordApi({
        code: values.code as string,
        confirmPassword: values.confirmPassword as string,
        email: emailValue.value,
        newPassword: values.newPassword as string,
        tenantCode: showTenantCode.value ? tenantCode.value : undefined,
      });

      notification.success({
        description: $t('user.auth.resetSuccessDesc'),
        duration: 3,
        message: $t('user.auth.resetSuccess'),
      });

      await router.push('/login');
    }
  } catch (error: unknown) {
    const err = error as {
      response?: {
        data?: {
          data?: {
            tenant_code_required?: boolean;
          };
        };
      };
    };
    if (err?.response?.data?.data?.tenant_code_required) {
      showTenantCode.value = true;
    }
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <AuthenticationForgetPassword
    :form-schema="formSchema"
    :loading="loading"
    @submit="handleSubmit"
  >
    <template v-if="showTenantCode" #form-extend>
      <div class="mb-4">
        <Input
          v-model:value="tenantCode"
          :placeholder="$t('user.auth.tenantCodePlaceholder')"
          size="large"
        >
          <template #prefix>
            <span class="i-lucide-building text-muted-foreground" />
          </template>
        </Input>
      </div>
    </template>
  </AuthenticationForgetPassword>
</template>
