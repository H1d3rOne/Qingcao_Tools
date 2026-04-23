import { mount, shallowMount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

vi.mock('@/stores', () => ({
  useXianyuUserStore: () => ({
    logout: vi.fn().mockResolvedValue(undefined),
  }),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}))

vi.mock('@/api/modules/xianyu', () => ({
  createXianyuMonitorTask: vi.fn(),
  getXianyuItemDetail: vi.fn(),
  getXianyuUserProfile: vi.fn().mockResolvedValue({ data: null }),
  openXianyuChatSession: vi.fn(),
  searchXianyuItems: vi.fn(),
}))

import XianyuPage from './index.vue'

describe('Xianyu page tabs', () => {
  it('shows 管理 instead of 发布 in bottom tabs', () => {
    const wrapper = shallowMount(XianyuPage, {
      global: {
        stubs: {
          XianyuChatPanel: true,
          XianyuMonitorPanel: true,
          XianyuManagePanel: true,
          'el-button': true,
          'el-input': true,
          'el-select': true,
          'el-option': true,
          'el-empty': true,
          'el-pagination': true,
          'el-dialog': true,
          'el-icon': true,
        },
      },
    })

    const text = wrapper.text()
    expect(text).toContain('管理')
    expect(text).not.toContain('发布')
  })

  it('keeps active tab label text visible after clicking another tab', async () => {
    const wrapper = mount(XianyuPage, {
      global: {
        stubs: {
          XianyuChatPanel: true,
          XianyuMonitorPanel: true,
          XianyuManagePanel: true,
          'el-button': { template: '<button @click="$emit(\'click\')"><slot /></button>' },
          'el-input': true,
          'el-select': true,
          'el-option': true,
          'el-empty': true,
          'el-pagination': true,
          'el-dialog': true,
          'el-icon': { template: '<span class="icon"><slot /></span>' },
        },
      },
    })

    const manageTab = wrapper.findAll('.bottom-nav__item')[2]
    await manageTab.trigger('click')

    expect(manageTab.find('strong').text()).toBe('管理')
    expect(manageTab.find('.bottom-nav__label').classes()).toContain('is-active-label')
    expect(manageTab.find('.bottom-nav__hint').text()).toBe('商品与发货')
    expect(manageTab.find('.bottom-nav__hint').classes()).toContain('is-active-hint')
  })
})
