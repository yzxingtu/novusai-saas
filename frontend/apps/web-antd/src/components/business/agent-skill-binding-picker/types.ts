/**
 * Admin agent skill binding picker shared types / 管理端智能体技能绑定选择器类型
 */
import type { AIAgentSkillGrantInfo } from '#/api/admin/ai-agents';
import type {
  AdminSkillSelectOption,
  AdminSkillSelectOptionExtra,
} from '#/api/admin/skills';

/** Unified draft for form + detail + batchBind payload / 表单与详情共用的技能绑定草稿 */
export interface AgentSkillBindingDraftItem {
  is_system: boolean;
  package_id: null | number;
  package_name: null | string;
  skill_id: number;
  skill_name: string;
  skill_type: null | string;
  source_plugin: null | string;
}

/** Build drafts from current agent grants (detail tab prefill). */
export function grantsToDrafts(
  grants: AIAgentSkillGrantInfo[],
): AgentSkillBindingDraftItem[] {
  return grants.map((g) => ({
    skill_id: g.skill_id,
    skill_name: g.skill_name || g.skill_key || `#${g.skill_id}`,
    package_id: null,
    package_name: g.package_name,
    skill_type: g.skill_type,
    is_system: Boolean(g.package_is_system),
    source_plugin: null,
  }));
}

/** Map API select option to draft (default consent auto). */
export function selectOptionToDraft(
  opt: AdminSkillSelectOption,
): AgentSkillBindingDraftItem {
  const ex: AdminSkillSelectOptionExtra | undefined = opt.extra;
  return {
    skill_id: opt.value,
    skill_name: opt.label,
    package_id: ex?.package_id ?? null,
    package_name: ex?.package_name ?? null,
    skill_type: ex?.skill_type ?? null,
    is_system: Boolean(ex?.is_system),
    source_plugin: ex?.source_plugin ?? null,
  };
}

/** Full batchBind payload: every skill id in desired order. */
export function draftsToBatchPayload(drafts: AgentSkillBindingDraftItem[]): {
  skill_ids: number[];
} {
  const skill_ids = drafts.map((d) => d.skill_id);
  return { skill_ids };
}
