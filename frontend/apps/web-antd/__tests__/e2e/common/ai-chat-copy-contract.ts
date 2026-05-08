// Test type: smoke
// Scope: shared copy assertions used by AI chat Playwright smoke.
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

interface CommonLocaleShape {
  aiPanel: {
    memory: string;
    moreActions: string;
    newChat: string;
  };
  globalAiChat: {
    agentProfileAria: string;
    agentProfileHint: string;
    contextDiagnostics: string;
    diagnosticContextSourcesLabel: string;
    diagnosticProtocolPathLabel: string;
    diagnosticSelectedSkillsLabel: string;
    diagnosticSelectedToolsLabel: string;
    diagnosticTerminationReasonLabel: string;
    knowledgeBaseFallback: string;
    mentionSectionKbs: string;
    noDescription: string;
    noKnowledgeBases: string;
    noSkillPackages: string;
    noSkillsInPackage: string;
    rebuildContextCompact: string;
    runTimeline: string;
    skillBindingFallback: string;
    skillEntries: string;
    skillPackages: string;
  };
}

const CURRENT_DIR = dirname(fileURLToPath(import.meta.url));
const LOCALES_ROOT = resolve(CURRENT_DIR, '../../../src/locales/langs');

function loadCommonLocale(locale: 'en-US' | 'zh-CN') {
  return JSON.parse(
    readFileSync(resolve(LOCALES_ROOT, locale, 'common.json'), 'utf8'),
  ) as CommonLocaleShape;
}

const zhCommon = loadCommonLocale('zh-CN');
const enCommon = loadCommonLocale('en-US');

function toVariants(zhValue: string, enValue: string) {
  return [zhValue, enValue];
}

function escapeRegex(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

export function buildLocaleVariantPattern(variants: readonly string[]) {
  return new RegExp(
    variants.map((variant) => escapeRegex(variant)).join('|'),
    'i',
  );
}

export function includesLocaleVariant(
  text: string,
  variants: readonly string[],
) {
  return variants.some((variant) => text.includes(variant));
}

export const sharedAIChatCopyContract = {
  agentProfileAria: toVariants(
    zhCommon.globalAiChat.agentProfileAria,
    enCommon.globalAiChat.agentProfileAria,
  ),
  agentProfileHint: toVariants(
    zhCommon.globalAiChat.agentProfileHint,
    enCommon.globalAiChat.agentProfileHint,
  ),
  agentProfileKnowledgeBases: toVariants(
    zhCommon.globalAiChat.mentionSectionKbs,
    enCommon.globalAiChat.mentionSectionKbs,
  ),
  agentProfileSkillEntries: toVariants(
    zhCommon.globalAiChat.skillEntries,
    enCommon.globalAiChat.skillEntries,
  ),
  agentProfileSkillPackages: toVariants(
    zhCommon.globalAiChat.skillPackages,
    enCommon.globalAiChat.skillPackages,
  ),
  knowledgeBaseFallback: toVariants(
    zhCommon.globalAiChat.knowledgeBaseFallback,
    enCommon.globalAiChat.knowledgeBaseFallback,
  ),
  noDescription: toVariants(
    zhCommon.globalAiChat.noDescription,
    enCommon.globalAiChat.noDescription,
  ),
  noKnowledgeBases: toVariants(
    zhCommon.globalAiChat.noKnowledgeBases,
    enCommon.globalAiChat.noKnowledgeBases,
  ),
  noSkillPackages: toVariants(
    zhCommon.globalAiChat.noSkillPackages,
    enCommon.globalAiChat.noSkillPackages,
  ),
  noSkillsInPackage: toVariants(
    zhCommon.globalAiChat.noSkillsInPackage,
    enCommon.globalAiChat.noSkillsInPackage,
  ),
  diagnosticContextSourcesLabel: toVariants(
    zhCommon.globalAiChat.diagnosticContextSourcesLabel,
    enCommon.globalAiChat.diagnosticContextSourcesLabel,
  ),
  diagnosticProtocolPathLabel: toVariants(
    zhCommon.globalAiChat.diagnosticProtocolPathLabel,
    enCommon.globalAiChat.diagnosticProtocolPathLabel,
  ),
  diagnosticSelectedSkillsLabel: toVariants(
    zhCommon.globalAiChat.diagnosticSelectedSkillsLabel,
    enCommon.globalAiChat.diagnosticSelectedSkillsLabel,
  ),
  diagnosticSelectedToolsLabel: toVariants(
    zhCommon.globalAiChat.diagnosticSelectedToolsLabel,
    enCommon.globalAiChat.diagnosticSelectedToolsLabel,
  ),
  diagnosticTerminationReasonLabel: toVariants(
    zhCommon.globalAiChat.diagnosticTerminationReasonLabel,
    enCommon.globalAiChat.diagnosticTerminationReasonLabel,
  ),
  headerMemory: toVariants(zhCommon.aiPanel.memory, enCommon.aiPanel.memory),
  headerMoreActions: toVariants(
    zhCommon.aiPanel.moreActions,
    enCommon.aiPanel.moreActions,
  ),
  headerNewChat: toVariants(zhCommon.aiPanel.newChat, enCommon.aiPanel.newChat),
  headerRefreshContext: toVariants(
    zhCommon.globalAiChat.rebuildContextCompact,
    enCommon.globalAiChat.rebuildContextCompact,
  ),
  headerRunTimeline: toVariants(
    zhCommon.globalAiChat.runTimeline,
    enCommon.globalAiChat.runTimeline,
  ),
  headerShowDiagnostics: toVariants(
    zhCommon.globalAiChat.contextDiagnostics,
    enCommon.globalAiChat.contextDiagnostics,
  ),
  skillBindingFallback: toVariants(
    zhCommon.globalAiChat.skillBindingFallback,
    enCommon.globalAiChat.skillBindingFallback,
  ),
} as const;
