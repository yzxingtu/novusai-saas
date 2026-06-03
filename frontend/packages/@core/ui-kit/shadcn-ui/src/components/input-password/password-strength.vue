<script setup lang="ts">
import { computed } from 'vue';

const props = withDefaults(defineProps<{ password?: string }>(), {
  password: '',
});

const strengthList: string[] = [
  '',
  '#e74242',
  '#ED6F6F',
  '#EFBD47',
  '#55D18780',
  '#55D187',
];

const currentStrength = computed(() => {
  return checkPasswordStrength(props.password);
});

const currentColor = computed(() => {
  return strengthList[currentStrength.value];
});

/**
 * 校验密码强度（0–5）/ Score password strength 0–5
 */
function checkPasswordStrength(password: string) {
  let strength = 0;

  // 长度 / length
  if (password.length >= 8) strength++;

  // 小写 / lowercase
  if (/[a-z]/.test(password)) strength++;

  // 大写 / uppercase
  if (/[A-Z]/.test(password)) strength++;

  // 数字 / digits
  if (/\d/.test(password)) strength++;

  // 特殊字符 / special chars
  if (/[^\da-z]/i.test(password)) strength++;

  return strength;
}
</script>

<template>
  <div class="relative mt-2 flex items-center justify-between">
    <template v-for="index in 5" :key="index">
      <div
        class="relative mr-1 h-1.5 w-1/5 rounded-sm bg-heavy last:mr-0 dark:bg-input-background"
      >
        <span
          :style="{
            backgroundColor: currentColor,
            width: currentStrength >= index ? '100%' : '',
          }"
          class="absolute left-0 h-full w-0 rounded-sm transition-all duration-500"
        ></span>
      </div>
    </template>
  </div>
</template>
