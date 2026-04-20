<script setup lang="ts">
import { computed, reactive, watch } from 'vue'

interface ChatAiDialogModel {
  enabled: boolean
  base_url: string
  api_key: string
  model: string
  system_prompt: string
  temperature: number
  api_key_masked?: string
  api_key_configured?: boolean
}

const props = defineProps<{
  visible: boolean
  saving: boolean
  testing: boolean
  modelValue: ChatAiDialogModel
}>()

const emit = defineEmits<{
  'update:visible': [boolean]
  save: [ChatAiDialogModel]
  test: [ChatAiDialogModel]
}>()

const form = reactive<ChatAiDialogModel>({ ...props.modelValue })

watch(
  () => props.modelValue,
  (value) => {
    Object.assign(form, value)
  },
  { deep: true }
)

const title = computed(() => 'AI 配置')
</script>

<template>
  <el-dialog
    :model-value="visible"
    :title="title"
    width="680px"
    @close="emit('update:visible', false)"
  >
    <el-form label-width="110px">
      <el-form-item label="Base URL">
        <el-input v-model="form.base_url" />
      </el-form-item>
      <el-form-item label="API Key">
        <el-input
          v-model="form.api_key"
          show-password
          placeholder="留空则保留当前 Key"
        />
      </el-form-item>
      <el-form-item label="Model">
        <el-input v-model="form.model" />
      </el-form-item>
      <el-form-item label="Temperature">
        <el-input-number
          v-model="form.temperature"
          :min="0"
          :max="2"
          :step="0.1"
        />
      </el-form-item>
      <el-form-item label="Prompt">
        <el-input
          v-model="form.system_prompt"
          type="textarea"
          :rows="6"
        />
      </el-form-item>
      <el-alert
        v-if="form.api_key_configured"
        :title="`已配置 Key：${form.api_key_masked || ''}`"
        type="success"
        :closable="false"
      />
    </el-form>

    <template #footer>
      <el-button @click="emit('update:visible', false)">
        取消
      </el-button>
      <el-button
        :loading="testing"
        @click="emit('test', { ...form })"
      >
        测试回复
      </el-button>
      <el-button
        type="primary"
        :loading="saving"
        @click="emit('save', { ...form })"
      >
        保存
      </el-button>
    </template>
  </el-dialog>
</template>
