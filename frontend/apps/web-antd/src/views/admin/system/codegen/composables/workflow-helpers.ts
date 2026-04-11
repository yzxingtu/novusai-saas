import yaml from 'js-yaml';

export type GenerateResultPayload = {
  config_id?: null | number;
  conflicts: Array<Record<string, string>>;
  errors: string[];
  files_created: string[];
  files_modified: string[];
  migration?: null | {
    error?: string;
    message?: string;
    migration_path?: string;
    phase?: string;
    success?: boolean;
  };
  module?: null | string;
  resource?: null | string;
  success: boolean;
  table_name?: null | string;
};

export type GenerateNextStepKey =
  | 'checkMigration'
  | 'migrationAlreadyApplied'
  | 'migrationNoChanges'
  | 'restartIfNeeded'
  | 'reviewCode'
  | 'runMigration';

export type CodegenSavePayload = {
  config_json: Record<string, unknown>;
  display_name: string;
  display_name_en: string;
  module: string;
  name: string;
  resource: string;
};

export function buildGenerateNextSteps(
  result: GenerateResultPayload | null,
): GenerateNextStepKey[] {
  if (!result) return [];

  const steps: GenerateNextStepKey[] = [];
  const migration = result.migration;
  const hasWrittenFiles =
    (result.files_created?.length ?? 0) > 0 ||
    (result.files_modified?.length ?? 0) > 0;

  if (migration?.migration_path) {
    steps.push('checkMigration');
  }
  if (migration?.phase === 'noop') {
    steps.push('migrationNoChanges');
  } else if (migration?.success) {
    steps.push('migrationAlreadyApplied');
  } else if (migration || result.success) {
    steps.push('runMigration');
  }
  if (hasWrittenFiles) {
    steps.push('restartIfNeeded');
  }
  steps.push('reviewCode');
  return steps;
}

export function buildCodegenSavePayload(
  json: Record<string, unknown>,
  options: {
    unnamedLabel: string;
  },
): CodegenSavePayload {
  const resource = String(json.resource ?? '').trim();
  const module = String(json.module ?? '').trim();
  const displayName = String(json.display_name ?? '').trim();

  return {
    config_json: json,
    display_name: displayName,
    display_name_en: String(json.display_name_en ?? '').trim() || resource,
    module,
    name:
      String(json.name ?? '').trim() ||
      displayName ||
      options.unnamedLabel,
    resource,
  };
}

export function parseImportedYaml(
  raw: string,
): null | Record<string, unknown> {
  const parsed = yaml.load(raw);
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
    return null;
  }
  return parsed as Record<string, unknown>;
}

export function formatConflictItem(conflict: unknown): string {
  if (
    conflict &&
    typeof conflict === 'object' &&
    'path' in (conflict as Record<string, unknown>)
  ) {
    const path = (conflict as Record<string, unknown>).path;
    if (typeof path === 'string' && path) {
      return path;
    }
  }
  return JSON.stringify(conflict);
}
