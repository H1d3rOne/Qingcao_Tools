import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  listXianyuDeliveryRules: vi.fn(),
  createXianyuDeliveryRule: vi.fn(),
  updateXianyuDeliveryRule: vi.fn(),
  deleteXianyuDeliveryRule: vi.fn(),
  toggleXianyuDeliveryRule: vi.fn(),
  messageSuccess: vi.fn(),
  messageError: vi.fn(),
  messageWarning: vi.fn(),
  confirmMock: vi.fn(),
  writeText: vi.fn(),
}))

vi.mock('@/api/modules/xianyu', () => ({
  listXianyuDeliveryRules: mocks.listXianyuDeliveryRules,
  createXianyuDeliveryRule: mocks.createXianyuDeliveryRule,
  updateXianyuDeliveryRule: mocks.updateXianyuDeliveryRule,
  deleteXianyuDeliveryRule: mocks.deleteXianyuDeliveryRule,
  toggleXianyuDeliveryRule: mocks.toggleXianyuDeliveryRule,
}))

vi.mock('element-plus', () => ({
  ElMessage: {
    success: mocks.messageSuccess,
    error: mocks.messageError,
    warning: mocks.messageWarning,
  },
  ElMessageBox: {
    confirm: mocks.confirmMock,
  },
}))

import XianyuManageDeliveryPanel from './XianyuManageDeliveryPanel.vue'

function buildWrapper() {
  return mount(XianyuManageDeliveryPanel, {
    global: {
      stubs: {
        'el-button': {
          template: '<button @click="$emit(\'click\')"><slot /></button>',
        },
        'el-icon': {
          template: '<span class="icon"><slot /></span>',
        },
        'el-switch': {
          props: ['modelValue'],
          template: '<button class="switch" @click="$emit(\'update:modelValue\', !modelValue)">{{ modelValue }}</button>',
        },
        'el-dialog': {
          props: ['modelValue'],
          template: '<div v-if="modelValue" class="dialog"><slot /><slot name="footer" /></div>',
        },
        'el-form': {
          template: '<form><slot /></form>',
        },
        'el-form-item': {
          template: '<label><slot /></label>',
        },
        'el-input': {
          props: ['modelValue', 'placeholder'],
          template: '<input :placeholder="placeholder" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
        },
        'el-select': {
          props: ['modelValue'],
          template: '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>',
        },
        'el-option': {
          props: ['label', 'value'],
          template: '<option :value="value">{{ label }}</option>',
        },
        'el-empty': {
          template: '<div>empty</div>',
        },
      },
    },
  })
}

describe('XianyuManageDeliveryPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.listXianyuDeliveryRules.mockResolvedValue({ data: [] })
    mocks.createXianyuDeliveryRule.mockResolvedValue({ data: {} })
    mocks.updateXianyuDeliveryRule.mockResolvedValue({ data: {} })
    mocks.deleteXianyuDeliveryRule.mockResolvedValue({ data: { deleted: true } })
    mocks.toggleXianyuDeliveryRule.mockResolvedValue({ data: { enabled: true } })
    mocks.confirmMock.mockResolvedValue('confirm')
    mocks.writeText.mockResolvedValue(undefined)
    Object.defineProperty(globalThis.navigator, 'clipboard', {
      value: { writeText: mocks.writeText },
      configurable: true,
    })
  })

  it('creates rule payload with current form fields', async () => {
    const wrapper = buildWrapper()
    await flushPromises()

    await wrapper.get('button').trigger('click')
    await flushPromises()

    const inputs = wrapper.findAll('input')
    await inputs[0].setValue('测试规则')
    await wrapper.get('select').setValue('keyword')
    await inputs[1].setValue('关键词A')
    await inputs[2].setValue('卡密文本')

    const switches = wrapper.findAll('.switch')
    await switches[0].trigger('click')
    await switches[1].trigger('click')

    const saveButton = wrapper.findAll('button').find((node) => node.text().includes('保存规则'))
    await saveButton!.trigger('click')
    await flushPromises()

    expect(mocks.createXianyuDeliveryRule).toHaveBeenCalledWith({
      name: '测试规则',
      match_mode: 'keyword',
      match_value: '关键词A',
      delivery_text: '卡密文本',
      send_chat_text: false,
      send_dummy_ship: false,
    })
  })

  it('validates required fields before saving', async () => {
    const wrapper = buildWrapper()
    await flushPromises()

    await wrapper.get('button').trigger('click')
    await flushPromises()

    const saveButton = wrapper.findAll('button').find((node) => node.text().includes('保存规则'))
    await saveButton!.trigger('click')
    await flushPromises()

    expect(mocks.createXianyuDeliveryRule).not.toHaveBeenCalled()
    expect(mocks.messageWarning).toHaveBeenCalled()
  })

  it('confirms delete and copies delivery text', async () => {
    mocks.listXianyuDeliveryRules.mockResolvedValue({
      data: [
        {
          id: 'rule-1',
          name: '现货卡密',
          enabled: true,
          match_mode: 'item_id',
          match_value: '1001',
          delivery_text: '复制这段卡密',
          send_chat_text: true,
          send_dummy_ship: true,
          created_at: 1,
          updated_at: 1,
        },
      ],
    })

    const wrapper = buildWrapper()
    await flushPromises()

    const copyButton = wrapper.findAll('button').find((node) => node.text().includes('复制文本'))
    await copyButton!.trigger('click')
    await flushPromises()
    expect(mocks.writeText).toHaveBeenCalledWith('复制这段卡密')

    const deleteButton = wrapper.findAll('button').find((node) => node.text().includes('删除'))
    await deleteButton!.trigger('click')
    await flushPromises()

    expect(mocks.confirmMock).toHaveBeenCalled()
    expect(mocks.deleteXianyuDeliveryRule).toHaveBeenCalledWith('rule-1')
  })

  it('renders rule summary shell and action hierarchy for delivery rules', async () => {
    mocks.listXianyuDeliveryRules.mockResolvedValue({
      data: [
        {
          id: 'rule-1',
          name: '现货卡密',
          enabled: true,
          match_mode: 'item_id',
          match_value: '1001',
          delivery_text: '复制这段卡密',
          send_chat_text: true,
          send_dummy_ship: true,
          created_at: 1,
          updated_at: 1,
        },
      ],
    })

    const wrapper = buildWrapper()
    await flushPromises()

    expect(wrapper.find('.mg-rule__summary').exists()).toBe(true)
    expect(wrapper.find('.mg-rule__body-grid').exists()).toBe(true)
    expect(wrapper.findAll('.mg-rule__flag')).toHaveLength(2)
  })
})
