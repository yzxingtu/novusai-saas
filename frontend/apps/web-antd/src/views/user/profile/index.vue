<script setup lang="ts">
/**
 * 用户个人中心
 */
import type { UserProfileInfo } from '#/api/user/auth';

import { computed, onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';

import { VbenAvatar } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';
import { preferences } from '@vben/preferences';
import { useUserStore } from '@vben/stores';

import {
  Button,
  Form,
  FormItem,
  Input,
  message,
  Radio,
  RadioGroup,
  Spin,
  Tabs,
  TabPane,
} from 'ant-design-vue';

import { getUserProfileApi, updateUserProfileApi } from '#/api/user/auth';
import { ImageUpload } from '#/components';
import { $t } from '#/locales';

defineOptions({ name: 'UserProfile' });

const router = useRouter();
const userStore = useUserStore();

const loading = ref(false);
const saving = ref(false);
const activeTab = ref('basic');
const profile = ref<UserProfileInfo | null>(null);

const formState = reactive({
  avatarId: '',
  nickname: '',
  email: '',
  phone: '',
  gender: 0,
});

const avatar = computed(() => {
  return (
    profile.value?.avatar ||
    userStore.userInfo?.avatar ||
    preferences.app.defaultAvatar
  );
});

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

function goToChangePassword() {
  router.push('/profile/change-password');
}

onMounted(() => {
  loadProfile();
});
</script>

<template>
  <Spin :spinning="loading">
    <div class="space-y-6">
      <!-- Profile Header -->
      <div
        class="relative overflow-hidden rounded-xl border border-border bg-gradient-to-r from-primary/8 via-primary/4 to-transparent p-6 sm:p-8"
      >
        <div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:gap-6">
          <VbenAvatar
            :src="avatar"
            :alt="displayName"
            class="size-20 shrink-0 rounded-full ring-2 ring-primary/20 sm:size-24"
          />
          <div class="flex-1">
            <h1 class="text-xl font-bold text-foreground sm:text-2xl">
              {{ displayName }}
            </h1>
            <p class="mt-1 text-sm text-muted-foreground">
              @{{ profile?.username }}
            </p>
            <div
              class="mt-2 flex flex-wrap gap-3 text-xs text-muted-foreground"
            >
              <span class="flex items-center gap-1">
                <IconifyIcon icon="lucide:shield" class="size-3.5" />
                {{ profile?.roleName || $t('user.dashboard.noRole') }}
              </span>
              <span class="flex items-center gap-1">
                <IconifyIcon icon="lucide:calendar" class="size-3.5" />
                {{ formattedCreatedAt }}
              </span>
              <span class="flex items-center gap-1">
                <IconifyIcon icon="lucide:clock" class="size-3.5" />
                {{ formattedLastLogin }}
              </span>
            </div>
          </div>
        </div>
        <!-- Decorative -->
        <div
          class="absolute -right-8 -top-8 size-32 rounded-full bg-primary/5"
        />
      </div>

      <!-- Tabs -->
      <Tabs v-model:activeKey="activeTab">
        <!-- Basic Info Tab -->
        <TabPane key="basic">
          <template #tab>
            <span class="flex items-center gap-1.5">
              <IconifyIcon icon="lucide:user" class="size-4" />
              {{ $t('user.profile.edit') }}
            </span>
          </template>
          <div class="rounded-lg border border-border bg-card p-6">
            <Form
              layout="vertical"
              :model="formState"
              class="mx-auto max-w-lg"
            >
              <FormItem :label="$t('user.profile.avatar')">
                <ImageUpload
                  v-model="formState.avatarId"
                  endpoint="user"
                />
              </FormItem>

              <FormItem :label="$t('user.profile.username')">
                <Input
                  :value="profile?.username"
                  disabled
                  class="!bg-accent/50"
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

              <FormItem>
                <Button
                  type="primary"
                  :loading="saving"
                  @click="handleSaveProfile"
                >
                  {{ $t('common.save') }}
                </Button>
              </FormItem>
            </Form>
          </div>
        </TabPane>

        <!-- Security Tab -->
        <TabPane key="security">
          <template #tab>
            <span class="flex items-center gap-1.5">
              <IconifyIcon icon="lucide:shield" class="size-4" />
              {{ $t('user.profile.security') }}
            </span>
          </template>
          <div class="rounded-lg border border-border bg-card p-6">
            <div class="mx-auto max-w-lg space-y-4">
              <!-- Change Password Card -->
              <div
                class="flex items-center justify-between rounded-lg border border-border p-4"
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
                    <h3 class="text-sm font-medium text-foreground">
                      {{ $t('user.profile.changePassword') }}
                    </h3>
                    <p class="text-xs text-muted-foreground">
                      {{ $t('user.profile.changePasswordDesc') }}
                    </p>
                  </div>
                </div>
                <Button @click="goToChangePassword">
                  {{ $t('user.profile.changePassword') }}
                </Button>
              </div>
            </div>
          </div>
        </TabPane>
      </Tabs>
    </div>
  </Spin>
</template>
