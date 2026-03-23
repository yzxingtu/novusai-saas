import type {
  PublishTemplatePayload,
  WorkflowBuilderCapability,
  WorkflowTemplateDetail,
  WorkflowTemplateSummary,
} from '../../../types/admin';

import { $t } from '@novus/plugin-shared';

import { ADMIN_I18N_PREFIX } from '../shared/constants';

interface FilterOption {
  label: string;
  value: string;
}

export interface EditorCapabilityCategory {
  code: string;
  descriptionKey: string;
  icon: string;
  titleKey: string;
}

export function getTemplateStatusOptions(): FilterOption[] {
  return [
    {
      value: 'draft',
      label: $t(`${ADMIN_I18N_PREFIX}.status.template.draft`),
    },
    {
      value: 'published',
      label: $t(`${ADMIN_I18N_PREFIX}.status.template.published`),
    },
    {
      value: 'deprecated',
      label: $t(`${ADMIN_I18N_PREFIX}.status.template.deprecated`),
    },
    {
      value: 'archived',
      label: $t(`${ADMIN_I18N_PREFIX}.status.template.archived`),
    },
  ];
}

export function getBuilderSurfaceOptions(): FilterOption[] {
  return [
    {
      value: 'platform_workflow_studio',
      label: $t(
        `${ADMIN_I18N_PREFIX}.templates.builderSurface.platformWorkflowStudio`,
      ),
    },
    {
      value: 'tenant_template_editor',
      label: $t(
        `${ADMIN_I18N_PREFIX}.templates.builderSurface.tenantTemplateEditor`,
      ),
    },
    {
      value: 'tenant_simple_builder',
      label: $t(
        `${ADMIN_I18N_PREFIX}.templates.builderSurface.tenantSimpleBuilder`,
      ),
    },
  ];
}

export function getReleaseScopeOptions(): FilterOption[] {
  return [
    {
      value: 'platform_catalog',
      label: $t(`${ADMIN_I18N_PREFIX}.common.releaseScope.platform_catalog`),
    },
    {
      value: 'selected_tenants',
      label: $t(`${ADMIN_I18N_PREFIX}.common.releaseScope.selected_tenants`),
    },
    {
      value: 'tenant_private',
      label: $t(`${ADMIN_I18N_PREFIX}.common.releaseScope.tenant_private`),
    },
  ];
}

export const editorCapabilityCategories: EditorCapabilityCategory[] = [
  {
    code: 'flow_core',
    icon: 'lucide:route',
    titleKey: 'editor.capabilities.flowCore.title',
    descriptionKey: 'editor.capabilities.flowCore.description',
  },
  {
    code: 'ai_core',
    icon: 'lucide:sparkles',
    titleKey: 'editor.capabilities.aiCore.title',
    descriptionKey: 'editor.capabilities.aiCore.description',
  },
  {
    code: 'tool_runtime',
    icon: 'lucide:wrench',
    titleKey: 'editor.capabilities.toolRuntime.title',
    descriptionKey: 'editor.capabilities.toolRuntime.description',
  },
  {
    code: 'governance',
    icon: 'lucide:shield-check',
    titleKey: 'editor.capabilities.governance.title',
    descriptionKey: 'editor.capabilities.governance.description',
  },
  {
    code: 'managed_extension',
    icon: 'lucide:plug-zap',
    titleKey: 'editor.capabilities.managedExtension.title',
    descriptionKey: 'editor.capabilities.managedExtension.description',
  },
];

export function getTemplateStatusColor(status: null | string | undefined): string {
  switch (status) {
    case 'published': {
      return 'success';
    }
    case 'deprecated': {
      return 'orange';
    }
    case 'archived': {
      return 'default';
    }
    case 'draft':
    default: {
      return 'processing';
    }
  }
}

export function getTemplateStatusText(status: null | string | undefined): string {
  if (!status) {
    return $t(`${ADMIN_I18N_PREFIX}.common.unknown`);
  }
  const key = `${ADMIN_I18N_PREFIX}.status.template.${status}`;
  const translated = $t(key);
  return translated === key ? status : translated;
}

export function getRiskColor(level: null | string | undefined): string {
  switch (level) {
    case 'critical': {
      return 'red';
    }
    case 'high': {
      return 'orange';
    }
    case 'medium': {
      return 'gold';
    }
    case 'low': {
      return 'green';
    }
    default: {
      return 'default';
    }
  }
}

export function getRiskText(level: null | string | undefined): string {
  if (!level) {
    return $t(`${ADMIN_I18N_PREFIX}.common.notAvailable`);
  }
  const key = `${ADMIN_I18N_PREFIX}.risk.${level}`;
  const translated = $t(key);
  return translated === key ? level : translated;
}

export function getBuilderSurfaceText(surface: null | string | undefined): string {
  if (!surface) {
    return $t(`${ADMIN_I18N_PREFIX}.common.notAvailable`);
  }
  const key = `${ADMIN_I18N_PREFIX}.templates.builderSurface.${surface}`;
  const translated = $t(key);
  return translated === key ? surface : translated;
}

export function getReleaseScopeText(scope: null | string | undefined): string {
  if (!scope) {
    return $t(`${ADMIN_I18N_PREFIX}.common.notAvailable`);
  }
  const key = `${ADMIN_I18N_PREFIX}.common.releaseScope.${scope}`;
  const translated = $t(key);
  return translated === key ? scope : translated;
}

export function getTemplateCategoryText(category: null | string | undefined): string {
  if (!category) {
    return $t(`${ADMIN_I18N_PREFIX}.common.notAvailable`);
  }
  return category;
}

export function getCapabilityCategoryText(
  category: null | string | undefined,
): string {
  if (!category) {
    return $t(`${ADMIN_I18N_PREFIX}.common.unknown`);
  }
  const key = `${ADMIN_I18N_PREFIX}.editor.capabilityCategory.${category}`;
  const translated = $t(key);
  return translated === key ? category : translated;
}

export function getCapabilityLabel(capability: WorkflowBuilderCapability): string {
  if (capability.label) {
    return capability.label;
  }
  const key = `${ADMIN_I18N_PREFIX}.editor.capabilityCode.${capability.code}`;
  const translated = $t(key);
  return translated === key ? capability.code : translated;
}

export function getTemplateGraphCounts(template: null | WorkflowTemplateDetail) {
  return {
    nodeCount: template?.nodes?.length ?? 0,
    edgeCount: template?.edges?.length ?? 0,
  };
}

export function buildTemplatePublishPayload(
  template: Pick<
    WorkflowTemplateSummary,
    'latest_version_id' | 'release_scope'
  >,
): PublishTemplatePayload {
  return {
    versionId: template.latest_version_id ?? undefined,
    releaseScope: template.release_scope ?? 'selected_tenants',
    channel: 'stable',
    environmentCode: 'prod_env',
    rolloutJson: {},
    notes: null,
    changeTypes: ['workflow_definition_change'],
    validationResult: {},
    riskLevel: null,
  };
}
