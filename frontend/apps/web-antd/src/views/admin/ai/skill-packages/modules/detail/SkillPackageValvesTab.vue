<script lang="ts" setup>
import {
  Alert,
  Button,
  Empty,
  Input,
  InputNumber,
  Switch,
  Tag,
} from 'ant-design-vue';

import { $t } from '#/locales';

import { useSkillPackageDetailContext } from './detail-context';

const {
  canUpdateSkillPackage,
  configuredValveCount,
  getBooleanValveValue,
  getJsonValvePlaceholder,
  getJsonValveValue,
  getNumberValveValue,
  getStringValveValue,
  getValveInputType,
  handleSaveValves,
  hasValves,
  isSecretKey,
  resetValvesToDefaults,
  sortedValveFields,
  updateBooleanValve,
  updateJsonValve,
  updateNumberValve,
  updateStringValve,
  valvesFieldCount,
  valvesSaving,
} = useSkillPackageDetailContext();
</script>

<template>
  <div class="flex flex-col gap-4 p-5 pt-3">
    <div class="flex items-start justify-between gap-4">
      <div>
        <div class="text-sm font-semibold text-foreground">
          {{ $t('admin.ai.skillPackage.valves.title') }}
        </div>
        <p class="mt-1 text-xs text-muted-foreground">
          {{ configuredValveCount }}/{{ valvesFieldCount }}
        </p>
      </div>

      <div class="flex items-center gap-2">
        <Button
          v-if="canUpdateSkillPackage"
          size="small"
          :disabled="!hasValves"
          @click="resetValvesToDefaults"
        >
          {{ $t('admin.ai.skillPackage.valves.resetDefaults') }}
        </Button>
        <Button
          v-if="canUpdateSkillPackage"
          size="small"
          type="primary"
          :loading="valvesSaving"
          :disabled="!hasValves"
          @click="handleSaveValves"
        >
          {{ $t('shared.common.save') }}
        </Button>
      </div>
    </div>

    <template v-if="hasValves">
      <Alert
        :message="$t('admin.ai.skillPackage.valves.description')"
        type="info"
        show-icon
      />

      <div class="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <div
          v-for="field in sortedValveFields"
          :key="field.key"
          class="rounded-xl border bg-accent/30 p-4"
        >
          <div class="mb-3 flex items-start justify-between gap-3">
            <div class="min-w-0">
              <div class="flex flex-wrap items-center gap-2">
                <code
                  class="rounded bg-background px-2 py-1 font-mono text-xs text-foreground"
                >
                  {{ field.key }}
                </code>
                <Tag
                  v-if="field.isRequired"
                  color="red"
                  class="!mr-0 !text-[11px]"
                >
                  {{ $t('admin.ai.skillPackage.valves.required') }}
                </Tag>
                <Tag
                  v-if="isSecretKey(field.key)"
                  color="gold"
                  class="!mr-0 !text-[11px]"
                >
                  {{ $t('admin.ai.skillPackage.valves.sensitiveHint') }}
                </Tag>
              </div>

              <p
                v-if="field.description"
                class="mt-2 text-xs leading-relaxed text-muted-foreground"
              >
                {{ field.description }}
              </p>
            </div>

            <Tag class="!mr-0 !text-[11px]">
              {{ field.type || 'string' }}
            </Tag>
          </div>

          <Switch
            v-if="getValveInputType(field.type) === 'switch'"
            :checked="getBooleanValveValue(field.key)"
            @update:checked="
              (value) => updateBooleanValve(field.key, Boolean(value))
            "
          />

          <InputNumber
            v-else-if="getValveInputType(field.type) === 'number'"
            :value="getNumberValveValue(field.key)"
            class="w-full"
            :placeholder="
              field.default !== undefined ? String(field.default) : undefined
            "
            @update:value="
              (value) =>
                updateNumberValve(
                  field.key,
                  typeof value === 'number' ? value : null,
                )
            "
          />

          <Input.TextArea
            v-else-if="getValveInputType(field.type) === 'json'"
            :value="getJsonValveValue(field.key)"
            :rows="5"
            class="font-mono text-xs"
            :placeholder="getJsonValvePlaceholder(field)"
            @update:value="(value) => updateJsonValve(field.key, value)"
          />

          <div
            v-else-if="isSecretKey(field.key)"
            class="flex items-center gap-2"
          >
            <Input.Password
              :value="getStringValveValue(field.key)"
              class="flex-1"
              :placeholder="
                field.default !== undefined ? String(field.default) : undefined
              "
              @update:value="(value) => updateStringValve(field.key, value)"
            />
            <Tag
              v-if="getStringValveValue(field.key) === '******'"
              color="green"
              class="!mr-0 cursor-pointer !text-[11px]"
              @click="updateStringValve(field.key, '')"
            >
              {{ $t('admin.ai.skillPackage.valves.secretConfigured') }}
            </Tag>
          </div>

          <Input
            v-else
            :value="getStringValveValue(field.key)"
            :placeholder="
              field.default !== undefined ? String(field.default) : undefined
            "
            @update:value="(value) => updateStringValve(field.key, value)"
          />
        </div>
      </div>
    </template>

    <div v-else class="py-12">
      <Empty :description="$t('admin.ai.skillPackage.valves.noSchema')" />
    </div>
  </div>
</template>
