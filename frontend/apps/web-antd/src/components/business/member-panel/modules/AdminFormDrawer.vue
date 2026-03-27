<script lang="ts" setup>
import type { MemberRoleOption, OrgTreeApi } from '../data';
import type { MemberPanelMember } from '../types';

/**
 * Admin Create/Edit Form Drawer
 * 管理员新建/编辑表单抽屉
 *
 * Uses custom submit logic for member CRUD under the selected org node.
 * 使用自定义提交逻辑处理当前组织节点下的成员 CRUD。
 */
import type { adminApi, tenantApi } from '#/api';

import { computed, ref } from 'vue';

import { useVbenDrawer } from '@vben/common-ui';
import { IconifyIcon } from '@vben/icons';

import { Avatar, message, Spin, Upload } from 'ant-design-vue';

import { useVbenForm } from '#/adapter/form';
import { adminApi as admin, tenantApi as tenant } from '#/api';
import { $t } from '#/locales';
import { toAttachmentImageUrl } from '#/utils/image';

import { getAdminFormDefaults, useAdminFormSchema } from '../data';

const props = withDefaults(
  defineProps<{
    /** API prefix / API 前缀 */
    apiPrefix?: 'admin' | 'tenant';
    /** Current node ID / 当前节点 ID */
    nodeId?: null | number;
    /** Node name (for display) / 节点名称 */
    nodeName?: string;
    /** Org tree API (select node in edit mode) / 组织树 API */
    orgTreeApi?: OrgTreeApi;
  }>(),
  {
    nodeId: null,
    nodeName: '',
    apiPrefix: 'admin',
    orgTreeApi: undefined,
  },
);
const emits = defineEmits<{ success: [] }>();
const avatarValue = ref('');
const avatarUploading = ref(false);

const avatarSrc = computed(() => {
  const val = avatarValue.value;
  return toAttachmentImageUrl(val, { preset: 'avatar' });
});

const avatarInitial = computed(() => {
  const name = currentNickname.value || currentUsername.value || '?';
  return name.charAt(0).toUpperCase();
});

const currentNickname = ref('');
const currentUsername = ref('');

async function handleAvatarUpload(file: File) {
  avatarUploading.value = true;
  try {
    const result =
      props.apiPrefix === 'tenant'
        ? await tenant.smartUploadFile({
            file,
            visibility: 'public',
            business_type: 'avatar',
          })
        : await admin.smartUploadFile({
            file,
            visibility: 'public',
            business_type: 'avatar',
          });
    const attachmentId = String(
      (result as { attachment?: { id?: number } }).attachment?.id || '',
    );
    if (!attachmentId) throw new Error('Upload failed');
    avatarValue.value = attachmentId;
    message.success($t('admin.profile.messages.avatarUpdated'));
  } catch {
    message.error($t('admin.profile.messages.avatarFailed'));
  } finally {
    avatarUploading.value = false;
  }
}

function beforeAvatarUpload(file: File) {
  const isImage = file.type.startsWith('image/');
  if (!isImage) {
    message.error($t('admin.profile.messages.avatarTypeError'));
    return false;
  }
  const isLt2M = file.size / 1024 / 1024 < 2;
  if (!isLt2M) {
    message.error($t('admin.profile.messages.avatarSizeError'));
    return false;
  }
  handleAvatarUpload(file);
  return false;
}

const isEdit = ref(false);
const recordId = ref<number>();
const sourceOrgNodeId = ref<null | number>(null);

interface MemberFormValues {
  email?: string;
  is_active?: boolean;
  nickname?: null | string;
  org_node_id?: null | number;
  password?: string;
  phone?: null | string;
  role_id?: null | number;
  username?: string;
}

async function loadRoleOptions(
  currentMember?: MemberPanelMember,
): Promise<MemberRoleOption[]> {
  if (props.apiPrefix !== 'tenant') {
    return [];
  }

  const roles = await tenant.getAllTenantPermissionRoleListApi();

  const options = roles
    .filter((role) => role.isActive)
    .map((role) => ({
      label: role.name,
      value: role.id,
    }));

  if (
    currentMember?.roleId &&
    currentMember.roleName &&
    !options.some((option) => option.value === currentMember.roleId)
  ) {
    options.unshift({
      label: currentMember.roleName,
      value: currentMember.roleId,
    });
  }

  return options;
}

// Form / 表单
const [Form, formApi] = useVbenForm({
  showDefaultActions: false,
});

// Drawer / 抽屉
const [Drawer, drawerApi] = useVbenDrawer({
  async onConfirm() {
    const { valid } = await formApi.validate();
    if (!valid) return;

    const values = (await formApi.getValues()) as MemberFormValues;
    const selectedOrgNodeId =
      values.org_node_id ?? sourceOrgNodeId.value ?? props.nodeId ?? null;

    // Build request body / 构造请求体
    const baseData = {
      email: values.email,
      phone: values.phone || null,
      nickname: values.nickname || null,
      is_active: values.is_active ?? true,
      ...(isEdit.value && avatarValue.value
        ? { avatar: avatarValue.value }
        : {}),
    };

    drawerApi.lock();
    try {
      if (isEdit.value && recordId.value) {
        const targetOrgNodeId = sourceOrgNodeId.value ?? props.nodeId;
        if (typeof targetOrgNodeId !== 'number') {
          message.error($t('shared.memberPanel.selectNodeFirst'));
          drawerApi.unlock();
          return;
        }

        // Update member under the selected org node / 更新当前组织节点下的成员
        const data = {
          ...baseData,
          org_node_id: selectedOrgNodeId,
          ...(props.apiPrefix === 'tenant'
            ? { role_id: values.role_id ?? null }
            : {}),
        };
        await (props.apiPrefix === 'tenant'
          ? tenant.updateTenantMemberApi(
              targetOrgNodeId,
              recordId.value,
              data as tenantApi.TenantUpdateMemberRequest,
              {
                showSuccessMessage: true,
                successMessage: $t('ui.actionMessage.updateSuccess'),
              },
            )
          : admin.updateMemberApi(
              targetOrgNodeId,
              recordId.value,
              data as adminApi.UpdateMemberRequest,
              {
                showSuccessMessage: true,
                successMessage: $t('ui.actionMessage.updateSuccess'),
              },
            ));
      } else {
        if (typeof selectedOrgNodeId !== 'number') {
          message.error($t('shared.memberPanel.selectNodeFirst'));
          drawerApi.unlock();
          return;
        }

        // Create member / 创建成员
        const data = {
          ...baseData,
          username: values.username,
          password: values.password,
          org_node_id: selectedOrgNodeId,
          ...(props.apiPrefix === 'tenant'
            ? { role_id: values.role_id ?? null }
            : {}),
        };
        await (props.apiPrefix === 'tenant'
          ? tenant.createTenantMemberApi(
              selectedOrgNodeId,
              data as tenantApi.TenantCreateMemberRequest,
              {
                showSuccessMessage: true,
                successMessage: $t('ui.actionMessage.createSuccess'),
              },
            )
          : admin.createMemberApi(
              selectedOrgNodeId,
              data as adminApi.CreateMemberRequest,
              {
                showSuccessMessage: true,
                successMessage: $t('ui.actionMessage.createSuccess'),
              },
            ));
      }
      emits('success');
      drawerApi.close();
    } catch {
      drawerApi.unlock();
    }
  },

  async onOpenChange(isOpen) {
    if (!isOpen) return;

    const data = drawerApi.getData() as
      | (MemberPanelMember & { mode?: string })
      | undefined;
    isEdit.value = data?.mode === 'edit';
    recordId.value = data?.id;
    sourceOrgNodeId.value = data?.orgNodeId ?? props.nodeId ?? null;

    await formApi.resetForm();

    let roleOptions: MemberRoleOption[] = [];
    try {
      roleOptions = await loadRoleOptions(data);
    } catch {
      roleOptions = [];
    }

    // Update schema / 更新 schema
    formApi.setState({
      schema: useAdminFormSchema({
        apiPrefix: props.apiPrefix,
        isEdit: isEdit.value,
        nodeName: data?.orgNodeName ?? props.nodeName,
        nodeId: data?.orgNodeId ?? props.nodeId,
        orgTreeApi: props.orgTreeApi,
        roleOptions,
      }),
    });

    // Fill form data / 填充表单数据
    if (isEdit.value && data) {
      avatarValue.value = data.avatar || '';
      currentNickname.value = data.nickname || '';
      currentUsername.value = data.username || '';
      formApi.setValues({
        username: data.username,
        email: data.email,
        nickname: data.nickname,
        is_active: data.isActive,
        org_node_id: data.orgNodeId ?? props.nodeId,
        ...(props.apiPrefix === 'tenant' ? { role_id: data.roleId } : {}),
        org_node_display:
          data.orgNodeName || props.nodeName || $t('shared.common.notAssigned'),
      });
    } else {
      avatarValue.value = '';
      currentNickname.value = '';
      currentUsername.value = '';
      // Create mode defaults / 新建模式默认值
      formApi.setValues(
        getAdminFormDefaults(props.apiPrefix, props.nodeName, props.nodeId),
      );
    }
  },
});

// Title / 标题
const title = computed(() =>
  isEdit.value
    ? $t('admin.system.admin.edit')
    : $t('admin.system.admin.create'),
);

// Open create form / 打开创建表单
function openCreate() {
  drawerApi.setData({ mode: 'add' }).open();
}

// Open edit form / 打开编辑表单
function openEdit(record: MemberPanelMember) {
  drawerApi.setData({ ...record, mode: 'edit' }).open();
}

defineExpose({ openCreate, openEdit });
</script>

<template>
  <Drawer :title="title" class="w-[400px]">
    <!-- Avatar upload section (edit mode) -->
    <div v-if="isEdit" class="mb-6 flex justify-center">
      <div class="group relative">
        <Upload
          :show-upload-list="false"
          :before-upload="beforeAvatarUpload"
          accept="image/*"
        >
          <div class="relative cursor-pointer">
            <Avatar
              v-if="avatarSrc"
              :src="avatarSrc"
              :size="80"
              class="shadow-lg ring-4 ring-background transition-all group-hover:ring-primary/20"
            />
            <Avatar
              v-else
              :size="80"
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
                class="size-5 text-white"
              />
            </div>
          </div>
        </Upload>
      </div>
    </div>
    <Form />
  </Drawer>
</template>
