<script lang="ts" setup>
/**
 * 在线协作用户头像栏
 *
 * 显示当前文档的在线协作用户头像（最多 8 个），超出显示 +N。
 * 通过 CollabClient 的 onUsersChange 回调更新。
 */
import { computed } from 'vue';
import { Tooltip } from 'ant-design-vue';

const props = defineProps<{
  users: Array<{
    userId: number | null;
    username: string | null;
    color: string;
  }>;
}>();

const MAX_VISIBLE = 8;

const visibleUsers = computed(() => props.users.slice(0, MAX_VISIBLE));
const overflowCount = computed(() => Math.max(0, props.users.length - MAX_VISIBLE));

function getInitial(username: string | null): string {
  if (!username) return '?';
  return username.charAt(0).toUpperCase();
}
</script>

<template>
  <div class="flex items-center">
    <Tooltip
      v-for="(user, idx) in visibleUsers"
      :key="user.userId ?? idx"
      :title="user.username || 'Anonymous'"
    >
      <div
        class="flex size-7 items-center justify-center rounded-full border-2 border-background text-[11px] font-semibold text-white"
        :style="{ backgroundColor: user.color, marginLeft: idx > 0 ? '-6px' : '0' }"
      >
        {{ getInitial(user.username) }}
      </div>
    </Tooltip>
    <div
      v-if="overflowCount > 0"
      class="flex size-7 items-center justify-center rounded-full border-2 border-background text-[11px] font-semibold text-white"
      :style="{ backgroundColor: '#6B7280', marginLeft: '-6px' }"
    >
      +{{ overflowCount }}
    </div>
  </div>
</template>
