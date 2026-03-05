<script lang="ts" setup>
/**
 * 租户端个人中心页面
 *
 * 现代化布局：顶部 Hero 区域（头像+基本信息） + 下方 Tab 内容
 */
import { computed, onMounted, ref } from 'vue';

import { Page } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';
import { useUserStore } from '@vben/stores';

import {
  Avatar,
  Button,
  Card,
  Form,
  Input,
  message,
  Spin,
  Tabs,
  Upload,
} from 'ant-design-vue';

import { uploadAttachmentApi } from '#/api/tenant/attachment';
import {
  getTenantAdminInfoApi,
  tenantChangePasswordApi,
  updateTenantProfileApi,
} from '#/api/tenant/auth';
import { $t } from '#/locales';
import { getProcessedImageUrl, toAvatarDisplayUrl } from '#/utils/image';

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
  roleName: string;
  tenantName: string;
  createdAt: string;
}

const form = ref<ProfileFormState>({
  nickname: '',
  email: '',
  phone: '',
  avatar: '',
  username: '',
  roleName: '',
  tenantName: '',
  createdAt: '',
});

const passwordForm = ref({
  oldPassword: '',
  newPassword: '',
  confirmPassword: '',
});

const displayName = computed(
  () => form.value.nickname || form.value.username || '-',
);
const avatarSrc = computed(() => {
  const val = form.value.avatar || userStore.userInfo?.avatar || '';
  if (!val) return '';
  const id = Number(val);
  if (Number.isFinite(id) && id > 0) {
    return getProcessedImageUrl(id, { preset: 'avatar' });
  }
  return val;
});
const avatarInitial = computed(() =>
  (displayName.value || '?').charAt(0).toUpperCase(),
);

async function loadProfile() {
  loading.value = true;
  try {
    const info = await getTenantAdminInfoApi();
    form.value = {
      nickname: info.realName || '',
      email: info.email || '',
      phone: '',
      avatar: info.avatar || '',
      username: info.username || '',
      roleName: '',
      tenantName: info.tenantName || '',
      createdAt: '',
    };
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

    // sync to userStore
    if (userStore.userInfo) {
      userStore.setUserInfo({
        ...userStore.userInfo,
        realName: form.value.nickname || form.value.username,
      });
    }

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
    const result = await uploadAttachmentApi({
      file,
      visibility: 'public',
      business_type: 'avatar',
    });
    const attachmentId = String(result.attachment?.id || '');
    if (!attachmentId) throw new Error('Upload failed');
    form.value.avatar = attachmentId;

    // save immediately
    await updateTenantProfileApi({ avatar: attachmentId });

    if (userStore.userInfo) {
      userStore.setUserInfo({
        ...userStore.userInfo,
        avatar: toAvatarDisplayUrl(attachmentId),
      });
    }

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
          <div class="flex items-center gap-8">
            <!-- Avatar with upload overlay -->
            <div class="group relative flex-shrink-0">
              <Upload
                :show-upload-list="false"
                :before-upload="beforeAvatarUpload"
                accept="image/*"
              >
                <div class="relative cursor-pointer">
                  <Avatar
                    v-if="avatarSrc"
                    :src="avatarSrc"
                    :size="96"
                    class="shadow-lg ring-4 ring-background transition-all group-hover:ring-primary/20"
                  />
                  <Avatar
                    v-else
                    :size="96"
                    class="bg-primary/10 text-2xl font-bold text-primary shadow-lg ring-4 ring-background transition-all group-hover:ring-primary/20"
                  >
                    {{ avatarInitial }}
                  </Avatar>
                  <!-- Upload overlay -->
                  <div
                    class="absolute inset-0 flex items-center justify-center rounded-full bg-black/40 opacity-0 transition-all group-hover:opacity-100"
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

            <!-- User info -->
            <div class="min-w-0 flex-1">
              <h2 class="mb-1 text-2xl font-bold text-foreground">
                {{ displayName }}
              </h2>
              <p class="mb-3 text-sm text-muted-foreground">
                @{{ form.username }}
              </p>
              <div class="flex flex-wrap items-center gap-4 text-sm">
                <div
                  v-if="form.email"
                  class="flex items-center gap-1.5 text-muted-foreground"
                >
                  <IconifyIcon icon="lucide:mail" class="size-4" />
                  <span>{{ form.email }}</span>
                </div>
                <div
                  v-if="form.tenantName"
                  class="flex items-center gap-1.5 text-muted-foreground"
                >
                  <IconifyIcon icon="lucide:building-2" class="size-4" />
                  <span>{{ form.tenantName }}</span>
                </div>
              </div>
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
