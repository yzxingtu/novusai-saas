<script lang="ts" setup>
/**
 * 企业端个人中心页面
 *
 * 现代化布局：顶部 Hero 区域（头像+基本信息） + 下方 Tab 内容
 */
import { computed, onMounted, ref } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';
import { useUserStore } from '@vben/stores';

import {
  Button,
  Card,
  Form,
  Input,
  message,
  Spin,
  Tabs,
  Upload,
} from 'ant-design-vue';

import { smartUploadFile } from '#/api/tenant/attachment';
import {
  getTenantAdminInfoApi,
  tenantChangePasswordApi,
  updateTenantProfileApi,
} from '#/api/tenant/auth';
import { getTenantAdminIdentityDetailApi } from '#/api/tenant/admins';
import { IdentityDisplay } from '#/components/business/identity-display';
import { $t } from '#/locales';
import { toAvatarDisplayUrl } from '#/utils/image';

defineOptions({ name: 'TenantProfile' });

const userStore = useUserStore();

const loading = ref(false);
const saving = ref(false);
const avatarUploading = ref(false);
const activeTab = ref('basic');
const passwordSaving = ref(false);

interface ProfileFormState {
  nickname: string;
  email: string;
  phone: string;
  avatar: string;
  username: string;
  tenantName: string;
}

interface TenantProfileIdentityState {
  isActive: boolean;
  isLeader: boolean;
  isOwner: boolean;
  orgNodeName: string;
}

const form = ref<ProfileFormState>({
  nickname: '',
  email: '',
  phone: '',
  avatar: '',
  username: '',
  tenantName: '',
});
const profileId = ref<number | string>('current-tenant-admin');
const identityState = ref<TenantProfileIdentityState>({
  isActive: true,
  isLeader: false,
  isOwner: false,
  orgNodeName: '',
});

const passwordForm = ref({
  oldPassword: '',
  newPassword: '',
  confirmPassword: '',
});

const displayName = computed(
  () => form.value.nickname || form.value.username || '-',
);
const showUsernameLine = computed(
  () => Boolean(form.value.username) && displayName.value !== form.value.username,
);
const showSupplementaryInfo = computed(
  () =>
    showUsernameLine.value ||
    Boolean(form.value.email) ||
    Boolean(form.value.tenantName),
);
const identityModel = computed(() => ({
  avatar: form.value.avatar || undefined,
  id: profileId.value,
  isActive: identityState.value.isActive,
  isLeader: identityState.value.isLeader,
  isOwner: identityState.value.isOwner,
  nickname: form.value.nickname || undefined,
  orgNodeName: identityState.value.orgNodeName || undefined,
  username: form.value.username || undefined,
}));

function applyIdentityState(detail?: {
  is_active?: boolean;
  is_leader?: boolean;
  is_owner?: boolean;
  org_node_name?: null | string;
}) {
  identityState.value = {
    isActive: detail?.is_active ?? true,
    isLeader: Boolean(detail?.is_leader),
    isOwner: Boolean(detail?.is_owner),
    orgNodeName: detail?.org_node_name?.trim() || '',
  };
}

function syncUserStoreProfile(updates: {
  avatar?: string;
  realName?: string;
}) {
  if (!userStore.userInfo) {
    return;
  }
  userStore.setUserInfo({
    ...userStore.userInfo,
    ...updates,
  });
}

function resolveAvatarOverlayClasses() {
  return avatarUploading.value
    ? 'bg-black/40'
    : 'bg-black/0 group-hover:bg-black/40';
}

function resolveAvatarIconClasses() {
  return avatarUploading.value
    ? 'opacity-100'
    : 'opacity-0 group-hover:opacity-100';
}

async function loadProfile() {
  loading.value = true;
  try {
    const info = await getTenantAdminInfoApi();
    profileId.value = info.id;
    let detail:
      | Awaited<ReturnType<typeof getTenantAdminIdentityDetailApi>>
      | undefined;
    try {
      detail = await getTenantAdminIdentityDetailApi(Number(info.id));
    } catch {
      detail = undefined;
    }

    form.value = {
      nickname: detail?.nickname || info.realName || '',
      email: detail?.email || info.email || '',
      phone: detail?.phone || '',
      avatar: detail?.avatar || info.avatar || '',
      username: detail?.username || info.username || '',
      tenantName: info.tenantName || '',
    };
    applyIdentityState(detail);
  } catch {
    message.error($t('tenant.profile.messages.loadFailed'));
  } finally {
    loading.value = false;
  }
}

async function handleSaveBasic() {
  saving.value = true;
  try {
    await updateTenantProfileApi({
      nickname: form.value.nickname || null,
      email: form.value.email || null,
      phone: form.value.phone || null,
    });

    syncUserStoreProfile({
      realName: form.value.nickname || form.value.username,
    });

    message.success($t('tenant.profile.messages.updateSuccess'));
  } catch {
    message.error($t('tenant.profile.messages.updateFailed'));
  } finally {
    saving.value = false;
  }
}

async function handleChangePassword() {
  if (passwordForm.value.newPassword !== passwordForm.value.confirmPassword) {
    message.error($t('shared.profile.validation.passwordMismatch'));
    return;
  }
  passwordSaving.value = true;
  try {
    await tenantChangePasswordApi({
      oldPassword: passwordForm.value.oldPassword,
      newPassword: passwordForm.value.newPassword,
      confirmPassword: passwordForm.value.confirmPassword,
    });
    message.success($t('tenant.profile.messages.passwordChanged'));
    passwordForm.value = {
      oldPassword: '',
      newPassword: '',
      confirmPassword: '',
    };
  } catch {
    message.error($t('tenant.profile.messages.passwordFailed'));
  } finally {
    passwordSaving.value = false;
  }
}

async function handleAvatarUpload(file: File) {
  avatarUploading.value = true;
  try {
    const result = await smartUploadFile({
      file,
      visibility: 'public',
      business_type: 'avatar',
    });
    const attachmentId = String(result.attachment?.id || '');
    if (!attachmentId) throw new Error('Upload failed');
    form.value.avatar = attachmentId;

    // save immediately / 立即保存
    await updateTenantProfileApi({ avatar: attachmentId });

    syncUserStoreProfile({
      avatar: toAvatarDisplayUrl(attachmentId),
    });

    message.success($t('tenant.profile.messages.avatarUpdated'));
  } catch {
    message.error($t('tenant.profile.messages.avatarFailed'));
  } finally {
    avatarUploading.value = false;
  }
}

function beforeAvatarUpload(file: File) {
  const isImage = file.type.startsWith('image/');
  if (!isImage) {
    message.error($t('tenant.profile.messages.avatarTypeError'));
    return false;
  }
  const isLt2M = file.size / 1024 / 1024 < 2;
  if (!isLt2M) {
    message.error($t('tenant.profile.messages.avatarSizeError'));
    return false;
  }
  handleAvatarUpload(file);
  return false;
}

onMounted(() => {
  loadProfile();
});
</script>

<template>
  <Page auto-content-height content-class="flex flex-col gap-6">
    <Spin :spinning="loading">
      <!-- Hero Section -->
      <Card class="overflow-hidden border-0 shadow-sm">
        <div
          class="via-primary/3 rounded-xl bg-gradient-to-r from-primary/5 to-transparent p-8"
        >
          <div class="flex items-start justify-start">
            <div class="relative w-full">
              <IdentityDisplay
                :avatar-size="96"
                :model="identityModel"
                :show-role-badge="false"
                :show-status-badge="false"
                :show-user-type-badge="false"
                class="w-full"
              >
                <template #after>
                  <div
                    v-if="showSupplementaryInfo"
                    class="flex w-full flex-col items-start gap-2 text-left"
                  >
                    <p
                      v-if="showUsernameLine"
                      class="text-sm text-muted-foreground"
                    >
                      @{{ form.username }}
                    </p>
                    <div
                      class="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-muted-foreground"
                    >
                      <span
                        v-if="form.email"
                        class="inline-flex items-center gap-1.5"
                      >
                        <IconifyIcon icon="lucide:mail" class="size-4" />
                        <span class="truncate">{{ form.email }}</span>
                      </span>
                      <span
                        v-if="form.tenantName"
                        class="inline-flex items-center gap-1.5"
                      >
                        <IconifyIcon
                          icon="lucide:building-2"
                          class="size-4"
                        />
                        <span class="truncate">{{ form.tenantName }}</span>
                      </span>
                    </div>
                  </div>
                </template>
              </IdentityDisplay>

              <Upload
                :show-upload-list="false"
                :before-upload="beforeAvatarUpload"
                accept="image/*"
                class="absolute left-0 top-0"
              >
                <div class="group relative size-24 cursor-pointer rounded-full">
                  <div
                    class="absolute inset-0 rounded-full transition-all"
                    :class="resolveAvatarOverlayClasses()"
                  ></div>
                  <div
                    class="absolute inset-0 flex items-center justify-center transition-all"
                    :class="resolveAvatarIconClasses()"
                  >
                    <Spin v-if="avatarUploading" size="small" />
                    <IconifyIcon
                      v-else
                      icon="lucide:camera"
                      class="size-6 text-white"
                    />
                  </div>
                </div>
              </Upload>
            </div>
          </div>
        </div>
      </Card>

      <!-- Content Tabs -->
      <Card class="mt-6 border-0 shadow-sm">
        <Tabs v-model:active-key="activeTab">
          <Tabs.TabPane key="basic" :tab="$t('tenant.profile.tabs.basic')">
            <div class="max-w-lg py-4">
              <Form layout="vertical">
                <Form.Item :label="$t('shared.profile.nickname')">
                  <Input
                    v-model:value="form.nickname"
                    :placeholder="
                      $t('shared.profile.placeholder.inputNickname')
                    "
                    size="large"
                  />
                </Form.Item>
                <Form.Item :label="$t('shared.profile.email')">
                  <Input
                    v-model:value="form.email"
                    :placeholder="$t('shared.profile.placeholder.inputEmail')"
                    size="large"
                  />
                </Form.Item>
                <Form.Item :label="$t('shared.profile.phone')">
                  <Input
                    v-model:value="form.phone"
                    :placeholder="$t('shared.profile.placeholder.inputPhone')"
                    size="large"
                  />
                </Form.Item>
                <Form.Item>
                  <Button
                    type="primary"
                    :loading="saving"
                    size="large"
                    @click="handleSaveBasic"
                  >
                    <template #icon>
                      <IconifyIcon icon="lucide:save" class="size-4" />
                    </template>
                    {{ $t('tenant.profile.save') }}
                  </Button>
                </Form.Item>
              </Form>
            </div>
          </Tabs.TabPane>

          <Tabs.TabPane
            key="password"
            :tab="$t('tenant.profile.tabs.password')"
          >
            <div class="max-w-lg py-4">
              <Form layout="vertical">
                <Form.Item :label="$t('shared.profile.oldPassword')">
                  <Input.Password
                    v-model:value="passwordForm.oldPassword"
                    :placeholder="
                      $t('shared.profile.placeholder.inputOldPassword')
                    "
                    size="large"
                  />
                </Form.Item>
                <Form.Item :label="$t('shared.profile.newPassword')">
                  <Input.Password
                    v-model:value="passwordForm.newPassword"
                    :placeholder="
                      $t('shared.profile.placeholder.inputNewPassword')
                    "
                    size="large"
                  />
                </Form.Item>
                <Form.Item :label="$t('shared.profile.confirmPassword')">
                  <Input.Password
                    v-model:value="passwordForm.confirmPassword"
                    :placeholder="
                      $t('shared.profile.placeholder.confirmNewPassword')
                    "
                    size="large"
                  />
                </Form.Item>
                <Form.Item>
                  <Button
                    type="primary"
                    :loading="passwordSaving"
                    size="large"
                    @click="handleChangePassword"
                  >
                    <template #icon>
                      <IconifyIcon icon="lucide:key" class="size-4" />
                    </template>
                    {{ $t('tenant.profile.changePassword') }}
                  </Button>
                </Form.Item>
              </Form>
            </div>
          </Tabs.TabPane>
        </Tabs>
      </Card>
    </Spin>
  </Page>
</template>
