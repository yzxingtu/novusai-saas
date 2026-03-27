<script lang="ts" setup>
import { ref, watch } from 'vue';

import { cn } from '@vben-core/shared/utils';

interface Props {
  class?: string;
  /**
   * @zh_CN 最小加载时间
   * @en_US Minimum loading time
   */
  minLoadingTime?: number;
  /**
   * @zh_CN loading状态开启
   */
  spinning?: boolean;
}

defineOptions({
  name: 'VbenSpinner',
});

const props = withDefaults(defineProps<Props>(), {
  minLoadingTime: 50,
});
// const startTime = ref(0);
const showSpinner = ref(false);
const renderSpinner = ref(false);
const timer = ref<ReturnType<typeof setTimeout>>();

watch(
  () => props.spinning,
  (show) => {
    if (!show) {
      showSpinner.value = false;
      clearTimeout(timer.value);
      return;
    }

    // startTime.value = performance.now();
    timer.value = setTimeout(() => {
      // const loadingTime = performance.now() - startTime.value;

      showSpinner.value = true;
      if (showSpinner.value) {
        renderSpinner.value = true;
      }
    }, props.minLoadingTime);
  },
  {
    immediate: true,
  },
);

function onTransitionEnd() {
  if (!showSpinner.value) {
    renderSpinner.value = false;
  }
}
</script>

<template>
  <div
    :class="
      cn(
        'flex-center absolute left-0 top-0 z-100 size-full bg-white transition-all duration-500 dark:bg-[#0a0e1a]',
        {
          'invisible opacity-0': !showSpinner,
        },
        props.class,
      )
    "
    @transitionend="onTransitionEnd"
  >
    <div
      v-if="renderSpinner"
      :class="{ paused: !renderSpinner }"
      class="loading-icon"
    >
      <svg viewBox="0 0 100 50" width="120" height="60">
        <defs>
          <linearGradient
            id="spinner-grad"
            gradientUnits="userSpaceOnUse"
            x1="12"
            y1="25"
            x2="88"
            y2="25"
          >
            <stop offset="0%" stop-color="#FF6B35" />
            <stop offset="33%" stop-color="#FF2D87" />
            <stop offset="66%" stop-color="#9333EA" />
            <stop offset="100%" stop-color="#38BDF8" />
          </linearGradient>
        </defs>
        <path
          class="inf-strand"
          d="M 27 40 C 45 40 55 10 73 10 A 15 15 0 1 1 73 40 C 55 40 45 10 27 10 A 15 15 0 1 0 27 40 Z"
        />
        <path class="inf-eraser" d="M 35 12 C 46 17 54 33 65 38" />
        <path class="inf-strand" d="M 27 10 C 45 10 55 40 73 40" />
      </svg>
    </div>
  </div>
</template>

<style scoped>
.paused {
  animation-play-state: paused !important;
}

.loading-icon {
  width: 120px;
  height: 60px;
  animation: fade-pulse 2.5s ease-in-out infinite;
}

.inf-strand {
  fill: none;
  stroke: url('#spinner-grad');
  stroke-width: 8;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.inf-eraser {
  fill: none;
  stroke: #fff;
  stroke-width: 12;
  stroke-linecap: butt;
}

:deep(.dark) .inf-eraser,
.dark .inf-eraser {
  stroke: #0a0e1a;
}

@keyframes fade-pulse {
  0%,
  100% {
    opacity: 1;
  }

  50% {
    opacity: 0.4;
  }
}
</style>
