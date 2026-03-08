<script setup lang="ts">
/**
 * 用户个人资料页面 - 现代化设计
 */
import type { UserProfileInfo } from '#/api/user/auth';

import { computed, onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';

import { IconifyIcon } from '@vben/icons';
import { preferences } from '@vben/preferences';
import { useUserStore } from '@vben/stores';

import {
  Alert,
  Avatar,
  Button,
  Form,
  FormItem,
  Input,
  message,
  Radio,
  RadioGroup,
  Spin,
  Upload,
} from 'ant-design-vue';

import { smartUploadFile } from '#/api/user/attachment';
import { getUserProfileApi, updateUserProfileApi } from '#/api/user/auth';
import { $t } from '#/locales';
import { usePublicConfigStore } from '#/store/shared/public-config';
import { getProcessedImageUrl, toAvatarDisplayUrl } from '#/utils/image';

defineOptions({ name: 'UserProfile' });

const router = useRouter();
const userStore = useUserStore();
const publicConfigStore = usePublicConfigStore();

const canEdit = computed(() => publicConfigStore.isProfileEditAllowed);

const loading = ref(false);
const saving = ref(false);
const avatarUploading = ref(false);
const profile = ref<UserProfileInfo | null>(null);

const formState = reactive({
  avatarId: '',
  nickname: '',
  email: '',
  phone: '',
  gender: 0,
});

const avatarSrc = computed(() => {
  const val = formState.avatarId || profile.value?.avatar || '';
  if (!val) return userStore.userInfo?.avatar || preferences.app.defaultAvatar;
  const id = Number(val);
  if (Number.isFinite(id) && id > 0) {
    return getProcessedImageUrl(id, { preset: 'avatar' });
  }
  return val;
});

const avatarInitial = computed(() =>
  (displayName.value || '?').charAt(0).toUpperCase(),
);

const displayName = computed(() => {
  return (
    profile.value?.nickname ||
    profile.value?.username ||
    userStore.userInfo?.realName ||
    ''
  );
});

const formattedCreatedAt = computed(() => {
  if (!profile.value?.createdAt) return '-';
  return new Date(profile.value.createdAt).toLocaleDateString();
});

const formattedLastLogin = computed(() => {
  if (!profile.value?.lastLoginAt) return '-';
  return new Date(profile.value.lastLoginAt).toLocaleString();
});

function syncFormFromProfile(data: UserProfileInfo) {
  formState.avatarId = data.avatar || '';
  formState.nickname = data.nickname || '';
  formState.email = data.email || '';
  formState.phone = data.phone || '';
  formState.gender = data.gender ?? 0;
}

async function loadProfile() {
  loading.value = true;
  try {
    const data = await getUserProfileApi();
    profile.value = data;
    syncFormFromProfile(data);
  } catch {
    message.error($t('common.loadFailed'));
  } finally {
    loading.value = false;
  }
}

async function handleSaveProfile() {
  saving.value = true;
  try {
    const data = await updateUserProfileApi({
      avatar: formState.avatarId || undefined,
      nickname: formState.nickname || undefined,
      email: formState.email || undefined,
      phone: formState.phone || undefined,
      gender: formState.gender,
    });
    profile.value = data;
    syncFormFromProfile(data);
    message.success($t('user.profile.messages.updateSuccess'));

    // Update userStore so navbar reflects changes
    if (userStore.userInfo) {
      userStore.setUserInfo({
        ...userStore.userInfo,
        realName: data.nickname || data.username,
        avatar: data.avatar || '',
      });
    }
  } catch {
    message.error($t('common.saveFailed'));
  } finally {
    saving.value = false;
  }
}

async function handleAvatarUpload(file: File) {
  avatarUploading.value = true;
  try {
    const result = await smartUploadFile({
      file,
      visibility: 'public',
    });
    const attachmentId = String(result.attachment?.id || '');
    if (!attachmentId) throw new Error('Upload failed');
    formState.avatarId = attachmentId;

    // save immediately
    const data = await updateUserProfileApi({ avatar: attachmentId });
    profile.value = data;

    if (userStore.userInfo) {
      userStore.setUserInfo({
        ...userStore.userInfo,
        avatar: toAvatarDisplayUrl(attachmentId),
      });
    }

    message.success($t('user.profile.messages.avatarUpdated'));
  } catch {
    message.error($t('user.profile.messages.avatarFailed'));
  } finally {
    avatarUploading.value = false;
  }
}

function beforeAvatarUpload(file: File) {
  const isImage = file.type.startsWith('image/');
  if (!isImage) {
    message.error($t('user.profile.messages.avatarTypeError'));
    return false;
  }
  const isLt2M = file.size / 1024 / 1024 < 2;
  if (!isLt2M) {
    message.error($t('user.profile.messages.avatarSizeError'));
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
  <Spin :spinning="loading">
    <div class="space-y-6">
      <!-- Profile Hero Card -->
      <div
        class="relative overflow-hidden rounded-xl border border-border bg-card p-6"
      >
        <div
          class="absolute inset-0 bg-gradient-to-br from-primary/6 via-transparent to-primary/3"
        />
        <div class="relative flex flex-col gap-5 sm:flex-row sm:items-center sm:gap-6">
          <div class="group relative flex-shrink-0">
            <Upload
              :show-upload-list="false"
              :before-upload="beforeAvatarUpload"
              accept="image/*"
              :disabled="!canEdit"
            >
              <div class="relative cursor-pointer">
                <Avatar
                  v-if="avatarSrc"
                  :src="avatarSrc"
                  :size="96"
                  class="shadow-lg ring-2 ring-background transition-all group-hover:ring-primary/20"
                />
                <Avatar
                  v-else
                  :size="96"
                  class="bg-primary/10 text-2xl font-bold text-primary shadow-lg ring-2 ring-background transition-all group-hover:ring-primary/20"
                >
                  {{ avatarInitial }}
                </Avatar>
                <!-- Upload overlay -->
                <div
                  v-if="canEdit"
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
          <div class="flex-1 space-y-2">
            <div>
              <h2 class="text-xl font-bold text-foreground sm:text-2xl">
                {{ displayName }}
              </h2>
              <p class="text-sm text-muted-foreground">
                @{{ profile?.username }}
              </p>
            </div>
            <div class="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
              <span
                class="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-2.5 py-1 font-medium text-primary"
              >
                <IconifyIcon icon="lucide:shield" class="size-3" />
                {{ profile?.roleName || $t('user.dashboard.noRole') }}
              </span>
              <span class="inline-flex items-center gap-1">
                <IconifyIcon icon="lucide:calendar" class="size-3.5" />
                {{ formattedCreatedAt }}
              </span>
              <span class="inline-flex items-center gap-1">
                <IconifyIcon icon="lucide:clock" class="size-3.5" />
                {{ formattedLastLogin }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Profile Edit Disabled Alert -->
      <Alert
        v-if="!canEdit"
        type="warning"
        show-icon
        :message="$t('user.profile.editDisabled')"
        class="rounded-xl"
      />

      <!-- Basic Info Section -->
      <div class="rounded-xl border border-border bg-card">
        <div class="border-b border-border px-6 py-4">
          <h3 class="text-base font-semibold text-foreground">
            {{ $t('user.profile.edit') }}
          </h3>
        </div>
        <div class="px-6 py-5">
          <Form
            layout="vertical"
            :model="formState"
            :disabled="!canEdit"
            class="max-w-lg"
          >
            <FormItem :label="$t('user.profile.username')">
              <Input
                :value="profile?.username"
                disabled
                class="!bg-muted/50 !text-muted-foreground"
              />
            </FormItem>

            <FormItem :label="$t('user.profile.nickname')">
              <Input
                v-model:value="formState.nickname"
                :placeholder="$t('user.profile.placeholder.inputNickname')"
                allow-clear
              />
            </FormItem>

            <FormItem :label="$t('user.profile.email')">
              <Input
                v-model:value="formState.email"
                :placeholder="$t('user.profile.placeholder.inputEmail')"
                allow-clear
              />
            </FormItem>

            <FormItem :label="$t('user.profile.phone')">
              <Input
                v-model:value="formState.phone"
                :placeholder="$t('user.profile.placeholder.inputPhone')"
                allow-clear
              />
            </FormItem>

            <FormItem :label="$t('user.profile.gender')">
              <RadioGroup v-model:value="formState.gender">
                <Radio :value="0">{{ $t('user.profile.genderUnknown') }}</Radio>
                <Radio :value="1">{{ $t('user.profile.genderMale') }}</Radio>
                <Radio :value="2">{{ $t('user.profile.genderFemale') }}</Radio>
              </RadioGroup>
            </FormItem>
          </Form>
        </div>
        <div v-if="canEdit" class="flex items-center justify-end border-t border-border px-6 py-4">
          <Button
            type="primary"
            :loading="saving"
            @click="handleSaveProfile"
          >
            <span class="flex items-center gap-1.5">
              <IconifyIcon icon="lucide:save" class="size-4" />
              {{ $t('common.save') }}
            </span>
          </Button>
        </div>
      </div>

      <!-- Security Section -->
      <div class="rounded-xl border border-border bg-card">
        <div class="border-b border-border px-6 py-4">
          <h3 class="text-base font-semibold text-foreground">
            {{ $t('user.profile.security') }}
          </h3>
        </div>
        <div class="px-6 py-5">
          <div
            class="flex items-center justify-between rounded-lg border border-border p-4 transition-colors hover:border-primary/30"
          >
            <div class="flex items-center gap-3">
              <div
                class="flex size-10 items-center justify-center rounded-lg bg-warning/10"
              >
                <IconifyIcon
                  icon="lucide:key-round"
                  class="size-5 text-warning"
                />
              </div>
              <div>
                <h4 class="text-sm font-medium text-foreground">
                  {{ $t('user.profile.changePassword') }}
                </h4>
                <p class="text-xs text-muted-foreground">
                  {{ $t('user.profile.changePasswordDesc') }}
                </p>
              </div>
            </div>
            <Button @click="router.push('/settings/password')">
              {{ $t('user.profile.changePassword') }}
            </Button>
          </div>
        </div>
      </div>
    </div>
  </Spin>
</template>
