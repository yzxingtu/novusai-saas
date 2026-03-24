import type { Component } from 'vue';

import { enUS as adminEnUS, zhCN as adminZhCN } from './locales/admin';
import { enUS as tenantEnUS, zhCN as tenantZhCN } from './locales/tenant';
import AdminHomeView from './views/admin/home/index.vue';
import AdminReleaseListView from './views/admin/releases/index.vue';
import AdminRuntimeView from './views/admin/runtime/index.vue';
import AdminTemplateDetailView from './views/admin/templates/detail.vue';
import AdminTemplateEditorView from './views/admin/templates/editor.vue';
import AdminTemplateListView from './views/admin/templates/index.vue';
import TenantArtifactDetailView from './views/tenant/artifacts/detail.vue';
import TenantArtifactListView from './views/tenant/artifacts/index.vue';
import TenantHomeView from './views/tenant/home/index.vue';
import TenantRunDetailView from './views/tenant/runs/detail.vue';
import TenantRunListView from './views/tenant/runs/index.vue';
import TenantWorkflowCreateView from './views/tenant/workflows/create.vue';
import TenantWorkflowDetailView from './views/tenant/workflows/detail.vue';
import TenantWorkflowEditorView from './views/tenant/workflows/editor.vue';
import TenantWorkflowListView from './views/tenant/workflows/index.vue';

type LocaleMessages = Record<string, unknown>;

interface WorkflowPluginSharedApi {
  registerLocale?: (
    locale: string,
    prefix: string,
    messages: LocaleMessages,
  ) => void;
}

const ADMIN_LOCALE_PREFIX = 'plugin.workflow-orchestration.admin';
const TENANT_LOCALE_PREFIX = 'plugin.workflow-orchestration.tenant';
const LEGACY_ADMIN_LOCALE_PREFIX = 'plugin.workflowOrchestration.admin';
const LEGACY_TENANT_LOCALE_PREFIX = 'plugin.workflowOrchestration.tenant';

function getShared(): WorkflowPluginSharedApi | undefined {
  return (window as unknown as { NovusPluginShared?: WorkflowPluginSharedApi })
    .NovusPluginShared;
}

function registerLocaleGroup(
  prefix: string,
  bundles: {
    enUS: LocaleMessages;
    zhCN: LocaleMessages;
  },
): void {
  const shared = getShared();
  if (!shared?.registerLocale) {
    return;
  }

  shared.registerLocale('zh-CN', prefix, bundles.zhCN);
  shared.registerLocale('zh', prefix, bundles.zhCN);
  shared.registerLocale('en-US', prefix, bundles.enUS);
  shared.registerLocale('en', prefix, bundles.enUS);
}

export function setup(): void {
  registerLocaleGroup(ADMIN_LOCALE_PREFIX, {
    enUS: adminEnUS,
    zhCN: adminZhCN,
  });
  registerLocaleGroup(LEGACY_ADMIN_LOCALE_PREFIX, {
    enUS: adminEnUS,
    zhCN: adminZhCN,
  });
  registerLocaleGroup(TENANT_LOCALE_PREFIX, {
    enUS: tenantEnUS,
    zhCN: tenantZhCN,
  });
  registerLocaleGroup(LEGACY_TENANT_LOCALE_PREFIX, {
    enUS: tenantEnUS,
    zhCN: tenantZhCN,
  });
}

export const WorkflowOrchestrationAdminHomePage = AdminHomeView as Component;
export const WorkflowOrchestrationAdminTemplateListPage =
  AdminTemplateListView as Component;
export const WorkflowOrchestrationAdminTemplateDetailPage =
  AdminTemplateDetailView as Component;
export const WorkflowOrchestrationAdminTemplateEditorPage =
  AdminTemplateEditorView as Component;
export const WorkflowOrchestrationAdminReleaseListPage =
  AdminReleaseListView as Component;
export const WorkflowOrchestrationAdminRuntimePage =
  AdminRuntimeView as Component;

export const WorkflowOrchestrationTenantHomePage = TenantHomeView as Component;
export const WorkflowOrchestrationTenantWorkflowCreatePage =
  TenantWorkflowCreateView as Component;
export const WorkflowOrchestrationTenantWorkflowListPage =
  TenantWorkflowListView as Component;
export const WorkflowOrchestrationTenantWorkflowDetailPage =
  TenantWorkflowDetailView as Component;
export const WorkflowOrchestrationTenantWorkflowEditorPage =
  TenantWorkflowEditorView as Component;
export const WorkflowOrchestrationTenantRunListPage =
  TenantRunListView as Component;
export const WorkflowOrchestrationTenantRunDetailPage =
  TenantRunDetailView as Component;
export const WorkflowOrchestrationTenantArtifactListPage =
  TenantArtifactListView as Component;
export const WorkflowOrchestrationTenantArtifactDetailPage =
  TenantArtifactDetailView as Component;

export const WorkflowOrchestrationAdminHome =
  WorkflowOrchestrationAdminHomePage;
export const WorkflowOrchestrationAdminTemplateList =
  WorkflowOrchestrationAdminTemplateListPage;
export const WorkflowOrchestrationAdminTemplateDetail =
  WorkflowOrchestrationAdminTemplateDetailPage;
export const WorkflowOrchestrationAdminTemplateEditor =
  WorkflowOrchestrationAdminTemplateEditorPage;
export const WorkflowOrchestrationAdminReleaseList =
  WorkflowOrchestrationAdminReleaseListPage;
export const WorkflowOrchestrationAdminRuntime =
  WorkflowOrchestrationAdminRuntimePage;

export const WorkflowOrchestrationTenantHome =
  WorkflowOrchestrationTenantHomePage;
export const WorkflowOrchestrationTenantWorkflowCreate =
  WorkflowOrchestrationTenantWorkflowCreatePage;
export const WorkflowOrchestrationTenantWorkflowList =
  WorkflowOrchestrationTenantWorkflowListPage;
export const WorkflowOrchestrationTenantWorkflowDetail =
  WorkflowOrchestrationTenantWorkflowDetailPage;
export const WorkflowOrchestrationTenantWorkflowEditor =
  WorkflowOrchestrationTenantWorkflowEditorPage;
export const WorkflowOrchestrationTenantRunList =
  WorkflowOrchestrationTenantRunListPage;
export const WorkflowOrchestrationTenantRunDetail =
  WorkflowOrchestrationTenantRunDetailPage;
export const WorkflowOrchestrationTenantArtifactList =
  WorkflowOrchestrationTenantArtifactListPage;
export const WorkflowOrchestrationTenantArtifactDetail =
  WorkflowOrchestrationTenantArtifactDetailPage;
