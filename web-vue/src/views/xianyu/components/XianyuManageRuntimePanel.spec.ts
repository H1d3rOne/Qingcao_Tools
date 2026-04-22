import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  getXianyuDeliveryRuntimeStatus: vi.fn(),
  listXianyuDeliveryExecutions: vi.fn(),
  messageError: vi.fn(),
}))

vi.mock('@/api/modules/xianyu', () => ({
  getXianyuDeliveryRuntimeStatus: mocks.getXianyuDeliveryRuntimeStatus,
  listXianyuDeliveryExecutions: mocks.listXianyuDeliveryExecutions,
}))

vi.mock('element-plus', () => ({
  ElMessage: {
    error: mocks.messageError,
  },
}))

import XianyuManageRuntimePanel from './XianyuManageRuntimePanel.vue'

describe('XianyuManageRuntimePanel', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.clearAllMocks()
    mocks.getXianyuDeliveryRuntimeStatus.mockResolvedValue({
      data: {
        running: true,
        last_event_at: 1710000000,
        last_success_at: 1710000100,
        last_failure_at: 1710000200,
        last_error: '最近一次失败：订单缺字段',
        enabled_rule_count: 2,
        recent_success_count: 7,
        recent_failure_count: 1,
      },
    })
    mocks.listXianyuDeliveryExecutions.mockResolvedValue({
      data: [
        {
          id: 'record-1',
          rule_id: 'rule-1',
          rule_name: '自动卡密',
          order_id: 'order-1',
          item_id: 'item-1',
          buyer_id: 'buyer-1',
          status: 'success',
          message: 'delivered',
          created_at: 1710000300,
        },
      ],
    })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders runtime summary shell and keeps recent execution list readable', async () => {
    const wrapper = mount(XianyuManageRuntimePanel, {
      global: {
        stubs: {
          'el-button': {
            template: '<button @click="$emit(\'click\')"><slot /></button>',
          },
          'el-icon': {
            template: '<span class="icon"><slot /></span>',
          },
          'el-empty': {
            template: '<div>empty</div>',
          },
        },
      },
    })

    await flushPromises()

    expect(mocks.getXianyuDeliveryRuntimeStatus).toHaveBeenCalledTimes(1)
    expect(mocks.listXianyuDeliveryExecutions).toHaveBeenCalledWith({ limit: 20 })
    expect(wrapper.find('.mg-runtime-summary').exists()).toBe(true)
    expect(wrapper.findAll('.mg-time-info__item')).toHaveLength(3)
    expect(wrapper.find('.mg-exec__helper').text()).toContain('最近 20 条')
    expect(wrapper.text()).toContain('最近一次失败：订单缺字段')
    expect(wrapper.text()).toContain('自动卡密')

    await vi.advanceTimersByTimeAsync(15000)
    await flushPromises()

    expect(mocks.getXianyuDeliveryRuntimeStatus).toHaveBeenCalledTimes(2)

    wrapper.unmount()
    await vi.advanceTimersByTimeAsync(30000)
    expect(mocks.getXianyuDeliveryRuntimeStatus).toHaveBeenCalledTimes(2)
  })

  it('renders runtime focus summary and execution reason text', async () => {
    const wrapper = mount(XianyuManageRuntimePanel, {
      global: {
        stubs: {
          'el-button': {
            template: '<button @click="$emit(\'click\')"><slot /></button>',
          },
          'el-icon': true,
          'el-empty': true,
        },
      },
    })

    await flushPromises()

    expect(wrapper.find('.mg-runtime-summary__focus').exists()).toBe(true)
    expect(wrapper.find('.mg-exec__reason').text()).toContain('delivered')
  })
})
