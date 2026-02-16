/**
 * Test Scaffold — 测试脚手架 + 数据模拟器
 *
 * 根据 CrudConfig 生成:
 * 1. 后端 pytest 测试文件骨架
 * 2. 前端 vitest 测试文件骨架
 * 3. 测试数据工厂 (factory)
 */

import type { CrudConfig, FieldConfig } from '../types';

/**
 * 生成 pytest 测试文件内容
 */
export function generatePytestFile(config: CrudConfig): string {
  const module = config.module;
  const className = toPascalCase(module);

  const lines = [
    `"""Tests for ${className} CRUD API."""`,
    `import pytest`,
    `from httpx import AsyncClient`,
    ``,
    `from tests.conftest import get_admin_token`,
    ``,
    ``,
    `@pytest.fixture`,
    `def ${module}_data():`,
    `    """Factory for ${className} test data."""`,
    `    return {`,
  ];

  for (const field of config.fields.filter((f) => !isSystemField(f.name))) {
    const value = getTestValue(field);
    lines.push(`        "${field.name}": ${value},`);
  }

  lines.push(`    }`);
  lines.push(``);
  lines.push(``);
  lines.push(`class Test${className}CRUD:`);
  lines.push(`    """${className} CRUD test suite."""`);
  lines.push(``);
  lines.push(`    BASE_URL = "/api/admin/${module}s"`);
  lines.push(``);
  lines.push(`    @pytest.mark.asyncio`);
  lines.push(`    async def test_create(self, client: AsyncClient, ${module}_data):`);
  lines.push(`        """Test create ${module}."""`);
  lines.push(`        response = await client.post(self.BASE_URL, json=${module}_data)`);
  lines.push(`        assert response.status_code == 201`);
  lines.push(`        data = response.json()["data"]`);
  lines.push(`        assert data["id"] is not None`);

  for (const field of config.fields.filter((f) => f.required && !isSystemField(f.name)).slice(0, 3)) {
    lines.push(`        assert data["${field.name}"] == ${module}_data["${field.name}"]`);
  }

  lines.push(``);
  lines.push(`    @pytest.mark.asyncio`);
  lines.push(`    async def test_list(self, client: AsyncClient):`);
  lines.push(`        """Test list ${module}s."""`);
  lines.push(`        response = await client.get(self.BASE_URL)`);
  lines.push(`        assert response.status_code == 200`);
  lines.push(`        data = response.json()`);
  lines.push(`        assert "items" in data`);
  lines.push(`        assert "total" in data`);
  lines.push(``);
  lines.push(`    @pytest.mark.asyncio`);
  lines.push(`    async def test_get(self, client: AsyncClient, ${module}_data):`);
  lines.push(`        """Test get ${module} by id."""`);
  lines.push(`        create_resp = await client.post(self.BASE_URL, json=${module}_data)`);
  lines.push(`        item_id = create_resp.json()["data"]["id"]`);
  lines.push(`        response = await client.get(f"{self.BASE_URL}/{item_id}")`);
  lines.push(`        assert response.status_code == 200`);
  lines.push(``);
  lines.push(`    @pytest.mark.asyncio`);
  lines.push(`    async def test_update(self, client: AsyncClient, ${module}_data):`);
  lines.push(`        """Test update ${module}."""`);
  lines.push(`        create_resp = await client.post(self.BASE_URL, json=${module}_data)`);
  lines.push(`        item_id = create_resp.json()["data"]["id"]`);
  lines.push(`        update_data = {**${module}_data, "${config.fields[0]?.name || 'name'}": "updated"}`);
  lines.push(`        response = await client.put(f"{self.BASE_URL}/{item_id}", json=update_data)`);
  lines.push(`        assert response.status_code == 200`);
  lines.push(``);
  lines.push(`    @pytest.mark.asyncio`);
  lines.push(`    async def test_delete(self, client: AsyncClient, ${module}_data):`);
  lines.push(`        """Test delete ${module}."""`);
  lines.push(`        create_resp = await client.post(self.BASE_URL, json=${module}_data)`);
  lines.push(`        item_id = create_resp.json()["data"]["id"]`);
  lines.push(`        response = await client.delete(f"{self.BASE_URL}/{item_id}")`);
  lines.push(`        assert response.status_code == 200`);
  lines.push(``);

  if (config.search_config?.fields && config.search_config.fields.length > 0) {
    const searchField = config.search_config.fields[0]!;
    lines.push(`    @pytest.mark.asyncio`);
    lines.push(`    async def test_search(self, client: AsyncClient):`);
    lines.push(`        """Test search ${module}s."""`);
    lines.push(`        response = await client.get(`);
    lines.push(`            self.BASE_URL,`);
    lines.push(`            params={"filter[${searchField.field}][${searchField.operator}]": "test"},`);
    lines.push(`        )`);
    lines.push(`        assert response.status_code == 200`);
  }

  return lines.join('\n');
}

/**
 * 生成 vitest 测试文件内容
 */
export function generateVitestFile(config: CrudConfig): string {
  const module = config.module;
  const className = toPascalCase(module);

  return [
    `import { describe, expect, it } from 'vitest';`,
    ``,
    `import { generateMockData } from '../composables/use-mock-data';`,
    ``,
    `describe('${className} Mock Data', () => {`,
    `  it('should generate mock data', () => {`,
    `    const config = {} as unknown; // TODO: use actual config`,
    `    const data = generateMockData(config, 10);`,
    `    expect(data).toHaveLength(10);`,
    `    expect(data[0]).toHaveProperty('id');`,
    `  });`,
    ``,
    `  it('should have required fields', () => {`,
    `    const config = {} as unknown;`,
    `    const data = generateMockData(config, 1);`,
    `    const row = data[0];`,
    ...config.fields
      .filter((f) => f.required)
      .slice(0, 5)
      .map((f) => `    expect(row).toHaveProperty('${f.name}');`),
    `  });`,
    `});`,
  ].join('\n');
}

// ============================================================
// Helpers
// ============================================================

function isSystemField(name: string): boolean {
  return [
    'id', 'created_at', 'updated_at', 'is_deleted',
    'deleted_at', 'delete_level', 'tenant_id', 'sort_order',
  ].includes(name);
}

function getTestValue(field: FieldConfig): string {
  switch (field.type) {
    case 'string': { return `"test_${field.name}"`; }
    case 'text': { return `"Test ${field.name} content"`; }
    case 'integer': { return '1'; }
    case 'float':
    case 'decimal': { return '99.99'; }
    case 'boolean': { return 'True'; }
    case 'datetime':
    case 'date': { return '"2026-01-01T00:00:00"'; }
    case 'enum': { return `"${field.default || 'active'}"`; }
    case 'json': { return '{}'; }
    case 'file': { return '"https://example.com/test.jpg"'; }
    default: { return `"test_${field.name}"`; }
  }
}

function toPascalCase(str: string): string {
  return str
    .split(/[-_]/)
    .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
    .join('');
}
