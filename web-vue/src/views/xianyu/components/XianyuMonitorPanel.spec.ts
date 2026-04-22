import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  listXianyuMonitorTasks: vi.fn(),
  getXianyuMonitorHits: vi.fn(),
  createXianyuMonitorTask: vi.fn(),
  updateXianyuMonitorTask: vi.fn(),
  toggleXianyuMonitorTask: vi.fn(),
  runXianyuMonitorTask: vi.fn(),
  deleteXianyuMonitorTask: vi.fn(),
  messageSuccess: vi.fn(),
  messageError: vi.fn(),
  confirmMock: vi.fn(),
}))

vi.mock('@/api/modules/xianyu', () => ({
  listXianyuMonitorTasks: mocks.listXianyuMonitorTasks,
  getXianyuMonitorHits: mocks.getXianyuMonitorHits,
  createXianyuMonitorTask: mocks.createXianyuMonitorTask,
  updateXianyuMonitorTask: mocks.updateXianyuMonitorTask,
  toggleXianyuMonitorTask: mocks.toggleXianyuMonitorTask,
  runXianyuMonitorTask: mocks.runXianyuMonitorTask,
  deleteXianyuMonitorTask: mocks.deleteXianyuMonitorTask,
}))

vi.mock('element-plus', () => ({
  ElMessage: { success: mocks.messageSuccess, error: mocks.messageError },
  ElMessageBox: { confirm: mocks.confirmMock },
}))

import XianyuMonitorPanel from './XianyuMonitorPanel.vue'

function buildWrapper() {
  return mount(XianyuMonitorPanel, {
    props: {
      currentUser: { display_name: '会飞的猪' },
    },
    global: {
      stubs: {
        'el-button': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
        'el-icon': { template: '<span class="icon"><slot /></span>' },
        'el-empty': { template: '<div class="empty"><slot />empty</div>' },
        'el-dialog': { props: ['modelValue'], template: '<div v-if="modelValue"><slot /><slot name="footer" /></div>' },
        'el-form': { template: '<form><slot /></form>' },
        'el-form-item': { template: '<label><slot /></label>' },
        'el-input': { props: ['modelValue'], template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />' },
        'el-input-number': { props: ['modelValue'], template: '<input type="number" :value="modelValue" @input="$emit(\'update:modelValue\', Number($event.target.value))" />' },
        'el-select': { props: ['modelValue'], template: '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>' },
        'el-option': { props: ['value', 'label'], template: '<option :value="value">{{ label }}</option>' },
        'el-switch': { props: ['modelValue'], template: '<button class="switch" @click="$emit(\'update:modelValue\', !modelValue)"><slot /></button>' },
      },
    },
  })
}

describe('XianyuMonitorPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.listXianyuMonitorTasks.mockResolvedValue({
      data: [
        {
          id: 'task-1',
          name: '4060 监控',
          keyword: '4060',
          page: 1,
          page_size: 20,
          sort_field: '',
          sort_value: '',
          prop_values: {},
          min_price: null,
          max_price: null,
          interval_seconds: 180,
          enabled: true,
          created_at: 1710000000,
          updated_at: 1710000000,
          last_run_at: 1710000000,
          last_status: 'ok',
          last_error: '',
          seen_item_ids: ['1001'],
          latest_hits: [
            {
              item_id: '1001',
              title: '4060 显卡',
              price: '1999',
              image: 'https://example.com/1.jpg',
              detail_url: 'https://example.com/item/1001',
              discovered_at: 1710000000,
            },
          ],
          max_hits: null,
          published_within_hours: null,
          webhook_url: '',
          contact_seller_enabled: false,
        },
        {
          id: 'task-2',
          name: '3070 监控',
          keyword: '3070',
          page: 1,
          page_size: 20,
          sort_field: '',
          sort_value: '',
          prop_values: {},
          min_price: null,
          max_price: null,
          interval_seconds: 180,
          enabled: false,
          created_at: 1710000000,
          updated_at: 1710000000,
          last_run_at: 1710000000,
          last_status: 'idle',
          last_error: '',
          seen_item_ids: [],
          latest_hits: [],
          max_hits: null,
          published_within_hours: null,
          webhook_url: '',
          contact_seller_enabled: false,
        },
      ],
    })
    mocks.getXianyuMonitorHits.mockResolvedValue({
      data: [
        {
          item_id: '1001',
          title: '4060 显卡',
          price: '1999',
          image: 'https://example.com/1.jpg',
          detail_url: 'https://example.com/item/1001',
          discovered_at: 1710000000,
        },
      ],
    })
  })

  it('collapses hit preview by default and toggles preview list', async () => {
    const wrapper = buildWrapper()
    await flushPromises()

    expect(wrapper.text()).toContain('最近命中')
    expect(wrapper.text()).toContain('展开预览')
    expect(wrapper.find('.mp-hit-grid').exists()).toBe(false)
    expect(wrapper.find('.mp-hits__toggle-icon').exists()).toBe(true)

    const toggleButton = wrapper.get('.mp-hits__toggle')
    await toggleButton!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('收起预览')
    expect(wrapper.find('.mp-hits__toggle-icon').exists()).toBe(true)
    expect(wrapper.find('.mp-hit-grid').exists()).toBe(true)
    expect(wrapper.text()).toContain('4060 显卡')

    await wrapper.get('.mp-hits__toggle').trigger('click')
    await flushPromises()

    expect(wrapper.find('.mp-hit-grid').exists()).toBe(false)
  })

  it('resets preview to collapsed after switching tasks and highlights active task title', async () => {
    const wrapper = buildWrapper()
    await flushPromises()

    await wrapper.get('.mp-hits__toggle').trigger('click')
    await flushPromises()
    expect(wrapper.find('.mp-hit-grid').exists()).toBe(true)

    let tasks = wrapper.findAll('.mp-task')
    expect(tasks[0].classes()).toContain('mp-task--active')
    expect(tasks[0].find('.mp-task__name').classes()).toContain('mp-task__name--active')

    await tasks[1].trigger('click')
    await flushPromises()

    tasks = wrapper.findAll('.mp-task')
    expect(wrapper.find('.mp-hit-grid').exists()).toBe(false)
    expect(wrapper.text()).toContain('展开预览')
    expect(tasks[1].classes()).toContain('mp-task--active')
    expect(tasks[1].find('.mp-task__name').classes()).toContain('mp-task__name--active')
  })
})
