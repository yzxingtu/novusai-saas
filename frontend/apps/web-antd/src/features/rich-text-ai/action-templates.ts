import type {
  RichTextAiActionGroup,
  RichTextAiActionTemplate,
  RichTextAiActionType,
  RichTextAiFormatTemplate,
  RichTextAiOperationKind,
} from './types';

export const DEFAULT_RICH_TEXT_AI_ACTION_TEMPLATES = [
  {
    action: 'continue',
    defaultApplyMode: 'insert_after_selection',
    defaultFormatPreset: 'preserve_structure',
    descriptionKey:
      'admin.ai.skillPackage.richTextAi.actions.continue.description',
    endpointFeature: 'continue',
    icon: 'lucide:pen-line',
    labelKey: 'admin.ai.skillPackage.richTextAi.actions.continue.label',
    operationKind: 'insert',
    promptHintKey: 'admin.ai.skillPackage.richTextAi.actions.continue.prompt',
    requiresSelection: false,
    supportsCustomInstruction: false,
    supportsFormatInstruction: true,
    tagColor: 'green',
    visibleInContextMenu: true,
  },
  {
    action: 'rewrite',
    defaultApplyMode: 'replace_selection',
    defaultFormatPreset: 'preserve_structure',
    descriptionKey:
      'admin.ai.skillPackage.richTextAi.actions.rewrite.description',
    endpointFeature: 'rewrite',
    icon: 'lucide:refresh-ccw-dot',
    labelKey: 'admin.ai.skillPackage.richTextAi.actions.rewrite.label',
    operationKind: 'transform',
    promptHintKey: 'admin.ai.skillPackage.richTextAi.actions.rewrite.prompt',
    requiresSelection: true,
    supportsCustomInstruction: false,
    supportsFormatInstruction: true,
    tagColor: 'geekblue',
    visibleInContextMenu: true,
  },
  {
    action: 'insert',
    defaultApplyMode: 'insert_at_cursor',
    defaultFormatPreset: 'structured_sections',
    descriptionKey: 'admin.ai.skillPackage.richTextAi.actions.insert.description',
    endpointFeature: 'insert',
    icon: 'lucide:file-plus-2',
    labelKey: 'admin.ai.skillPackage.richTextAi.actions.insert.label',
    operationKind: 'insert',
    promptHintKey: 'admin.ai.skillPackage.richTextAi.actions.insert.prompt',
    requiresSelection: false,
    supportsCustomInstruction: true,
    supportsFormatInstruction: true,
    tagColor: 'green',
    visibleInContextMenu: true,
  },
  {
    action: 'format',
    defaultApplyMode: 'replace_selection',
    defaultFormatPreset: 'structured_sections',
    descriptionKey: 'admin.ai.skillPackage.richTextAi.actions.format.description',
    endpointFeature: 'format',
    icon: 'lucide:paintbrush-vertical',
    labelKey: 'admin.ai.skillPackage.richTextAi.actions.format.label',
    operationKind: 'format',
    promptHintKey: 'admin.ai.skillPackage.richTextAi.actions.format.prompt',
    requiresSelection: true,
    supportsCustomInstruction: true,
    supportsFormatInstruction: true,
    tagColor: 'volcano',
    visibleInContextMenu: true,
  },
  {
    action: 'optimize',
    defaultApplyMode: 'replace_selection',
    defaultFormatPreset: 'preserve_structure',
    descriptionKey:
      'admin.ai.skillPackage.richTextAi.actions.optimize.description',
    endpointFeature: 'optimize',
    icon: 'lucide:sparkles',
    labelKey: 'admin.ai.skillPackage.richTextAi.actions.optimize.label',
    operationKind: 'transform',
    promptHintKey: 'admin.ai.skillPackage.richTextAi.actions.optimize.prompt',
    requiresSelection: true,
    supportsCustomInstruction: false,
    supportsFormatInstruction: true,
    tagColor: 'blue',
    visibleInContextMenu: true,
  },
  {
    action: 'proofread',
    defaultApplyMode: 'replace_selection',
    defaultFormatPreset: 'preserve_structure',
    descriptionKey:
      'admin.ai.skillPackage.richTextAi.actions.proofread.description',
    endpointFeature: 'proofread',
    icon: 'lucide:spell-check',
    labelKey: 'admin.ai.skillPackage.richTextAi.actions.proofread.label',
    operationKind: 'transform',
    promptHintKey: 'admin.ai.skillPackage.richTextAi.actions.proofread.prompt',
    requiresSelection: true,
    supportsCustomInstruction: false,
    supportsFormatInstruction: false,
    tagColor: 'cyan',
    visibleInContextMenu: true,
  },
  {
    action: 'translate',
    defaultApplyMode: 'replace_selection',
    defaultFormatPreset: 'preserve_structure',
    descriptionKey:
      'admin.ai.skillPackage.richTextAi.actions.translate.description',
    endpointFeature: 'translate',
    icon: 'lucide:languages',
    labelKey: 'admin.ai.skillPackage.richTextAi.actions.translate.label',
    operationKind: 'translate',
    promptHintKey: 'admin.ai.skillPackage.richTextAi.actions.translate.prompt',
    requiresSelection: true,
    supportsCustomInstruction: false,
    supportsFormatInstruction: true,
    tagColor: 'purple',
    visibleInContextMenu: true,
  },
  {
    action: 'summarize',
    defaultApplyMode: 'replace_selection',
    defaultFormatPreset: 'bullet_list',
    descriptionKey:
      'admin.ai.skillPackage.richTextAi.actions.summarize.description',
    endpointFeature: 'summarize',
    icon: 'lucide:list-collapse',
    labelKey: 'admin.ai.skillPackage.richTextAi.actions.summarize.label',
    operationKind: 'summarize',
    promptHintKey: 'admin.ai.skillPackage.richTextAi.actions.summarize.prompt',
    requiresSelection: true,
    supportsCustomInstruction: false,
    supportsFormatInstruction: true,
    tagColor: 'gold',
    visibleInContextMenu: true,
  },
  {
    action: 'expand',
    defaultApplyMode: 'replace_selection',
    defaultFormatPreset: 'structured_sections',
    descriptionKey:
      'admin.ai.skillPackage.richTextAi.actions.expand.description',
    endpointFeature: 'expand',
    icon: 'lucide:stretch-horizontal',
    labelKey: 'admin.ai.skillPackage.richTextAi.actions.expand.label',
    operationKind: 'transform',
    promptHintKey: 'admin.ai.skillPackage.richTextAi.actions.expand.prompt',
    requiresSelection: true,
    supportsCustomInstruction: false,
    supportsFormatInstruction: true,
    tagColor: 'orange',
    visibleInContextMenu: true,
  },
  {
    action: 'custom',
    defaultApplyMode: 'replace_selection',
    defaultFormatPreset: 'preserve_structure',
    descriptionKey:
      'admin.ai.skillPackage.richTextAi.actions.custom.description',
    endpointFeature: 'custom',
    icon: 'lucide:wand-sparkles',
    labelKey: 'admin.ai.skillPackage.richTextAi.actions.custom.label',
    operationKind: 'transform',
    promptHintKey: 'admin.ai.skillPackage.richTextAi.actions.custom.prompt',
    requiresSelection: false,
    supportsCustomInstruction: true,
    supportsFormatInstruction: true,
    tagColor: 'magenta',
    visibleInContextMenu: true,
  },
  {
    action: 'chat',
    defaultApplyMode: 'copy_only',
    descriptionKey: 'admin.ai.skillPackage.richTextAi.actions.chat.description',
    endpointFeature: 'chat',
    icon: 'lucide:messages-square',
    labelKey: 'admin.ai.skillPackage.richTextAi.actions.chat.label',
    operationKind: 'assist',
    promptHintKey: 'admin.ai.skillPackage.richTextAi.actions.chat.prompt',
    requiresSelection: false,
    supportsCustomInstruction: true,
    supportsFormatInstruction: false,
    tagColor: 'default',
    visibleInContextMenu: false,
  },
] as const satisfies readonly RichTextAiActionTemplate[];

export const DEFAULT_RICH_TEXT_AI_FORMAT_TEMPLATES = [
  {
    descriptionKey:
      'admin.ai.skillPackage.richTextAi.formatPresets.preserve_structure.description',
    formatInstructionKey:
      'admin.ai.skillPackage.richTextAi.formatPresets.preserve_structure.instruction',
    icon: 'lucide:panel-top',
    labelKey:
      'admin.ai.skillPackage.richTextAi.formatPresets.preserve_structure.label',
    preset: 'preserve_structure',
  },
  {
    descriptionKey:
      'admin.ai.skillPackage.richTextAi.formatPresets.plain_text.description',
    formatInstructionKey:
      'admin.ai.skillPackage.richTextAi.formatPresets.plain_text.instruction',
    icon: 'lucide:remove-formatting',
    labelKey: 'admin.ai.skillPackage.richTextAi.formatPresets.plain_text.label',
    preset: 'plain_text',
  },
  {
    descriptionKey:
      'admin.ai.skillPackage.richTextAi.formatPresets.bullet_list.description',
    formatInstructionKey:
      'admin.ai.skillPackage.richTextAi.formatPresets.bullet_list.instruction',
    icon: 'lucide:list',
    labelKey: 'admin.ai.skillPackage.richTextAi.formatPresets.bullet_list.label',
    preset: 'bullet_list',
  },
  {
    descriptionKey:
      'admin.ai.skillPackage.richTextAi.formatPresets.structured_sections.description',
    formatInstructionKey:
      'admin.ai.skillPackage.richTextAi.formatPresets.structured_sections.instruction',
    icon: 'lucide:heading',
    labelKey:
      'admin.ai.skillPackage.richTextAi.formatPresets.structured_sections.label',
    preset: 'structured_sections',
  },
] as const satisfies readonly RichTextAiFormatTemplate[];

const TEMPLATE_BY_ACTION = new Map<
  RichTextAiActionType,
  RichTextAiActionTemplate
>(DEFAULT_RICH_TEXT_AI_ACTION_TEMPLATES.map((item) => [item.action, item]));

export function getRichTextAiActionTemplate(
  action: RichTextAiActionType,
): RichTextAiActionTemplate {
  return TEMPLATE_BY_ACTION.get(action) ?? TEMPLATE_BY_ACTION.get('custom')!;
}

export function getRichTextAiContextMenuActions(options: {
  enabledActions?: readonly RichTextAiActionType[];
  includeAssistActions?: boolean;
} = {}): RichTextAiActionTemplate[] {
  const enabled = options.enabledActions
    ? new Set<RichTextAiActionType>(options.enabledActions)
    : null;

  return DEFAULT_RICH_TEXT_AI_ACTION_TEMPLATES.filter((template) => {
    if (enabled && !enabled.has(template.action)) {
      return false;
    }
    if (!options.includeAssistActions && !template.visibleInContextMenu) {
      return false;
    }
    return true;
  });
}

export function groupRichTextAiActionsByKind(
  templates: readonly RichTextAiActionTemplate[] =
    DEFAULT_RICH_TEXT_AI_ACTION_TEMPLATES,
): RichTextAiActionGroup[] {
  const groups = new Map<RichTextAiOperationKind, RichTextAiActionTemplate[]>();

  for (const template of templates) {
    const group = groups.get(template.operationKind) ?? [];
    group.push(template);
    groups.set(template.operationKind, group);
  }

  return [...groups.entries()].map(([kind, actions]) => ({ actions, kind }));
}
