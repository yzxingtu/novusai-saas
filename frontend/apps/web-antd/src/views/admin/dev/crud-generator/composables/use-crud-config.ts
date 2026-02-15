/**
 * CRUD Generator — 响应式配置状态管理
 *
 * 提供全局配置 ref<CrudConfig>，基于 useManualRefHistory 实现 Undo/Redo。
 * 支持 50 步撤销历史。
 */

import { computed, ref, watch } from 'vue';

import { useManualRefHistory } from '@vueuse/core';

import type { CrudConfig, StepWarning, WizardStep } from '../types';

// ============================================================
// 默认配置工厂
// ============================================================

export function createDefaultConfig(): CrudConfig {
  return {
    // Step 1: 基本信息
    module: '',
    table_name: '',
    display_name: '',
    display_name_en: '',
    scope: 'tenant',
    parent_menu: '',
    description: '',

    // 选项
    soft_delete: true,
    drag_sort: false,
    has_status_toggle: true,
    recyclable: true,

    // Step 2: 字段
    fields: [],

    // 关联
    relations: [],

    // 搜索
    search_config: null,

    // 枚举
    enums: [],

    // Step 3: 列表
    list_config: {
      show_checkbox: true,
      show_index: false,
      default_sort: '-created_at',
      row_height: 64,
      stripe: true,
      pager: true,
      toolbar_export: true,
      toolbar_search: true,
    },

    // Step 4: 表单
    form_config: {
      drawer_width: '600px',
      form_type: 'drawer',
      groups: null,
      columns: 1,
      label_width: 120,
    },

    // 操作列
    operations: ['edit', 'delete'],

    // 下拉选项
    selectable: null,

    // 复合索引
    indexes: [],

    // 导入导出
    import_export: null,

    // 权限
    permissions: null,

    // Hooks
    hooks: [],

    // 自定义 Slot
    custom_slots: [],

    // 布局
    layout: {
      variant: 'standard',
      card_fields: null,
      card_cover_field: null,
      card_columns: 3,
      detail_position: 'right',
      detail_width: '40%',
      kanban_group_field: null,
      timeline_date_field: null,
    },

    // 样式
    style: {
      primary_color: null,
      compact: false,
      bordered: true,
      rounded: true,
      header_sticky: true,
      custom_css: null,
    },

    // 动画
    animation: {
      row_enter: true,
      drawer_transition: true,
      status_transition: true,
      skeleton_loading: true,
    },

    // Git
    git: {
      auto_branch: false,
      auto_commit: false,
      commit_message_template:
        'feat({module}): scaffold CRUD for {display_name}',
    },

    // 审计
    audit: {
      enable: true,
      log_fields: null,
      sensitive_fields: [],
    },

    // 测试
    test: {
      generate_unit_tests: true,
      generate_api_tests: true,
      test_data_count: 5,
      custom_fixtures: [],
    },

    // 行内编辑
    inline_edit: {
      enable: false,
      editable_fields: [],
      save_mode: 'cell',
      debounce_ms: 300,
    },

    // 可观测性
    observability: {
      enable_metrics: false,
      enable_tracing: false,
      slow_query_threshold_ms: 1000,
      custom_tags: {},
    },

    // 自然语言查询
    nl_query: {
      enable: false,
      query_fields: [],
      example_queries_zh: [],
      example_queries_en: [],
    },

    // 逻辑编排
    logic_flows: [],
  };
}

// ============================================================
// Composable
// ============================================================

const MAX_HISTORY = 50;

export function useCrudConfig() {
  const config = ref<CrudConfig>(createDefaultConfig());
  const currentStep = ref<WizardStep>(0);
  const isDirty = ref(false);
  const isGenerating = ref(false);

  // Undo/Redo — 手动提交快照，避免高频自动记录
  const { undo, redo, canUndo, canRedo, commit, history } =
    useManualRefHistory(config, {
      capacity: MAX_HISTORY,
      clone: true,
    });

  // 标记 dirty
  watch(
    config,
    () => {
      isDirty.value = true;
    },
    { deep: true },
  );

  /** 提交一个历史快照（在关键操作后调用，如字段增删、Step 切换） */
  function snapshot() {
    commit();
  }

  /** 重置为默认配置 */
  function resetConfig() {
    config.value = createDefaultConfig();
    isDirty.value = false;
    commit();
  }

  /** 从外部数据加载配置（如 AI 生成结果、模板加载） */
  function loadConfig(data: CrudConfig) {
    config.value = { ...createDefaultConfig(), ...data };
    isDirty.value = true;
    commit();
  }

  /** 校验指定步骤的配置完整性（返回警告列表，不阻止前进） */
  function validateStep(step: WizardStep): StepWarning[] {
    const warnings: StepWarning[] = [];
    const c = config.value;

    if (step === 0) {
      if (!c.module) warnings.push({ step: 0, field: 'module', message: 'module_required', severity: 'error' });
      if (!c.table_name) warnings.push({ step: 0, field: 'table_name', message: 'table_required', severity: 'error' });
    } else if (step === 1) {
      if (c.fields.length === 0) warnings.push({ step: 1, message: 'no_fields', severity: 'error' });
    } else if (step === 2) {
      const hasListField = c.fields.some((f) => f.in_list);
      if (!hasListField && c.fields.length > 0) {
        warnings.push({ step: 2, message: 'no_list_fields', severity: 'warning' });
      }
      const searchFields = c.search_config?.fields ?? [];
      for (const sf of searchFields) {
        if (!sf.operator) {
          warnings.push({ step: 2, field: sf.field, message: 'search_no_operator', severity: 'warning' });
        }
      }
    } else if (step === 3) {
      const hasFormField = c.fields.some((f) => f.in_form);
      if (!hasFormField && c.fields.length > 0) {
        warnings.push({ step: 3, message: 'no_form_fields', severity: 'warning' });
      }
      const groups = c.form_config?.groups ?? [];
      for (const g of groups) {
        const fieldNames = new Set(c.fields.map((f) => f.name));
        for (const gf of g.fields ?? []) {
          if (!fieldNames.has(gf)) {
            warnings.push({ step: 3, field: gf, message: 'group_field_missing', severity: 'warning' });
          }
        }
      }
    }

    return warnings;
  }

  const stepWarnings = computed(() => validateStep(currentStep.value));

  /** 跳转到指定步骤 */
  function goToStep(step: WizardStep) {
    snapshot();
    currentStep.value = step;
  }

  /** 下一步 */
  function nextStep() {
    if (currentStep.value < 4) {
      goToStep((currentStep.value + 1) as WizardStep);
    }
  }

  /** 上一步 */
  function prevStep() {
    if (currentStep.value > 0) {
      goToStep((currentStep.value - 1) as WizardStep);
    }
  }

  return {
    config,
    currentStep,
    isDirty,
    isGenerating,

    // Undo/Redo
    undo,
    redo,
    canUndo,
    canRedo,
    snapshot,
    history,

    // 校验
    stepWarnings,
    validateStep,

    // 操作
    resetConfig,
    loadConfig,
    goToStep,
    nextStep,
    prevStep,
    createDefaultConfig,
  };
}

export type UseCrudConfigReturn = ReturnType<typeof useCrudConfig>;
