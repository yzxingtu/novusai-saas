/**
 * CRUD Generator — Mock 数据生成器
 *
 * 根据 CrudConfig 字段类型自动生成 50-100 条模拟数据，
 * 用于 ListPreview / FormPreview 的实时预览。
 */

import { computed } from 'vue';

import type {
  CrudConfig,
  EnumDefinition,
  FieldConfig,
  FieldType,
  RelationConfig,
} from '../types';

// ============================================================
// 随机工具
// ============================================================

/** Seeded pseudo-random for deterministic output (same config → same data) */
function createRng(seed: number) {
  let s = seed;
  return () => {
    s = (s * 1_664_525 + 1_013_904_223) & 0x7fff_ffff;
    return s / 0x7fff_ffff;
  };
}

function pick<T>(arr: readonly T[], rng: () => number): T {
  return arr[Math.floor(rng() * arr.length)]!;
}

function randInt(min: number, max: number, rng: () => number): number {
  return Math.floor(rng() * (max - min + 1)) + min;
}

function randFloat(min: number, max: number, decimals: number, rng: () => number): number {
  const val = rng() * (max - min) + min;
  const factor = 10 ** decimals;
  return Math.round(val * factor) / factor;
}

// ============================================================
// DEV-ONLY: Mock data pools for preview rendering.
// Chinese sample data is intentional — these are locale-specific
// test fixtures, not UI labels. i18n exemption applies.
// ============================================================

const CHINESE_SURNAMES = [
  '张', '李', '王', '刘', '陈', '杨', '赵', '黄', '周', '吴',
  '徐', '孙', '胡', '朱', '高', '林', '何', '郭', '马', '罗',
];

const CHINESE_GIVEN_NAMES = [
  '伟', '芳', '娜', '秀英', '敏', '静', '丽', '强', '磊', '军',
  '洋', '勇', '艳', '杰', '涛', '明', '超', '秀兰', '霞', '平',
];

const COMPANY_NAMES = [
  '科技', '信息', '网络', '软件', '数据', '智能', '云计算', '电子',
  '通信', '系统', '创新', '未来', '数字', '互联', '安全',
];

const COMPANY_SUFFIXES = [
  '有限公司', '科技有限公司', '信息技术有限公司', '集团',
];

const CITY_NAMES = [
  '北京', '上海', '广州', '深圳', '杭州', '成都', '武汉', '南京',
  '重庆', '西安', '苏州', '天津', '长沙', '郑州', '青岛',
];

const PRODUCT_NAMES = [
  '云服务器', '数据库', '对象存储', '消息队列', 'CDN加速',
  'API网关', '容器服务', '日志服务', '监控平台', '安全防护',
];

const DEPARTMENT_NAMES = [
  '技术部', '产品部', '市场部', '运营部', '财务部',
  '人力资源部', '销售部', '客服部', '行政部', '研发部',
];

const TITLES = [
  '项目方案', '技术文档', '需求分析', '测试报告', '用户手册',
  '设计规范', '接口文档', '部署指南', '运维手册', '培训材料',
];

const LOREM_SENTENCES = [
  '这是一段示例文本，用于模拟实际内容的显示效果。',
  '系统支持多种配置选项，满足不同业务场景的需求。',
  '请根据实际情况进行调整和优化。',
  '该功能已通过全面测试，可以正常使用。',
  '详细信息请参阅相关技术文档。',
];

const EMAIL_DOMAINS = ['example.com', 'test.com', 'demo.cn', 'mail.com'];

const IMAGE_URLS = [
  'https://picsum.photos/seed/1/200/200',
  'https://picsum.photos/seed/2/200/200',
  'https://picsum.photos/seed/3/200/200',
  'https://picsum.photos/seed/4/200/200',
  'https://picsum.photos/seed/5/200/200',
];

const FILE_URLS = [
  '/uploads/mock/document-1.pdf',
  '/uploads/mock/report-2.xlsx',
  '/uploads/mock/image-3.png',
  '/uploads/mock/data-4.csv',
];

// ============================================================
// 字段值生成
// ============================================================

function generateFieldValue(
  field: FieldConfig,
  index: number,
  enums: EnumDefinition[],
  _relations: RelationConfig[],
  rng: () => number,
): unknown {
  // Enum field
  if (field.type === 'enum' && field.enum_ref) {
    const enumDef = enums.find((e) => e.name === field.enum_ref);
    if (enumDef && enumDef.values.length > 0) {
      return pick(enumDef.values, rng).value;
    }
  }

  // Relation field (foreign key)
  if (field.relation_ref) {
    return randInt(1, 20, rng);
  }

  return generateByType(field, index, rng);
}

function generateByType(
  field: FieldConfig,
  index: number,
  rng: () => number,
): unknown {
  const name = field.name.toLowerCase();
  const type: FieldType = field.type;

  switch (type) {
    case 'string': {
      return generateStringByName(name, index, rng);
    }
    case 'text': {
      const count = randInt(1, 3, rng);
      return Array.from({ length: count }, () => pick(LOREM_SENTENCES, rng)).join('');
    }
    case 'integer': {
      if (name === 'sort' || name === 'sort_order' || name === 'order') {
        return index + 1;
      }
      if (name.includes('count') || name.includes('quantity') || name.includes('num')) {
        return randInt(0, 1000, rng);
      }
      if (name.includes('age')) {
        return randInt(18, 65, rng);
      }
      return randInt(1, 9999, rng);
    }
    case 'float':
    case 'decimal': {
      if (name.includes('price') || name.includes('amount') || name.includes('cost') || name.includes('fee')) {
        return randFloat(10, 99999, 2, rng);
      }
      if (name.includes('rate') || name.includes('ratio') || name.includes('percent')) {
        return randFloat(0, 100, 2, rng);
      }
      return randFloat(0, 1000, 2, rng);
    }
    case 'boolean': {
      return rng() > 0.5;
    }
    case 'datetime': {
      const now = Date.now();
      const offset = randInt(-30 * 24 * 3600 * 1000, 0, rng);
      return new Date(now + offset).toISOString().replace('T', ' ').slice(0, 19);
    }
    case 'date': {
      const now = Date.now();
      const offset = randInt(-90 * 24 * 3600 * 1000, 0, rng);
      return new Date(now + offset).toISOString().slice(0, 10);
    }
    case 'json': {
      return { key1: `value_${index}`, key2: randInt(1, 100, rng) };
    }
    case 'enum': {
      // Fallback if no enum_ref (shouldn't happen normally)
      return `option_${randInt(1, 5, rng)}`;
    }
    case 'file': {
      if (name.includes('avatar') || name.includes('image') || name.includes('cover') || name.includes('photo')) {
        return pick(IMAGE_URLS, rng);
      }
      return pick(FILE_URLS, rng);
    }
    default: {
      return `mock_${index}`;
    }
  }
}

/** Generate string value based on field name pattern */
function generateStringByName(
  name: string,
  index: number,
  rng: () => number,
): string {
  // Name patterns
  if (name === 'name' || name.endsWith('_name') || name === 'username') {
    return `${pick(CHINESE_SURNAMES, rng)}${pick(CHINESE_GIVEN_NAMES, rng)}`;
  }
  if (name === 'title' || name.endsWith('_title')) {
    return `${pick(TITLES, rng)} #${index + 1}`;
  }
  if (name.includes('email') || name === 'mail') {
    return `user${index + 1}@${pick(EMAIL_DOMAINS, rng)}`;
  }
  if (name.includes('phone') || name.includes('mobile') || name === 'tel') {
    return `1${randInt(30, 99, rng)}${String(randInt(10000000, 99999999, rng))}`;
  }
  if (name.includes('company') || name.includes('org')) {
    return `${pick(CITY_NAMES, rng)}${pick(COMPANY_NAMES, rng)}${pick(COMPANY_SUFFIXES, rng)}`;
  }
  if (name.includes('city') || name.includes('address') || name.includes('location')) {
    // DEV-ONLY: Chinese address format for preview
    return `${pick(CITY_NAMES, rng)}市某某区某某路${randInt(1, 999, rng)}号`;
  }
  if (name.includes('department') || name === 'dept') {
    return pick(DEPARTMENT_NAMES, rng);
  }
  if (name.includes('product')) {
    return pick(PRODUCT_NAMES, rng);
  }
  if (name.includes('code') || name.includes('no') || name.includes('sn') || name.includes('number')) {
    const prefix = name.replace(/_?(code|no|sn|number)$/i, '').toUpperCase() || 'NO';
    return `${prefix.slice(0, 4)}-${String(Date.now()).slice(-6)}-${String(index + 1).padStart(4, '0')}`;
  }
  if (name.includes('url') || name.includes('link') || name.includes('website')) {
    return `https://example.com/${name}/${index + 1}`;
  }
  if (name.includes('ip')) {
    return `${randInt(10, 192, rng)}.${randInt(0, 255, rng)}.${randInt(0, 255, rng)}.${randInt(1, 254, rng)}`;
  }
  if (name.includes('color')) {
    const hex = Math.floor(rng() * 0xffffff).toString(16).padStart(6, '0');
    return `#${hex}`;
  }
  if (name.includes('desc') || name.includes('remark') || name.includes('note') || name.includes('comment')) {
    return pick(LOREM_SENTENCES, rng);
  }
  if (name.includes('tag') || name.includes('label')) {
    // DEV-ONLY: Chinese tag labels for preview
    const tags = ['重要', '紧急', '待处理', '已完成', '进行中', '低优先级'];
    return pick(tags, rng);
  }
  if (name.includes('avatar') || name.includes('image') || name.includes('cover')) {
    return pick(IMAGE_URLS, rng);
  }

  // Generic fallback
  return `${name}_${index + 1}`;
}

// ============================================================
// 关联展示值生成
// ============================================================

function generateRelationDisplayValue(
  relation: RelationConfig,
  rng: () => number,
): Record<string, unknown> {
  return {
    id: randInt(1, 50, rng),
    [relation.label_field || 'name']: `${pick(CHINESE_SURNAMES, rng)}${pick(CHINESE_GIVEN_NAMES, rng)}`,
  };
}

// ============================================================
// Mock 数据行生成
// ============================================================

export interface MockDataRow {
  id: number;
  [key: string]: unknown;
}

/**
 * Generate mock data rows from CrudConfig.
 *
 * @param config - The CRUD configuration
 * @param count - Number of rows to generate (default 50)
 * @param seed - Random seed for deterministic output
 */
export function generateMockData(
  config: CrudConfig,
  count = 50,
  seed = 42,
): MockDataRow[] {
  const rng = createRng(seed);
  const rows: MockDataRow[] = [];

  for (let i = 0; i < count; i++) {
    const row: MockDataRow = { id: i + 1 };

    // System fields
    row.created_at = (() => {
      const now = Date.now();
      const offset = randInt(-30 * 24 * 3600 * 1000, 0, rng);
      return new Date(now + offset).toISOString().replace('T', ' ').slice(0, 19);
    })();
    row.updated_at = row.created_at;

    if (config.soft_delete) {
      row.is_deleted = false;
    }

    if (config.has_status_toggle) {
      row.status = rng() > 0.2;
    }

    if (config.drag_sort) {
      row.sort_order = i + 1;
    }

    // Field values
    for (const field of config.fields) {
      row[field.name] = generateFieldValue(
        field,
        i,
        config.enums,
        config.relations,
        rng,
      );
    }

    // Relation display values
    for (const rel of config.relations) {
      if (rel.type === 'belongs_to') {
        row[`${rel.name}_display`] = generateRelationDisplayValue(rel, rng);
      }
    }

    rows.push(row);
  }

  return rows;
}

// ============================================================
// Composable
// ============================================================

export function useMockData(configGetter: () => CrudConfig) {
  const mockData = computed(() => {
    const cfg = configGetter();
    if (!cfg.fields || cfg.fields.length === 0) return [];
    return generateMockData(cfg, 50);
  });

  const singleMockRow = computed(() => {
    const data = mockData.value;
    return data.length > 0 ? data[0]! : { id: 1 };
  });

  return {
    mockData,
    singleMockRow,
    generateMockData,
  };
}
