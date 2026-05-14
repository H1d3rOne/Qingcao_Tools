<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  size?: 'small' | 'medium' | 'large'
  text?: string
}

const props = withDefaults(defineProps<Props>(), {
  size: 'medium',
  text: '加载中...'
})

const sizeClass = computed(() => {
  switch (props.size) {
    case 'small':
      return 'text-2xl'
    case 'large':
      return 'text-6xl'
    default:
      return 'text-4xl'
  }
})
</script>

<template>
  <div class="loading flex flex-col items-center justify-center py-12">
    <el-icon
      class="animate-spin text-primary"
      :class="sizeClass"
    >
      <svg
        viewBox="0 0 1024 1024"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          fill="currentColor"
          d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64zm0 820c-205.4 0-372-166.6-372-372s166.6-372 372-372 372 166.6 372 372-166.6 372-372 372z"
        />
        <path
          fill="currentColor"
          d="M512 140c-205.4 0-372 166.6-372 372 0 84.7 28.6 162.9 76.5 224.5l50.4-50.4C233.9 636.7 212 577.5 212 512c0-165.7 134.3-300 300-300s300 134.3 300 300-134.3 300-300 300c-65.5 0-124.7-21.9-174.1-58.6l-50.4 50.4C349.1 851.4 427.3 880 512 880c205.4 0 372-166.6 372-372S717.4 140 512 140z"
        />
      </svg>
    </el-icon>
    <p
      v-if="text"
      class="mt-4 text-gray-400"
    >
      {{ text }}
    </p>
  </div>
</template>
