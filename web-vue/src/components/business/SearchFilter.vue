<script setup lang="ts">
import { ref, watch } from 'vue'

interface FilterOption {
  label: string
  value: number
}

interface Props {
  sortOptions?: FilterOption[]
  durationOptions?: FilterOption[]
  timeOptions?: FilterOption[]
}

const props = withDefaults(defineProps<Props>(), {
  sortOptions: () => [
    { label: '综合排序', value: 0 },
    { label: '最多点赞', value: 1 },
    { label: '最新发布', value: 2 }
  ],
  durationOptions: () => [
    { label: '全部时长', value: 0 },
    { label: '0-1分钟', value: 1 },
    { label: '1-5分钟', value: 2 },
    { label: '5分钟以上', value: 3 }
  ],
  timeOptions: () => [
    { label: '全部时间', value: 0 },
    { label: '一天内', value: 1 },
    { label: '一周内', value: 2 },
    { label: '半年内', value: 3 }
  ]
})

const emit = defineEmits<{
  change: [filters: { sort_type: number; filter_duration: number; publish_time: number }]
}>()

const sortType = ref(0)
const filterDuration = ref(0)
const publishTime = ref(0)

watch([sortType, filterDuration, publishTime], () => {
  emit('change', {
    sort_type: sortType.value,
    filter_duration: filterDuration.value,
    publish_time: publishTime.value
  })
})
</script>

<template>
  <div class="search-filter flex flex-wrap items-center gap-4 p-4 rounded-xl bg-dark-card">
    <!-- 排序 -->
    <div class="flex items-center gap-2">
      <span class="text-gray-400 text-sm">排序：</span>
      <el-radio-group
        v-model="sortType"
        size="small"
      >
        <el-radio-button
          v-for="option in sortOptions"
          :key="option.value"
          :value="option.value"
        >
          {{ option.label }}
        </el-radio-button>
      </el-radio-group>
    </div>

    <!-- 时长 -->
    <div class="flex items-center gap-2">
      <span class="text-gray-400 text-sm">时长：</span>
      <el-radio-group
        v-model="filterDuration"
        size="small"
      >
        <el-radio-button
          v-for="option in durationOptions"
          :key="option.value"
          :value="option.value"
        >
          {{ option.label }}
        </el-radio-button>
      </el-radio-group>
    </div>

    <!-- 发布时间 -->
    <div class="flex items-center gap-2">
      <span class="text-gray-400 text-sm">时间：</span>
      <el-radio-group
        v-model="publishTime"
        size="small"
      >
        <el-radio-button
          v-for="option in timeOptions"
          :key="option.value"
          :value="option.value"
        >
          {{ option.label }}
        </el-radio-button>
      </el-radio-group>
    </div>
  </div>
</template>
