import { buildAdminPath } from '../shared/constants';

export interface HomeQuickLink {
  descriptionKey: string;
  icon: string;
  key: string;
  path: string;
  titleKey: string;
}

export interface BuilderSurfaceCard {
  code: string;
  descriptionKey: string;
  icon: string;
  titleKey: string;
}

export const homeQuickLinks: HomeQuickLink[] = [
  {
    key: 'templates',
    icon: 'lucide:copy-plus',
    path: buildAdminPath('templates'),
    titleKey: 'home.quickLinks.templates.title',
    descriptionKey: 'home.quickLinks.templates.description',
  },
  {
    key: 'releases',
    icon: 'lucide:rocket',
    path: buildAdminPath('releases'),
    titleKey: 'home.quickLinks.releases.title',
    descriptionKey: 'home.quickLinks.releases.description',
  },
  {
    key: 'runtime',
    icon: 'lucide:activity',
    path: buildAdminPath('runtime'),
    titleKey: 'home.quickLinks.runtime.title',
    descriptionKey: 'home.quickLinks.runtime.description',
  },
];

export const builderSurfaceCards: BuilderSurfaceCard[] = [
  {
    code: 'platform_workflow_studio',
    icon: 'lucide:workflow',
    titleKey: 'home.builderSurfaces.platformWorkflowStudio.title',
    descriptionKey: 'home.builderSurfaces.platformWorkflowStudio.description',
  },
  {
    code: 'tenant_template_editor',
    icon: 'lucide:copy-check',
    titleKey: 'home.builderSurfaces.tenantTemplateEditor.title',
    descriptionKey: 'home.builderSurfaces.tenantTemplateEditor.description',
  },
  {
    code: 'tenant_simple_builder',
    icon: 'lucide:wand-sparkles',
    titleKey: 'home.builderSurfaces.tenantSimpleBuilder.title',
    descriptionKey: 'home.builderSurfaces.tenantSimpleBuilder.description',
  },
];
