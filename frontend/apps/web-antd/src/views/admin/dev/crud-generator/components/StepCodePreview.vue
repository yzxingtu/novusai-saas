<script setup lang="ts">
import { computed, ref } from 'vue';

import {
  Button,
  Card,
  Empty,
  Tabs,
  Tag,
  Tooltip,
  Tree,
} from 'ant-design-vue';

import { $t } from '#/locales';

import type { CrudConfig } from '../types';

const props = defineProps<{
  config: CrudConfig;
}>();

const T = 'admin.dev.crudGenerator.preview';

/** 预览文件结构（基于配置动态生成） */
interface PreviewFile {
  key: string;
  title: string;
  group: string;
  lang: string;
  content: string;
}

const activeTab = ref<'code' | 'ddl'>('code');
const selectedFileKey = ref<string>('');
const copied = ref(false);

/** 根据当前配置生成预览文件列表 */
const previewFiles = computed<PreviewFile[]>(() => {
  const mod = props.config.module || 'example';
  const table = props.config.table_name || 'examples';
  const modelName = mod
    .split(/[-_]/)
    .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
    .join('');

  const files: PreviewFile[] = [];

  // Backend
  files.push({
    key: `backend/model`,
    title: `app/models/${mod}.py`,
    group: 'backend',
    lang: 'python',
    content: generateModelPreview(modelName, table, props.config),
  });
  files.push({
    key: `backend/schema`,
    title: `app/schemas/${mod}.py`,
    group: 'backend',
    lang: 'python',
    content: generateSchemaPreview(modelName, props.config),
  });
  files.push({
    key: `backend/repository`,
    title: `app/repositories/${mod}_repository.py`,
    group: 'backend',
    lang: 'python',
    content: generateRepoPreview(modelName),
  });
  files.push({
    key: `backend/service`,
    title: `app/services/${mod}_service.py`,
    group: 'backend',
    lang: 'python',
    content: generateServicePreview(modelName),
  });
  files.push({
    key: `backend/controller`,
    title: `app/api/${props.config.scope === 'admin' ? 'admin' : 'tenant'}/${mod}.py`,
    group: 'backend',
    lang: 'python',
    content: generateControllerPreview(modelName, mod, props.config),
  });

  // Frontend
  files.push({
    key: `frontend/api`,
    title: `api/${props.config.scope === 'admin' ? 'admin' : 'tenant'}/${mod}.ts`,
    group: 'frontend',
    lang: 'typescript',
    content: generateApiPreview(modelName, mod, props.config),
  });
  files.push({
    key: `frontend/data`,
    title: `views/${props.config.scope === 'admin' ? 'admin' : 'tenant'}/${mod}/data.ts`,
    group: 'frontend',
    lang: 'typescript',
    content: generateDataPreview(props.config),
  });
  files.push({
    key: `frontend/index`,
    title: `views/${props.config.scope === 'admin' ? 'admin' : 'tenant'}/${mod}/index.vue`,
    group: 'frontend',
    lang: 'vue',
    content: generateIndexVuePreview(mod, props.config),
  });
  files.push({
    key: `frontend/form`,
    title: `views/${props.config.scope === 'admin' ? 'admin' : 'tenant'}/${mod}/modules/form.vue`,
    group: 'frontend',
    lang: 'vue',
    content: generateFormVuePreview(modelName),
  });

  // i18n
  files.push({
    key: `i18n/zh`,
    title: `locales/zh-CN/${props.config.scope === 'admin' ? 'admin' : 'tenant'}/${mod}.json`,
    group: 'i18n',
    lang: 'json',
    content: generateI18nPreview(props.config, 'zh'),
  });
  files.push({
    key: `i18n/en`,
    title: `locales/en-US/${props.config.scope === 'admin' ? 'admin' : 'tenant'}/${mod}.json`,
    group: 'i18n',
    lang: 'json',
    content: generateI18nPreview(props.config, 'en'),
  });

  // Migration
  files.push({
    key: `migration/alembic`,
    title: `migrations/versions/create_${table}.py`,
    group: 'migration',
    lang: 'python',
    content: generateMigrationPreview(table, props.config),
  });

  // Test
  if (props.config.test.generate_api_tests) {
    files.push({
      key: `test/api`,
      title: `tests/api/test_${mod}.py`,
      group: 'test',
      lang: 'python',
      content: generateTestPreview(modelName, mod),
    });
  }

  return files;
});

/** 文件树数据 */
const treeData = computed(() => {
  const groups: Record<string, { title: string; key: string; icon: string; children: { title: string; key: string; isLeaf: boolean }[] }> = {};

  const groupMeta: Record<string, { titleKey: string; icon: string }> = {
    backend: { titleKey: 'groupBackend', icon: 'icon-[lucide--server]' },
    frontend: { titleKey: 'groupFrontend', icon: 'icon-[lucide--monitor]' },
    i18n: { titleKey: 'groupI18n', icon: 'icon-[lucide--languages]' },
    migration: { titleKey: 'groupMigration', icon: 'icon-[lucide--database]' },
    test: { titleKey: 'groupTest', icon: 'icon-[lucide--flask-conical]' },
  };

  for (const file of previewFiles.value) {
    if (!groups[file.group]) {
      const meta = groupMeta[file.group] ?? { titleKey: file.group, icon: '' };
      groups[file.group] = {
        title: $t(`${T}.${meta.titleKey}`),
        key: `group-${file.group}`,
        icon: meta.icon,
        children: [],
      };
    }
    groups[file.group]!.children.push({
      title: file.title.split('/').pop() ?? file.title,
      key: file.key,
      isLeaf: true,
    });
  }

  return Object.values(groups);
});

const selectedFile = computed(() =>
  previewFiles.value.find((f) => f.key === selectedFileKey.value),
);

const lineCount = computed(() =>
  selectedFile.value ? selectedFile.value.content.split('\n').length : 0,
);

/** DDL 预览 */
const ddlContent = computed(() => generateDDLPreview(props.config));

function onTreeSelect(keys: (string | number)[]) {
  if (keys.length > 0 && typeof keys[0] === 'string' && !keys[0].startsWith('group-')) {
    selectedFileKey.value = keys[0];
  }
}

async function copyCode() {
  const content = activeTab.value === 'ddl' ? ddlContent.value : selectedFile.value?.content;
  if (!content) return;
  try {
    await navigator.clipboard.writeText(content);
    copied.value = true;
    setTimeout(() => { copied.value = false; }, 2000);
  } catch {
    // clipboard not available
  }
}

// ============================================================
// Preview generators (simplified skeleton code)
// ============================================================

function generateModelPreview(model: string, table: string, cfg: CrudConfig): string {
  const base = cfg.scope === 'admin' ? 'BaseModel' : 'TenantModel';
  const fields = cfg.fields.map((f) => {
    const colType = { string: 'String', text: 'Text', integer: 'Integer', float: 'Float', decimal: 'Numeric', boolean: 'Boolean', datetime: 'DateTime', date: 'Date', json: 'JSON', enum: 'String', file: 'String' }[f.type] || 'String';
    const args = f.max_length && f.type === 'string' ? `(${f.max_length})` : '';
    const nullable = f.nullable ? ', nullable=True' : ', nullable=False';
    return `    ${f.name}: Mapped[${colType === 'Boolean' ? 'bool' : colType === 'Integer' ? 'int' : 'str'}] = mapped_column(${colType}${args}${nullable})`;
  });

  return `from sqlalchemy import ${[...new Set(cfg.fields.map((f) => ({ string: 'String', text: 'Text', integer: 'Integer', float: 'Float', decimal: 'Numeric', boolean: 'Boolean', datetime: 'DateTime', date: 'Date', json: 'JSON', enum: 'String', file: 'String' }[f.type] || 'String')))].join(', ')}
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import ${base}


class ${model}(${base}):
    __tablename__ = "${table}"
    __filterable__ = [${cfg.fields.filter((f) => f.filterable).map((f) => `"${f.name}"`).join(', ')}]
    __sortable__ = [${cfg.fields.filter((f) => f.sortable).map((f) => `"${f.name}"`).join(', ')}]

${fields.join('\n')}
`;
}

function generateSchemaPreview(model: string, cfg: CrudConfig): string {
  const fields = cfg.fields.map((f) => {
    const pyType = { string: 'str', text: 'str', integer: 'int', float: 'float', decimal: 'float', boolean: 'bool', datetime: 'datetime', date: 'date', json: 'dict', enum: 'str', file: 'str' }[f.type] || 'str';
    const opt = f.required ? '' : ' | None = None';
    return `    ${f.name}: ${pyType}${opt}`;
  });

  return `from pydantic import BaseModel


class ${model}Create(BaseModel):
${fields.join('\n')}


class ${model}Update(BaseModel):
${fields.map((f) => f.replace(': ', ': ').replace(/(?<! \| None) = None/, '') + ' | None = None').join('\n')}


class ${model}Response(BaseModel):
    id: int
${fields.join('\n')}
`;
}

function generateRepoPreview(model: string): string {
  return `from app.core.base_repository import TenantRepository

from app.models.${model.toLowerCase()} import ${model}


class ${model}Repository(TenantRepository[${model}]):
    pass
`;
}

function generateServicePreview(model: string): string {
  return `from app.core.base_service import TenantService

from app.repositories.${model.toLowerCase()}_repository import ${model}Repository


class ${model}Service(TenantService[${model}Repository]):
    repository_class = ${model}Repository
`;
}

function generateControllerPreview(model: string, mod: string, cfg: CrudConfig): string {
  const ctrl = cfg.scope === 'admin' ? 'GlobalController' : 'TenantController';
  return `from app.core.controller import ${ctrl}, permission_resource, action_read, action_create, action_update, action_delete
from app.services.${mod}_service import ${model}Service


@permission_resource("${mod}")
class ${model}Controller(${ctrl}):

    @action_read
    async def list(self):
        service = self.get_service(self.db${cfg.scope !== 'admin' ? ', self.tenant_id' : ''})
        items, total = await service.query_list(self.query_params)
        return self.paginated(items, total, self.query_params.page, self.query_params.page_size)

    @action_create
    async def create(self, data: dict):
        service = self.get_service(self.db${cfg.scope !== 'admin' ? ', self.tenant_id' : ''})
        item = await service.create(data)
        return self.created(data=item)

    @action_update
    async def update(self, id: int, data: dict):
        service = self.get_service(self.db${cfg.scope !== 'admin' ? ', self.tenant_id' : ''})
        item = await service.update(id, data)
        return self.success(data=item)

    @action_delete
    async def delete(self, id: int):
        service = self.get_service(self.db${cfg.scope !== 'admin' ? ', self.tenant_id' : ''})
        await service.delete(id)
        return self.deleted()
`;
}

function generateApiPreview(model: string, mod: string, cfg: CrudConfig): string {
  const prefix = cfg.scope === 'admin' ? 'admin' : 'tenant';
  return `import { requestClient } from '#/utils/request';

export interface ${model}Info {
  id: number;
${cfg.fields.map((f) => `  ${f.name}: ${{ string: 'string', text: 'string', integer: 'number', float: 'number', decimal: 'number', boolean: 'boolean', datetime: 'string', date: 'string', json: 'Record<string, unknown>', enum: 'string', file: 'string' }[f.type] || 'string'};`).join('\n')}
}

export function get${model}ListApi(params?: Record<string, unknown>) {
  return requestClient.get('/${prefix}/${mod}', { params });
}

export function create${model}Api(data: Partial<${model}Info>) {
  return requestClient.post('/${prefix}/${mod}', data);
}

export function update${model}Api(id: number, data: Partial<${model}Info>) {
  return requestClient.put(\`/${prefix}/${mod}/\${id}\`, data);
}

export function delete${model}Api(id: number) {
  return requestClient.delete(\`/${prefix}/${mod}/\${id}\`);
}
`;
}

function generateDataPreview(cfg: CrudConfig): string {
  const searchFields = cfg.fields.filter((f) => f.searchable);
  const listFields = cfg.fields.filter((f) => f.in_list);

  return `import { $t } from '#/locales';
import { searchInput, statusSelect } from '#/adapter/vxe-table';

export function useSearchSchema() {
  return [
${searchFields.map((f) => `    searchInput('${f.name}', $t('${cfg.module}.${f.name}')),`).join('\n')}
  ];
}

export function useColumns() {
  return [
${listFields.map((f) => `    { field: '${f.name}', title: $t('${cfg.module}.${f.name}')${f.list_width ? `, width: ${f.list_width}` : ''} },`).join('\n')}
  ];
}
`;
}

function generateIndexVuePreview(mod: string, cfg: CrudConfig): string {
  return `<script setup lang="ts">
import { useCrudPage } from '#/adapter/vxe-table';
import { get${mod}ListApi, delete${mod}Api } from '#/api/...';
import { useSearchSchema, useColumns } from './data';
import Form from './modules/form.vue';

const { Grid, FormDrawer, onCreate, onEdit, onDelete } = useCrudPage({
  formComponent: Form,
  listApi: get${mod}ListApi,
  deleteApi: delete${mod}Api,
  searchSchema: useSearchSchema(),
  columns: useColumns(),${cfg.recyclable ? '\n  recycleBin: true,' : ''}
});
<\/script>

<template>
  <Grid @create="onCreate" @edit="onEdit" @delete="onDelete" />
  <FormDrawer />
</template>
`;
}

function generateFormVuePreview(model: string): string {
  return `<script setup lang="ts">
import { useCrudDrawer } from '#/composables';
import { useVbenForm } from '#/adapter/form';

const emits = defineEmits<{ success: [] }>();

const [Form, formApi] = useVbenForm({
  schema: useFormSchema(),
  showDefaultActions: false,
});

const { Drawer, isEdit } = useCrudDrawer({
  formApi,
  apiPath: '/.../${model.toLowerCase()}',
  schema: (edit) => useFormSchema(edit),
});
<\/script>

<template>
  <Drawer>
    <Form />
  </Drawer>
</template>
`;
}

function generateI18nPreview(cfg: CrudConfig, lang: 'en' | 'zh'): string {
  const obj: Record<string, string> = {
    title: lang === 'zh' ? cfg.display_name || cfg.module : cfg.display_name_en || cfg.module,
  };
  for (const f of cfg.fields) {
    obj[f.name] = lang === 'zh' ? (f.label_zh || f.name) : (f.label_en || f.name);
  }
  return JSON.stringify(obj, null, 2);
}

function generateMigrationPreview(table: string, cfg: CrudConfig): string {
  const cols = cfg.fields.map((f) => {
    const saType = { string: `sa.String(${f.max_length || 200})`, text: 'sa.Text()', integer: 'sa.Integer()', float: 'sa.Float()', decimal: 'sa.Numeric(10, 2)', boolean: 'sa.Boolean()', datetime: 'sa.DateTime()', date: 'sa.Date()', json: 'sa.JSON()', enum: `sa.String(50)`, file: 'sa.String(500)' }[f.type] || 'sa.String(200)';
    return `        sa.Column("${f.name}", ${saType}, nullable=${f.nullable ? 'True' : 'False'}),`;
  });

  return `"""create ${table} table"""

import sqlalchemy as sa
from alembic import op


def upgrade():
    op.create_table(
        "${table}",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
${cols.join('\n')}
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.false_()),
    )


def downgrade():
    op.drop_table("${table}")
`;
}

function generateTestPreview(model: string, mod: string): string {
  return `import pytest
from httpx import AsyncClient


class Test${model}API:
    """${model} CRUD API tests"""

    @pytest.mark.asyncio
    async def test_list(self, client: AsyncClient):
        resp = await client.get("/${mod}")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_create(self, client: AsyncClient):
        data = {}  # TODO: add test data
        resp = await client.post("/${mod}", json=data)
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_update(self, client: AsyncClient):
        resp = await client.put("/${mod}/1", json={})
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_delete(self, client: AsyncClient):
        resp = await client.delete("/${mod}/1")
        assert resp.status_code == 200
`;
}

function generateDDLPreview(cfg: CrudConfig): string {
  const table = cfg.table_name || 'examples';
  const cols = cfg.fields.map((f) => {
    const sqlType = { string: `VARCHAR(${f.max_length || 200})`, text: 'TEXT', integer: 'INTEGER', float: 'FLOAT', decimal: 'NUMERIC(10,2)', boolean: 'BOOLEAN', datetime: 'TIMESTAMP', date: 'DATE', json: 'JSONB', enum: 'VARCHAR(50)', file: 'VARCHAR(500)' }[f.type] || 'VARCHAR(200)';
    const notNull = f.nullable ? '' : ' NOT NULL';
    const unique = f.unique ? ' UNIQUE' : '';
    return `    ${f.name} ${sqlType}${notNull}${unique}`;
  });

  const indexes = cfg.fields
    .filter((f) => f.index)
    .map((f) => `CREATE INDEX idx_${table}_${f.name} ON ${table} (${f.name});`);

  return `-- DDL Preview for ${table}
CREATE TABLE ${table} (
    id SERIAL PRIMARY KEY,
${cols.join(',\n')},
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE
);

${indexes.join('\n')}
`;
}
</script>

<template>
  <div class="step-code-preview flex gap-4" style="min-height: 500px;">
    <!-- Left: File Tree -->
    <Card
      :bordered="false"
      class="w-64 shrink-0"
      size="small"
    >
      <template #title>
        <span class="flex items-center gap-1.5 text-sm">
          <span class="icon-[lucide--folder-tree] size-4" />
          {{ $t(`${T}.fileTree`) }}
        </span>
      </template>

      <Tree
        :selected-keys="selectedFileKey ? [selectedFileKey] : []"
        :tree-data="treeData"
        block-node
        default-expand-all
        @select="onTreeSelect"
      >
        <template #title="{ title, isLeaf }">
          <span class="flex items-center gap-1 text-xs">
            <span
              v-if="!isLeaf"
              class="icon-[lucide--folder] size-3.5 text-primary"
            />
            <span
              v-else
              class="icon-[lucide--file-code] size-3.5 opacity-50"
            />
            {{ title }}
          </span>
        </template>
      </Tree>
    </Card>

    <!-- Right: Code Viewer -->
    <Card :bordered="false" class="flex-1" size="small">
      <template #title>
        <Tabs
          v-model:activeKey="activeTab"
          size="small"
          type="card"
        >
          <Tabs.TabPane key="code" :tab="$t(`${T}.code`)" />
          <Tabs.TabPane key="ddl" :tab="$t(`${T}.ddl`)" />
        </Tabs>
      </template>

      <template #extra>
        <div class="flex items-center gap-2">
          <Tag v-if="selectedFile && activeTab === 'code'" color="blue">
            {{ selectedFile.lang }}
          </Tag>
          <span v-if="activeTab === 'code' && selectedFile" class="text-muted-foreground text-xs">
            {{ lineCount }} {{ $t(`${T}.lines`, { count: lineCount }) }}
          </span>
          <Tooltip :title="copied ? $t(`${T}.copied`) : $t(`${T}.copyCode`)">
            <Button size="small" type="text" @click="copyCode">
              <template #icon>
                <span :class="copied ? 'icon-[lucide--check]' : 'icon-[lucide--copy]'" class="size-3.5" />
              </template>
            </Button>
          </Tooltip>
        </div>
      </template>

      <!-- Code Tab -->
      <template v-if="activeTab === 'code'">
        <div v-if="selectedFile" class="code-viewer">
          <div class="text-muted-foreground mb-2 flex items-center gap-1 text-xs">
            <span class="icon-[lucide--file-code] size-3" />
            {{ selectedFile.title }}
          </div>
          <pre class="bg-accent/50 overflow-auto rounded-lg border p-4 text-sm leading-relaxed"><code>{{ selectedFile.content }}</code></pre>
        </div>
        <Empty
          v-else
          :description="$t(`${T}.noFile`)"
          class="py-20"
        >
          <template #image>
            <span class="icon-[lucide--file-code] mx-auto block size-12 opacity-20" />
          </template>
        </Empty>
      </template>

      <!-- DDL Tab -->
      <template v-if="activeTab === 'ddl'">
        <pre class="bg-accent/50 overflow-auto rounded-lg border p-4 text-sm leading-relaxed"><code>{{ ddlContent }}</code></pre>
      </template>
    </Card>
  </div>
</template>
