<script lang="ts" setup>
import type { VbenFormSchema } from '@vben/common-ui';

import { computed, h, ref } from 'vue';
import { useRouter } from 'vue-router';

import { AuthenticationRegister, z } from '@vben/common-ui';
import { $t } from '@vben/locales';

import { Input, notification } from 'ant-design-vue';

import { userApi } from '#/api';

defineOptions({ name: 'UserRegister' });

const router = useRouter();
const loading = ref(false);
const showTenantCode = ref(false);
const tenantCode = ref('');

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
        default: () =>
          h('span', [
            $t('authentication.agree'),
            h(
              'a',
              {
                class: 'vben-link ml-1 ',
                href: '',
              },
              `${$t('authentication.privacyPolicy')} & ${$t('authentication.terms')}`,
            ),
          ]),
      }),
      rules: z.boolean().refine((value) => !!value, {
        message: $t('authentication.agreeTip'),
      }),
    },
  ];
});

async function handleSubmit(values: Record<string, unknown>) {
  try {
    loading.value = true;

    const result = await userApi.userRegisterApi({
      confirmPassword: values.confirmPassword as string,
      email: values.email as string,
      password: values.password as string,
      tenantCode: showTenantCode.value ? tenantCode.value : undefined,
      username: values.username as string,
    });

    const isPending = result.approvalStatus === 'pending';

    notification.success({
      description: isPending
        ? $t('user.auth.registerPendingDesc')
        : $t('user.auth.registerSuccessDesc'),
      duration: isPending ? 5 : 3,
      message: $t('user.auth.registerSuccess'),
    });

    await router.push('/login');
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
  <AuthenticationRegister
    :form-schema="formSchema"
    :loading="loading"
    @submit="handleSubmit"
  >
    <!-- Tenant code slot -->
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
  </AuthenticationRegister>
</template>
