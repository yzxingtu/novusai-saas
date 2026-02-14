<script setup lang="ts">
import {
  Button,
  Collapse,
  Empty,
  Input,
  Popconfirm,
} from 'ant-design-vue';

import { $t } from '#/locales';

import type { CrudConfig, EnumDefinition, EnumOption } from '../types';

const props = defineProps<{
  entity: CrudConfig;
}>();

const emit = defineEmits<{
  touched: [path: string];
}>();

const T = 'admin.dev.crudGenerator.enumEditor';

function addEnum() {
  const enumDef: EnumDefinition = {
    name: '',
    description: '',
    values: [],
    transitions: null,
  };
  props.entity.enums.push(enumDef);
  emit('touched', 'enums');
}

function removeEnum(index: number) {
  props.entity.enums.splice(index, 1);
  emit('touched', 'enums');
}

function addEnumValue(enumDef: EnumDefinition) {
  const val: EnumOption = {
    value: '',
    label_zh: '',
    label_en: '',
    color: null,
    icon: null,
  };
  enumDef.values.push(val);
  emit('touched', 'enums');
}

function removeEnumValue(enumDef: EnumDefinition, index: number) {
  enumDef.values.splice(index, 1);
  emit('touched', 'enums');
}

function onEnumChange() {
  emit('touched', 'enums');
}
</script>

<template>
  <div>
    <div class="mb-3 flex items-center justify-between">
      <span class="text-sm font-medium">
        {{ $t(`${T}.title`) }} ({{ entity.enums.length }})
      </span>
      <Button size="small" type="primary" @click="addEnum">
        <template #icon>
          <span class="icon-[lucide--plus] size-3.5" />
        </template>
        {{ $t(`${T}.addEnum`) }}
      </Button>
    </div>

    <div v-if="entity.enums.length > 0" class="space-y-3">
      <Collapse>
        <Collapse.Panel
          v-for="(enumDef, idx) in entity.enums"
          :key="idx"
          :header="enumDef.name || `Enum #${idx + 1}`"
        >
          <template #extra>
            <Popconfirm
              :title="$t('common.confirmDelete')"
              @confirm.stop="removeEnum(idx)"
            >
              <Button danger size="small" type="text" @click.stop>
                <template #icon>
                  <span class="icon-[lucide--trash-2] size-3.5" />
                </template>
              </Button>
            </Popconfirm>
          </template>

          <div class="space-y-3">
            <!-- Enum name & description -->
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="mb-1 block text-xs text-muted-foreground">{{ $t(`${T}.name`) }}</label>
                <Input
                  v-model:value="enumDef.name"
                  size="small"
                  @change="onEnumChange"
                />
              </div>
              <div>
                <label class="mb-1 block text-xs text-muted-foreground">{{ $t(`${T}.description`) }}</label>
                <Input
                  v-model:value="enumDef.description"
                  size="small"
                  @change="onEnumChange"
                />
              </div>
            </div>

            <!-- Enum values -->
            <div>
              <div class="mb-2 flex items-center justify-between">
                <label class="text-xs font-medium text-muted-foreground">{{ $t(`${T}.values`) }}</label>
                <Button size="small" type="link" @click="addEnumValue(enumDef)">
                  <template #icon>
                    <span class="icon-[lucide--plus] size-3" />
                  </template>
                  {{ $t(`${T}.addValue`) }}
                </Button>
              </div>

              <div v-if="enumDef.values.length > 0" class="space-y-2">
                <div
                  v-for="(val, vIdx) in enumDef.values"
                  :key="vIdx"
                  class="flex items-center gap-2"
                >
                  <Input
                    v-model:value="val.value"
                    :placeholder="$t(`${T}.value`)"
                    class="w-28"
                    size="small"
                    @change="onEnumChange"
                  />
                  <Input
                    v-model:value="val.label_zh"
                    :placeholder="$t(`${T}.labelZh`)"
                    class="w-24"
                    size="small"
                    @change="onEnumChange"
                  />
                  <Input
                    v-model:value="val.label_en"
                    :placeholder="$t(`${T}.labelEn`)"
                    class="w-24"
                    size="small"
                    @change="onEnumChange"
                  />
                  <Input
                    :value="val.color ?? ''"
                    :placeholder="$t(`${T}.color`)"
                    class="w-20"
                    size="small"
                    @update:value="(v: string) => { val.color = v || null; onEnumChange(); }"
                  />
                  <Popconfirm
                    :title="$t('common.confirmDelete')"
                    @confirm="removeEnumValue(enumDef, vIdx)"
                  >
                    <Button danger size="small" type="text">
                      <template #icon>
                        <span class="icon-[lucide--x] size-3" />
                      </template>
                    </Button>
                  </Popconfirm>
                </div>
              </div>
            </div>
          </div>
        </Collapse.Panel>
      </Collapse>
    </div>

    <Empty
      v-else
      :description="$t(`${T}.title`)"
      :image="Empty.PRESENTED_IMAGE_SIMPLE"
    />
  </div>
</template>
