import { describe, expect, it } from 'vitest';

import {
  buildCodegenSavePayload,
  buildGenerateNextSteps,
  formatConflictItem,
  parseImportedYaml,
} from '../workflow-helpers';

describe('codegen workflow helpers', () => {
  it('derives next steps from generation and migration state', () => {
    expect(
      buildGenerateNextSteps({
        conflicts: [],
        errors: [],
        files_created: ['backend/app/models/system/article.py'],
        files_modified: [],
        migration: {
          migration_path: 'backend/migrations/versions/001_article.py',
          success: true,
        },
        success: true,
      }),
    ).toEqual([
      'checkMigration',
      'migrationAlreadyApplied',
      'restartIfNeeded',
      'reviewCode',
    ]);

    expect(
      buildGenerateNextSteps({
        conflicts: [],
        errors: [],
        files_created: [],
        files_modified: [],
        migration: {
          phase: 'noop',
          success: true,
        },
        success: true,
      }),
    ).toEqual([
      'migrationNoChanges',
      'reviewCode',
    ]);
  });

  it('builds save payloads with trimmed fields and sensible fallbacks', () => {
    expect(
      buildCodegenSavePayload(
        {
          display_name: '  Article  ',
          module: ' system ',
          resource: ' article ',
        },
        { unnamedLabel: 'Unnamed' },
      ),
    ).toEqual({
      config_json: {
        display_name: '  Article  ',
        module: ' system ',
        resource: ' article ',
      },
      display_name: 'Article',
      display_name_en: 'article',
      module: 'system',
      name: 'Article',
      resource: 'article',
    });

    expect(
      buildCodegenSavePayload(
        {
          display_name: '',
          module: 'system',
          name: '',
          resource: 'notice',
        },
        { unnamedLabel: 'Unnamed' },
      ).name,
    ).toBe('Unnamed');
  });

  it('parses YAML mappings and rejects invalid shapes', () => {
    expect(parseImportedYaml('resource: article\nmodule: system\n')).toEqual({
      module: 'system',
      resource: 'article',
    });
    expect(parseImportedYaml('- item')).toBeNull();
    expect(parseImportedYaml('hello')).toBeNull();
  });

  it('formats conflict items using path when present', () => {
    expect(formatConflictItem({ path: 'backend/app/models/article.py' })).toBe(
      'backend/app/models/article.py',
    );
    expect(formatConflictItem({ reason: 'file_exists' })).toBe(
      '{"reason":"file_exists"}',
    );
  });
});
