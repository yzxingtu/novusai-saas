<script lang="ts" setup>
import { computed, nextTick, onMounted, reactive, ref } from 'vue';

import {
  copyTenantWorkflowFromTemplateApi,
  createTenantWorkflowApi,
  listTenantWorkflowTemplatesApi,
} from '../../../api/tenant';
import type { TenantWorkflowTemplateSummary } from '../../../types/tenant';
import ConsoleShell from '../shared/ConsoleShell.vue';
import {
  TENANT_WORKFLOW_AI_CONVERSATION_SCOPE,
  buildPrompt,
  openWorkflowAIPanel,
  useWorkflowPageAI,
} from '../../../shared/ai';
import {
  TENANT_WORKFLOW_CREATE_PAGE_ACCESS_CODES,
  WORKFLOW_ACCESS_CODES,
} from '../../../shared/access';
import { useTenantOrchestration } from '../shared/use-tenant-orchestration';

defineOptions({
  name: 'WorkflowOrchestrationTenantWorkflowCreate',
});

const TENANT_WORKFLOW_CREATE_PAGE_KEY =
  'tenant.workflow_orchestration.workflows.create';

const {
  formatRelativeTime,
  hasAccess,
  hasAnyAccess,
  navigateTo,
  t,
} = useTenantOrchestration();
const permissionDeniedMessage = t(
  'plugin.workflow-orchestration.tenant.common.messages.permissionDenied',
);
const canAccessCreatePage = hasAnyAccess(TENANT_WORKFLOW_CREATE_PAGE_ACCESS_CODES);
const canCreateBlank = hasAccess(
  WORKFLOW_ACCESS_CODES.WORKFLOW_BUILDER_CREATE,
);
const canCopyTemplate = hasAccess(
  WORKFLOW_ACCESS_CODES.WORKFLOW_BUILDER_COPY,
);
const canOpenWorkflowCenter = hasAccess(
  WORKFLOW_ACCESS_CODES.WORKFLOW_CENTER_LIST,
);

const actionKey = ref('');
const errorMessage = ref('');
const ideaDraft = ref('');
const templateKeyword = ref('');
const templateLoading = ref(false);
const templateErrorMessage = ref('');
const templates = ref<TenantWorkflowTemplateSummary[]>([]);
const blankCreateSection = ref<HTMLElement>();
const nameInput = ref<HTMLInputElement>();
const form = reactive({
  description: '',
  name: '',
});

const starterPromptKeys = [
  'campaignReview',
  'invoiceApproval',
  'riskFollowup',
] as const;

const canSubmit = computed(() => form.name.trim().length > 0 && !actionKey.value);
const creating = computed(() => actionKey.value === 'blank');

function isTemplateBusy(templateId: number): boolean {
  return actionKey.value === `template:${templateId}`;
}

async function focusBlankCreate(): Promise<void> {
  blankCreateSection.value?.scrollIntoView({
    behavior: 'smooth',
    block: 'center',
  });
  await nextTick();
  nameInput.value?.focus();
}

function buildPlannerPrompt(seed?: string): string {
  const normalizedSeed = seed?.trim() || ideaDraft.value.trim();
  return buildPrompt([
    t('plugin.workflow-orchestration.tenant.createEntry.ai.systemLead'),
    normalizedSeed
      ? t('plugin.workflow-orchestration.tenant.createEntry.ai.userIdea', {
          idea: normalizedSeed,
        })
      : t('plugin.workflow-orchestration.tenant.createEntry.ai.emptyIdea'),
    t('plugin.workflow-orchestration.tenant.createEntry.ai.outputContract'),
  ]);
}

function openAIPlanner(seed?: string): void {
  openWorkflowAIPanel({
    conversationScope: TENANT_WORKFLOW_AI_CONVERSATION_SCOPE,
    message: buildPlannerPrompt(seed),
    pageKey: TENANT_WORKFLOW_CREATE_PAGE_KEY,
  });
}

async function loadTemplates(): Promise<void> {
  if (!canCopyTemplate) {
    templateLoading.value = false;
    templateErrorMessage.value = '';
    templates.value = [];
    return;
  }

  templateLoading.value = true;
  templateErrorMessage.value = '';
  try {
    const result = await listTenantWorkflowTemplatesApi({
      keyword: templateKeyword.value.trim() || undefined,
      page: 1,
      size: 6,
    });
    templates.value = result.items;
  } catch (error: unknown) {
    templateErrorMessage.value =
      error instanceof Error
        ? error.message
        : t('plugin.workflow-orchestration.tenant.common.messages.loadFailed');
  } finally {
    templateLoading.value = false;
  }
}

async function createWorkflow(payload?: {
  description?: string;
  name?: string;
}): Promise<{ message: string; success: boolean }> {
  if (!canCreateBlank) {
    errorMessage.value = permissionDeniedMessage;
    return {
      success: false,
      message: permissionDeniedMessage,
    };
  }

  const name = payload?.name?.trim() ?? form.name.trim();
  const description = payload?.description?.trim() ?? form.description.trim();

  if (!name) {
    errorMessage.value = t(
      'plugin.workflow-orchestration.tenant.workflow.validation.nameRequired',
    );
    return {
      success: false,
      message: errorMessage.value,
    };
  }

  actionKey.value = 'blank';
  errorMessage.value = '';

  try {
    const created = await createTenantWorkflowApi({
      description: description || undefined,
      name,
    });
    navigateTo(`workflows/${created.id}`);
    return {
      success: true,
      message: t('plugin.workflow-orchestration.tenant.createEntry.create.success'),
    };
  } catch (error: unknown) {
    errorMessage.value =
      error instanceof Error
        ? error.message
        : t('plugin.workflow-orchestration.tenant.common.messages.actionFailed');
    return {
      success: false,
      message: errorMessage.value,
    };
  } finally {
    actionKey.value = '';
  }
}

async function copyFromTemplate(
  template: TenantWorkflowTemplateSummary,
  overrides?: {
    description?: string;
    name?: string;
  },
): Promise<{ message: string; success: boolean }> {
  if (!canCopyTemplate) {
    errorMessage.value = permissionDeniedMessage;
    return {
      success: false,
      message: permissionDeniedMessage,
    };
  }

  if (!template.id) {
    errorMessage.value = t(
      'plugin.workflow-orchestration.tenant.createEntry.templates.validation.templateRequired',
    );
    return {
      success: false,
      message: errorMessage.value,
    };
  }

  actionKey.value = `template:${template.id}`;
  errorMessage.value = '';

  try {
    const created = await copyTenantWorkflowFromTemplateApi({
      description:
        overrides?.description?.trim() || form.description.trim() || undefined,
      name: overrides?.name?.trim() || form.name.trim() || undefined,
      templateId: template.id,
      templateVersionId: template.currentPublishedVersionId ?? 0,
    });
    navigateTo(`workflows/${created.id}`);
    return {
      success: true,
      message: t(
        'plugin.workflow-orchestration.tenant.createEntry.templates.create.success',
      ),
    };
  } catch (error: unknown) {
    errorMessage.value =
      error instanceof Error
        ? error.message
        : t('plugin.workflow-orchestration.tenant.common.messages.actionFailed');
    return {
      success: false,
      message: errorMessage.value,
    };
  } finally {
    actionKey.value = '';
  }
}

useWorkflowPageAI({
  conversationScope: TENANT_WORKFLOW_AI_CONVERSATION_SCOPE,
  pageKey: TENANT_WORKFLOW_CREATE_PAGE_KEY,
  buildContext: () => ({
    entityDescription: t(
      'plugin.workflow-orchestration.tenant.createEntry.ai.pageDescription',
    ),
    entityTitle: t('plugin.workflow-orchestration.tenant.createEntry.title'),
    entityType: 'workflow_orchestration_tenant_create',
    pageData: {
      create_name: form.name,
      create_description: form.description,
      idea_draft: ideaDraft.value,
      visible_templates: templates.value.slice(0, 6).map((template) => ({
        id: template.id,
        name: template.name,
        category: template.category ?? null,
      })),
      recommended_steps: [
        t('plugin.workflow-orchestration.tenant.createEntry.steps.blank.title'),
        t('plugin.workflow-orchestration.tenant.createEntry.steps.publish.title'),
        t('plugin.workflow-orchestration.tenant.createEntry.steps.run.title'),
      ],
    },
    pageTitle: t('plugin.workflow-orchestration.tenant.createEntry.title'),
  }),
  operations: [
    {
      name: 'create_blank_workflow',
      label: t('plugin.workflow-orchestration.tenant.createEntry.create.action'),
      description: t(
        'plugin.workflow-orchestration.tenant.createEntry.create.description',
      ),
      readonly: false,
      params: {
        description: {
          description: t(
            'plugin.workflow-orchestration.tenant.workflow.fields.description',
          ),
          required: false,
          type: 'string',
        },
        name: {
          description: t('plugin.workflow-orchestration.tenant.workflow.fields.name'),
          required: true,
          type: 'string',
        },
      },
      handler: async (params: Record<string, unknown>) =>
        canCreateBlank
          ? createWorkflow({
              description:
                typeof params.description === 'string' ? params.description : '',
              name: typeof params.name === 'string' ? params.name : '',
            })
          : {
              success: false,
              message: permissionDeniedMessage,
            },
    },
    {
      name: 'open_workflow_ai_planner',
      label: t('plugin.workflow-orchestration.tenant.createEntry.actions.askAI'),
      description: t('plugin.workflow-orchestration.tenant.createEntry.ai.description'),
      readonly: true,
      params: {
        idea: {
          description: t(
            'plugin.workflow-orchestration.tenant.createEntry.ai.inputLabel',
          ),
          required: false,
          type: 'string',
        },
      },
      handler: async (params: Record<string, unknown>) => {
        openAIPlanner(typeof params.idea === 'string' ? params.idea : undefined);
        return {
          success: true,
          message: t('plugin.workflow-orchestration.tenant.createEntry.ai.opened'),
        };
      },
    },
    {
      name: 'copy_workflow_from_template',
      label: t(
        'plugin.workflow-orchestration.tenant.createEntry.templates.actions.useTemplate',
      ),
      description: t(
        'plugin.workflow-orchestration.tenant.createEntry.templates.description',
      ),
      readonly: false,
      params: {
        description: {
          description: t(
            'plugin.workflow-orchestration.tenant.workflow.fields.description',
          ),
          required: false,
          type: 'string',
        },
        name: {
          description: t('plugin.workflow-orchestration.tenant.workflow.fields.name'),
          required: false,
          type: 'string',
        },
        template_id: {
          description: t(
            'plugin.workflow-orchestration.tenant.createEntry.templates.fields.templateId',
          ),
          required: true,
          type: 'number',
        },
      },
      handler: async (params: Record<string, unknown>) => {
        if (!canCopyTemplate) {
          return {
            success: false,
            message: permissionDeniedMessage,
          };
        }
        const templateId = Number(params.template_id);
        const target = templates.value.find((item) => item.id === templateId);
        if (!Number.isFinite(templateId) || !target) {
          return {
            success: false,
            message: t(
              'plugin.workflow-orchestration.tenant.createEntry.templates.validation.templateRequired',
            ),
          };
        }
        return copyFromTemplate(target, {
          description:
            typeof params.description === 'string'
              ? params.description
              : undefined,
          name:
            typeof params.name === 'string' && params.name.trim()
              ? params.name
              : undefined,
        });
      },
    },
    {
      name: 'open_workflow_center',
      label: t('plugin.workflow-orchestration.tenant.createEntry.actions.openCenter'),
      description: t('plugin.workflow-orchestration.tenant.createEntry.description'),
      readonly: true,
      handler: async () => {
        if (!canOpenWorkflowCenter) {
          return {
            success: false,
            message: permissionDeniedMessage,
          };
        }
        navigateTo('workflows');
        return {
          success: true,
          message: t('plugin.workflow-orchestration.tenant.createEntry.actions.openCenter'),
        };
      },
    },
    {
      name: 'focus_blank_workflow_create_form',
      label: t('plugin.workflow-orchestration.tenant.createEntry.actions.goEditor'),
      description: t(
        'plugin.workflow-orchestration.tenant.createEntry.create.description',
      ),
      readonly: true,
      handler: async () => {
        if (!canCreateBlank) {
          return {
            success: false,
            message: permissionDeniedMessage,
          };
        }
        await focusBlankCreate();
        return {
          success: true,
          message: t(
            'plugin.workflow-orchestration.tenant.createEntry.create.focused',
          ),
        };
      },
    },
  ],
});

onMounted(() => {
  if (canCopyTemplate) {
    void loadTemplates();
  } else {
    templateLoading.value = false;
  }
});
</script>

<template>
  <ConsoleShell
    :description="t('plugin.workflow-orchestration.tenant.createEntry.description')"
    :eyebrow="t('plugin.workflow-orchestration.tenant.createEntry.eyebrow')"
    :title="t('plugin.workflow-orchestration.tenant.createEntry.title')"
  >
    <template #actions>
      <button
        v-if="canAccessCreatePage && canOpenWorkflowCenter"
        class="inline-flex items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-sky-200 hover:text-sky-700"
        type="button"
        @click="navigateTo('workflows')"
      >
        {{ t('plugin.workflow-orchestration.tenant.createEntry.actions.openCenter') }}
      </button>
      <button
        v-if="canAccessCreatePage"
        class="inline-flex items-center rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800"
        type="button"
        @click="openAIPlanner()"
      >
        {{ t('plugin.workflow-orchestration.tenant.createEntry.actions.askAI') }}
      </button>
    </template>

    <EmptyState
      v-if="!canAccessCreatePage"
      :title="permissionDeniedMessage"
    />
    <template v-else>
    <section class="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
      <article class="relative overflow-hidden rounded-[28px] border border-sky-100 bg-white/95 p-6 shadow-sm">
        <div class="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(14,165,233,0.14),transparent_58%),radial-gradient(circle_at_bottom_right,rgba(15,23,42,0.08),transparent_56%)]" />
        <div class="relative space-y-5">
          <div class="space-y-2">
            <span class="inline-flex rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-xs font-medium text-sky-700">
              {{ t('plugin.workflow-orchestration.tenant.createEntry.ai.badge') }}
            </span>
            <h2 class="text-2xl font-semibold tracking-tight text-slate-950">
              {{ t('plugin.workflow-orchestration.tenant.createEntry.ai.title') }}
            </h2>
            <p class="max-w-2xl text-sm leading-6 text-slate-600">
              {{ t('plugin.workflow-orchestration.tenant.createEntry.ai.description') }}
            </p>
          </div>

          <label class="block space-y-2">
            <span class="text-sm font-medium text-slate-700">
              {{ t('plugin.workflow-orchestration.tenant.createEntry.ai.inputLabel') }}
            </span>
            <textarea
              v-model="ideaDraft"
              class="min-h-[132px] w-full rounded-3xl border border-slate-200 bg-white px-4 py-3 text-sm leading-6 text-slate-900 outline-none transition focus:border-sky-300 focus:ring-2 focus:ring-sky-100"
              :placeholder="t('plugin.workflow-orchestration.tenant.createEntry.ai.placeholder')"
            />
          </label>

          <div class="flex flex-wrap gap-3">
            <button
              class="inline-flex items-center rounded-full bg-slate-900 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-slate-800"
              type="button"
              @click="openAIPlanner()"
            >
              {{ t('plugin.workflow-orchestration.tenant.createEntry.actions.askAI') }}
            </button>
            <button
              v-if="canCreateBlank"
              class="inline-flex items-center rounded-full border border-slate-200 bg-white px-5 py-2.5 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:text-slate-900"
              type="button"
              @click="focusBlankCreate()"
            >
              {{ t('plugin.workflow-orchestration.tenant.createEntry.actions.goEditor') }}
            </button>
          </div>

          <div class="grid gap-3 md:grid-cols-3">
            <button
              v-for="promptKey in starterPromptKeys"
              :key="promptKey"
              class="rounded-3xl border border-white/70 bg-white/90 px-4 py-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-sky-200 hover:bg-sky-50/70"
              type="button"
              @click="openAIPlanner(t(`plugin.workflow-orchestration.tenant.createEntry.ai.starters.${promptKey}.prompt`))"
            >
              <div class="text-sm font-semibold text-slate-900">
                {{ t(`plugin.workflow-orchestration.tenant.createEntry.ai.starters.${promptKey}.title`) }}
              </div>
              <div class="mt-2 text-xs leading-5 text-slate-500">
                {{ t(`plugin.workflow-orchestration.tenant.createEntry.ai.starters.${promptKey}.description`) }}
              </div>
            </button>
          </div>
        </div>
      </article>

      <div class="space-y-4">
        <article class="rounded-[28px] border border-white/70 bg-white/95 p-6 shadow-sm">
          <template v-if="canCopyTemplate">
          <div class="space-y-2">
            <span class="inline-flex rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700">
              {{ t('plugin.workflow-orchestration.tenant.createEntry.templates.badge') }}
            </span>
            <h2 class="text-xl font-semibold text-slate-950">
              {{ t('plugin.workflow-orchestration.tenant.createEntry.templates.title') }}
            </h2>
            <p class="text-sm leading-6 text-slate-600">
              {{ t('plugin.workflow-orchestration.tenant.createEntry.templates.description') }}
            </p>
          </div>

          <div class="mt-5 flex gap-3">
            <input
              v-model="templateKeyword"
              class="w-full rounded-2xl border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 outline-none transition focus:border-sky-300 focus:ring-2 focus:ring-sky-100"
              :placeholder="t('plugin.workflow-orchestration.tenant.createEntry.templates.searchPlaceholder')"
              type="text"
              @keyup.enter="loadTemplates()"
            />
            <button
              class="inline-flex shrink-0 items-center rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:text-slate-900"
              type="button"
              @click="loadTemplates()"
            >
              {{ t('plugin.workflow-orchestration.tenant.common.actions.applyFilters') }}
            </button>
          </div>

          <p class="mt-3 text-xs leading-5 text-slate-500">
            {{ t('plugin.workflow-orchestration.tenant.createEntry.templates.overrideNotice') }}
          </p>

          <p
            v-if="templateErrorMessage"
            class="mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700"
          >
            {{ templateErrorMessage }}
          </p>

          <div v-if="templateLoading" class="mt-4 space-y-3">
            <div
              v-for="index in 3"
              :key="index"
              class="rounded-3xl border border-slate-100 bg-slate-50 px-4 py-4"
            >
              <div class="h-4 w-32 animate-pulse rounded-full bg-slate-200" />
              <div class="mt-3 h-10 animate-pulse rounded-2xl bg-slate-100" />
              <div class="mt-3 h-9 animate-pulse rounded-full bg-slate-100" />
            </div>
          </div>

          <div v-else-if="templates.length > 0" class="mt-4 space-y-3">
            <article
              v-for="template in templates"
              :key="template.id"
              class="rounded-3xl border border-slate-100 bg-slate-50/90 px-4 py-4"
            >
              <div class="flex flex-wrap items-start justify-between gap-3">
                <div class="space-y-2">
                  <div class="flex flex-wrap items-center gap-2">
                    <h3 class="text-sm font-semibold text-slate-950">
                      {{ template.name }}
                    </h3>
                    <span
                      v-if="template.category"
                      class="inline-flex rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-medium text-slate-600"
                    >
                      {{ template.category }}
                    </span>
                    <span
                      v-if="template.tags?.length"
                      class="inline-flex rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-[11px] font-medium text-sky-700"
                    >
                      {{ template.tags[0] }}
                    </span>
                  </div>
                  <p class="text-sm leading-6 text-slate-600">
                    {{
                      template.description
                        || t('plugin.workflow-orchestration.tenant.createEntry.templates.emptyDescription')
                    }}
                  </p>
                  <div class="flex flex-wrap gap-3 text-xs text-slate-500">
                    <span
                      v-if="
                        template.publishedVersion
                        || template.latestVersionNo != null
                      "
                    >
                      {{
                        template.publishedVersion
                          ? template.publishedVersion
                          : t(
                              'plugin.workflow-orchestration.tenant.createEntry.templates.fields.latestVersionNo',
                              { version: template.latestVersionNo },
                            )
                      }}
                    </span>
                    <span v-if="template.releaseScope">
                      {{
                        t(
                          `plugin.workflow-orchestration.tenant.common.releaseScope.${template.releaseScope}`,
                        )
                      }}
                    </span>
                    <span v-if="template.publishedAt">
                      {{
                        t(
                          'plugin.workflow-orchestration.tenant.createEntry.templates.fields.publishedAt',
                          { time: formatRelativeTime(template.publishedAt) },
                        )
                      }}
                    </span>
                  </div>
                </div>

                <button
                  class="inline-flex shrink-0 items-center rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
                  :disabled="!template.canCopy || !template.currentPublishedVersionId || (Boolean(actionKey) && !isTemplateBusy(template.id))"
                  type="button"
                  @click="copyFromTemplate(template)"
                >
                  {{
                    isTemplateBusy(template.id)
                      ? t('plugin.workflow-orchestration.tenant.common.messages.processing')
                      : t(
                          'plugin.workflow-orchestration.tenant.createEntry.templates.actions.useTemplate',
                        )
                  }}
                </button>
              </div>
            </article>
          </div>

          <div
            v-else
            class="mt-4 rounded-3xl border border-dashed border-slate-200 bg-slate-50/80 px-5 py-6 text-center"
          >
            <div class="text-sm font-semibold text-slate-900">
              {{ t('plugin.workflow-orchestration.tenant.createEntry.templates.emptyTitle') }}
            </div>
            <div class="mt-2 text-sm leading-6 text-slate-500">
              {{ t('plugin.workflow-orchestration.tenant.createEntry.templates.emptyDescriptionText') }}
            </div>
          </div>
          </template>
          <EmptyState
            v-else
            :description="permissionDeniedMessage"
            :title="t('plugin.workflow-orchestration.tenant.createEntry.templates.emptyTitle')"
          />
        </article>

        <article
          v-if="canCreateBlank"
          ref="blankCreateSection"
          class="rounded-[28px] border border-white/70 bg-white/95 p-6 shadow-sm"
        >
          <div class="space-y-2">
            <span class="inline-flex rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-600">
              {{ t('plugin.workflow-orchestration.tenant.createEntry.create.badge') }}
            </span>
            <h2 class="text-xl font-semibold text-slate-950">
              {{ t('plugin.workflow-orchestration.tenant.createEntry.create.title') }}
            </h2>
            <p class="text-sm leading-6 text-slate-600">
              {{ t('plugin.workflow-orchestration.tenant.createEntry.create.description') }}
            </p>
          </div>

          <div class="mt-5 space-y-4">
            <label class="block space-y-2">
              <span class="text-sm font-medium text-slate-700">
                {{ t('plugin.workflow-orchestration.tenant.workflow.fields.name') }}
              </span>
              <input
                ref="nameInput"
                v-model="form.name"
                class="w-full rounded-2xl border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 outline-none transition focus:border-sky-300 focus:ring-2 focus:ring-sky-100"
                :placeholder="t('plugin.workflow-orchestration.tenant.workflow.placeholders.name')"
                type="text"
              />
            </label>

            <label class="block space-y-2">
              <span class="text-sm font-medium text-slate-700">
                {{ t('plugin.workflow-orchestration.tenant.workflow.fields.description') }}
              </span>
              <textarea
                v-model="form.description"
                class="min-h-[120px] w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm leading-6 text-slate-900 outline-none transition focus:border-sky-300 focus:ring-2 focus:ring-sky-100"
                :placeholder="t('plugin.workflow-orchestration.tenant.workflow.placeholders.description')"
              />
            </label>

            <p
              v-if="errorMessage"
              class="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700"
            >
              {{ errorMessage }}
            </p>

            <button
              class="inline-flex w-full items-center justify-center rounded-full bg-slate-900 px-5 py-3 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="!canSubmit"
              type="button"
              @click="createWorkflow()"
            >
              {{
                creating
                  ? t('plugin.workflow-orchestration.tenant.common.messages.processing')
                  : t('plugin.workflow-orchestration.tenant.createEntry.create.action')
              }}
            </button>
          </div>
        </article>
      </div>
    </section>

    <section class="grid gap-4 lg:grid-cols-3">
      <article
        class="rounded-[26px] border border-white/70 bg-white/95 p-5 shadow-sm"
      >
        <div class="text-xs font-semibold uppercase tracking-[0.24em] text-sky-600">
          01
        </div>
        <h3 class="mt-3 text-lg font-semibold text-slate-950">
          {{ t('plugin.workflow-orchestration.tenant.createEntry.steps.blank.title') }}
        </h3>
        <p class="mt-2 text-sm leading-6 text-slate-600">
          {{ t('plugin.workflow-orchestration.tenant.createEntry.steps.blank.description') }}
        </p>
      </article>
      <article
        class="rounded-[26px] border border-white/70 bg-white/95 p-5 shadow-sm"
      >
        <div class="text-xs font-semibold uppercase tracking-[0.24em] text-sky-600">
          02
        </div>
        <h3 class="mt-3 text-lg font-semibold text-slate-950">
          {{ t('plugin.workflow-orchestration.tenant.createEntry.steps.publish.title') }}
        </h3>
        <p class="mt-2 text-sm leading-6 text-slate-600">
          {{ t('plugin.workflow-orchestration.tenant.createEntry.steps.publish.description') }}
        </p>
      </article>
      <article
        class="rounded-[26px] border border-white/70 bg-white/95 p-5 shadow-sm"
      >
        <div class="text-xs font-semibold uppercase tracking-[0.24em] text-sky-600">
          03
        </div>
        <h3 class="mt-3 text-lg font-semibold text-slate-950">
          {{ t('plugin.workflow-orchestration.tenant.createEntry.steps.run.title') }}
        </h3>
        <p class="mt-2 text-sm leading-6 text-slate-600">
          {{ t('plugin.workflow-orchestration.tenant.createEntry.steps.run.description') }}
        </p>
      </article>
    </section>
    </template>
  </ConsoleShell>
</template>
