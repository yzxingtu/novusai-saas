# CRUD Generator CLI 使用指南

## 快速开始

### 安装

CLI 随后端项目自带，无需额外安装。确保在 `backend/` 目录下运行：

```bash
# 方式 1: 直接调用模块
python -m app.codegen.cli --help

# 方式 2: 通过 pyproject.toml 注册的入口（需 pip install -e .）
crud-gen --help
```

### 第一个生成示例

```bash
# 1. 创建配置模板
python -m app.codegen.cli init -m article -t articles -o article.json

# 2. 校验配置
python -m app.codegen.cli validate -c article.json

# 3. 预览生成结果
python -m app.codegen.cli preview -c article.json

# 4. 生成代码并写盘
python -m app.codegen.cli generate -c article.json
```

---

## 全局选项

| 选项 | 缩写 | 说明 |
|------|------|------|
| `--verbose` | `-v` | 详细输出模式 |
| `--output-dir PATH` | `-o` | 覆盖项目根目录（默认自动检测） |
| `--format [json\|table\|text]` | | 输出格式（默认 text） |
| `--help` | `-h` | 显示帮助 |

---

## 命令参考

### `generate` — 单表代码生成

从 CrudConfig JSON/YAML 配置生成全栈 CRUD 代码。

```bash
python -m app.codegen.cli generate -c ./configs/user.json
python -m app.codegen.cli generate -c ./configs/user.json --dry-run
python -m app.codegen.cli generate -c ./configs/user.json --force --conflict overwrite
```

| 参数 | 缩写 | 说明 |
|------|------|------|
| `--config PATH` | `-c` | 配置文件路径（必填） |
| `--dry-run` | | 仅预览，不写盘 |
| `--force` | `-f` | 跳过确认直接写盘 |
| `--conflict [skip\|overwrite\|merge]` | | 冲突策略（默认 skip） |

**流程：**
1. 读取并校验 CrudConfig
2. 调用 Generator 生成代码
3. 预览文件列表（新建/冲突/合并）
4. 确认后写盘
5. 自动创建生成记录

---

### `preview` — 预览生成结果

预览生成的文件列表，不写入磁盘。

```bash
python -m app.codegen.cli preview -c ./configs/user.json
python -m app.codegen.cli preview -c ./configs/user.json --content --format json
```

| 参数 | 说明 |
|------|------|
| `--config PATH` / `-c` | 配置文件路径（必填） |
| `--content` | 输出中包含文件内容 |

---

### `batch` — 多表批量生成

从 BatchCrudProject 配置批量生成多实体代码。

```bash
python -m app.codegen.cli batch -c ./configs/project.json
python -m app.codegen.cli batch -c ./configs/project.json --entity user,role
python -m app.codegen.cli batch -c ./configs/project.json --dry-run
```

| 参数 | 说明 |
|------|------|
| `--config PATH` / `-c` | BatchCrudProject 配置文件（必填） |
| `--entity NAMES` | 只生成指定实体（逗号分隔模块名） |
| `--dry-run` | 仅预览，不写盘 |
| `--force` / `-f` | 跳过确认 |
| `--conflict [skip\|overwrite\|merge]` | 冲突策略 |

---

### `validate` — 校验配置

校验 CrudConfig 或 BatchCrudProject 配置文件的合法性。

```bash
python -m app.codegen.cli validate -c ./configs/user.json
python -m app.codegen.cli validate -c ./configs/project.json --batch
python -m app.codegen.cli validate -c ./configs/user.json --format json
```

| 参数 | 说明 |
|------|------|
| `--config PATH` / `-c` | 配置文件路径（必填） |
| `--batch` | 按 BatchCrudProject 格式校验 |

---

### `init` — 创建配置模板

交互式创建 CrudConfig 或 BatchCrudProject 模板。

```bash
python -m app.codegen.cli init -m user -t users -o user.json
python -m app.codegen.cli init --batch -o project.json
python -m app.codegen.cli init  # 输出到 stdout
```

| 参数 | 缩写 | 说明 |
|------|------|------|
| `--output PATH` | `-o` | 输出文件路径（默认 stdout） |
| `--batch` | | 生成 BatchCrudProject 模板 |
| `--module NAME` | `-m` | 预填充模块名 |
| `--table NAME` | `-t` | 预填充表名 |

---

### `rollback` — 回滚生成

根据生成记录 ID，删除该次生成创建的文件。

```bash
python -m app.codegen.cli rollback -r 42
python -m app.codegen.cli rollback -r 42 --dry-run
python -m app.codegen.cli rollback -r 42 --force
```

| 参数 | 说明 |
|------|------|
| `--record-id ID` / `-r` | 生成记录 ID（必填） |
| `--dry-run` | 仅预览要删除的文件 |
| `--force` / `-f` | 跳过确认 |

> 需要数据库访问。通过 `list-records` 查看可用记录。

---

### `delete` — 删除生成文件

根据配置文件重新计算文件路径，删除已存在的文件。

```bash
python -m app.codegen.cli delete -c ./configs/user.json --dry-run
python -m app.codegen.cli delete -c ./configs/user.json --force
```

| 参数 | 说明 |
|------|------|
| `--config PATH` / `-c` | 配置文件路径（必填） |
| `--dry-run` | 仅预览要删除的文件 |
| `--force` / `-f` | 跳过确认 |

---

### `list-records` — 查看生成历史

查看最近的代码生成记录。

```bash
python -m app.codegen.cli list-records
python -m app.codegen.cli list-records -n 20
python -m app.codegen.cli list-records --format json
```

| 参数 | 说明 |
|------|------|
| `--limit N` / `-n` | 显示条数（默认 10） |

> 需要数据库访问。

---

## 配置文件格式

### CrudConfig（单表）

```json
{
  "module": "article",
  "table_name": "articles",
  "display_name": "文章",
  "display_name_en": "Article",
  "scope": "tenant",
  "parent_menu": "",
  "description": "",
  "has_status_toggle": false,
  "fields": [
    {
      "name": "title",
      "type": "string",
      "label_zh": "标题",
      "label_en": "Title",
      "required": true,
      "max_length": 200,
      "searchable": true,
      "search_op": "ilike",
      "in_list": true,
      "in_form": true
    }
  ],
  "enums": [],
  "relations": [],
  "indexes": [],
  "custom_slots": []
}
```

### 字段类型对照表

| type | 数据库 | 前端组件 |
|------|--------|----------|
| `string` | VARCHAR | Input |
| `text` | TEXT | Textarea |
| `integer` | INTEGER | InputNumber |
| `float` | FLOAT | InputNumber |
| `boolean` | BOOLEAN | Switch |
| `datetime` | TIMESTAMP | DatePicker |
| `date` | DATE | DatePicker |
| `json` | JSONB | CodeEditor |

### BatchCrudProject（多表）

```json
{
  "entities": [
    { "module": "user", "table_name": "users", "...": "..." },
    { "module": "role", "table_name": "roles", "...": "..." }
  ],
  "cross_relations": [
    {
      "source_entity": "user_role",
      "target_entity": "user",
      "relation_type": "belongs_to",
      "foreign_key": "user_id"
    }
  ],
  "shared_enums": []
}
```

---

## 常见场景

### CI/CD 集成

```bash
# 在 CI 中校验配置（不写盘）
python -m app.codegen.cli validate -c configs/user.json --format json

# 在 CI 中预览生成（检查差异）
python -m app.codegen.cli preview -c configs/user.json --format json

# 自动化生成（跳过确认）
python -m app.codegen.cli generate -c configs/user.json --force --conflict skip
```

### 批量生成多表

```bash
# 创建批量模板
python -m app.codegen.cli init --batch -o project.json

# 编辑 project.json，添加多个 entities...

# 校验
python -m app.codegen.cli validate -c project.json --batch

# 预览
python -m app.codegen.cli batch -c project.json --dry-run

# 生成
python -m app.codegen.cli batch -c project.json --force
```

### 只生成部分实体

```bash
python -m app.codegen.cli batch -c project.json --entity user,role --dry-run
```

---

## 故障排除

| 错误 | 原因 | 解决 |
|------|------|------|
| `Config file not found` | 配置文件路径错误 | 检查 `-c` 参数路径 |
| `Validation failed` | Schema 校验失败 | 运行 `validate` 查看详情 |
| `Failed to load record` | 数据库连接失败 | 确保 `.env` 配置正确 |
| `No existing generated files` | 文件尚未生成 | 先运行 `generate` |

### 环境变量

CLI 使用与后端相同的 `.env` 配置，主要需要：

```env
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname
APP_ENV=development
```
