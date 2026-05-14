<script setup lang="ts">
</script>

<template>
  <div class="error-page flex flex-col items-center justify-center min-h-[60vh]">
    <el-icon
      class="text-primary mb-6"
      :size="120"
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
          d="M464 336a48 48 0 1 0 96 0 48 48 0 1 0-96 0zm72 112h-48c-4.4 0-8 3.6-8 8v272c0 4.4 3.6 8 8 8h48c4.4 0 8-3.6 8-8V456c0-4.4-3.6-8-8-8z"
        />
      </svg>
    </el-icon>
    <h1 class="text-4xl font-bold text-white mb-4">
      404
    </h1>
    <p class="text-gray-400 mb-8">
      抱歉，您访问的页面不存在
    </p>
    <el-button
      type="primary"
      @click="$router.push('/')"
    >
      返回首页
    </el-button>
  </div>
</template>
