import type { TableProps } from 'ant-design-vue';

import type { Ref } from 'vue';

import type { AdminSkillInfo } from '#/api/admin/skills';

import { computed, ref, watch } from 'vue';

import { useVbenDrawer } from '@vben/common-ui';

import { message, Modal } from 'ant-design-vue';

import { getSkillPackageSkillsApi } from '#/api/admin/skill-packages';
import {
  deleteSkillApi,
  testSkillApi,
  toggleSkillStatusApi,
} from '#/api/admin/skills';
import ValvesConfigPanel from '#/components/business/valves-config-panel/ValvesConfigPanel.vue';
import { buildPageAIFormExtraData } from '#/composables';
import { $t } from '#/locales';

import SkillForm from '../skills/modules/form.vue';

type UseSkillPackageDetailOptions = {
  loadPackages: () => Promise<void>;
  selectedPackageId: Ref<null | number>;
};

const PAGE_KEY = 'admin.ai.skill-packages';

export function useSkillPackageDetail(options: UseSkillPackageDetailOptions) {
  const skills = ref<AdminSkillInfo[]>([]);
  const skillsLoading = ref(false);

  const valvesConfigPanelRef = ref<InstanceType<
    typeof ValvesConfigPanel
  > | null>(null);

  const [SkillFormDrawer, skillFormApi] = useVbenDrawer({
    connectedComponent: SkillForm,
    destroyOnClose: true,
  });

  async function loadSkills() {
    if (!options.selectedPackageId.value) {
      skills.value = [];
      return;
    }

    skillsLoading.value = true;
    try {
      const response = await getSkillPackageSkillsApi(
        options.selectedPackageId.value,
        {
          'page[size]': 100,
          sort: 'sort_order,-created_at',
        },
      );
      skills.value = response.items;
    } catch {
      skills.value = [];
    } finally {
      skillsLoading.value = false;
    }
  }

  function buildSkillCreateDefaults(overrides: Record<string, unknown> = {}) {
    return {
      package_id: options.selectedPackageId.value,
      type: 'toolkit',
      timeout: 30,
      is_active: true,
      toolkit_content: '',
      valves_config: {},
      kb_ids: [],
      rag_enabled: true,
      rag_top_k: 5,
      rag_score_threshold: 0.5,
      rag_search_mode: 'hybrid',
      rag_rewrite_strategy: 'none',
      rag_reranker_enabled: false,
      rag_context_token_ratio: 0.3,
      ...overrides,
    };
  }

  function openSkillCreateDrawer(overrides: Record<string, unknown> = {}) {
    if (!options.selectedPackageId.value) {
      return {
        success: false,
        message: $t('admin.ai.skillPackage.messages.selectPackageFirst'),
      };
    }

    skillFormApi
      .setData({
        mode: 'add',
        _resource: '/admin/ai/skills',
        ...buildPageAIFormExtraData({
          pageKey: PAGE_KEY,
          defaults: buildSkillCreateDefaults(overrides),
        }),
      })
      .open();

    return { success: true };
  }

  function onCreateSkill() {
    return openSkillCreateDrawer();
  }

  function onEditSkill(row: AdminSkillInfo) {
    skillFormApi
      .setData({
        ...row,
        mode: 'edit',
        _resource: '/admin/ai/skills',
        ...buildPageAIFormExtraData({ pageKey: PAGE_KEY }),
      })
      .open();
  }

  async function onSkillFormSuccess() {
    await loadSkills();
    await options.loadPackages();
  }

  async function onToggleSkillStatus(row: AdminSkillInfo) {
    try {
      await toggleSkillStatusApi(row.id);
      message.success($t('admin.ai.skill.messages.toggleSuccess'));
      await loadSkills();
      await options.loadPackages();
    } catch {
      // handled by interceptor / 错误由请求拦截器处理
    }
  }

  async function onDeleteSkill(row: AdminSkillInfo) {
    Modal.confirm({
      title: $t('admin.common.confirmDelete'),
      onOk: async () => {
        try {
          await deleteSkillApi(row.id);
          message.success($t('common.deleteSuccess'));
          await loadSkills();
          await options.loadPackages();
        } catch {
          // handled by interceptor / 错误由请求拦截器处理
        }
      },
    });
  }

  async function onTestSkill(row: AdminSkillInfo) {
    try {
      const response = await testSkillApi(row.id);
      const detailStr = response.details
        ? `\n\n${JSON.stringify(response.details, null, 2)}`
        : '';

      Modal[response.success ? 'success' : 'error']({
        title: `${row.name} — ${response.success ? $t('admin.ai.skill.messages.testSuccess') : $t('admin.ai.skill.messages.testFailed')}`,
        content: response.message + detailStr,
        width: 520,
      });
    } catch {
      Modal.error({
        title: row.name,
        content: $t('admin.ai.skill.messages.testFailed'),
      });
    }
  }

  function onOpenValvesConfig() {
    valvesConfigPanelRef.value?.open();
  }

  const skillColumns = computed<TableProps['columns']>(() => [
    {
      title: $t('admin.ai.skill.name'),
      dataIndex: 'name',
      key: 'name',
      width: 240,
    },
    {
      title: $t('admin.ai.skill.type'),
      dataIndex: 'type',
      key: 'type',
      width: 120,
      align: 'center',
    },
    {
      title: $t('admin.ai.skill.isActive'),
      dataIndex: 'is_active',
      key: 'is_active',
      width: 100,
      align: 'center',
    },
    {
      title: $t('admin.ai.skill.timeout'),
      dataIndex: 'timeout',
      key: 'timeout',
      width: 100,
      align: 'center',
    },
    {
      title: $t('admin.common.createdAt'),
      dataIndex: 'created_at',
      key: 'created_at',
      width: 140,
    },
    {
      title: $t('admin.common.operation'),
      key: 'action',
      width: 200,
      align: 'center',
    },
  ]);

  watch(options.selectedPackageId, () => {
    void loadSkills();
  });

  return {
    onCreateSkill,
    onDeleteSkill,
    onEditSkill,
    onOpenValvesConfig,
    onSkillFormSuccess,
    onTestSkill,
    onToggleSkillStatus,
    skillColumns,
    SkillFormDrawer,
    skills,
    skillsLoading,
    valvesConfigPanelRef,
  };
}
