import { shallowMount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import XianyuManagePanel from './XianyuManagePanel.vue'

describe('XianyuManagePanel', () => {
  it('renders unified overview shell and keeps 商品管理 active by default', () => {
    const wrapper = shallowMount(XianyuManagePanel, {
      props: {
        currentUser: { display_name: '会飞的猪' },
      },
      global: {
        stubs: {
          XianyuManageItemsPanel: true,
          XianyuManageDeliveryPanel: true,
          XianyuManageRuntimePanel: true,
          'el-button': true,
          'el-icon': true,
        },
      },
    })

    expect(wrapper.find('.mg-overview').exists()).toBe(true)
    expect(wrapper.findAll('.mg-overview__stat')).toHaveLength(4)
    expect(wrapper.findAll('.mg-tab')).toHaveLength(3)
    expect(wrapper.find('.mg-tab--active .mg-tab__text').text()).toContain('商品管理')
    expect(wrapper.text()).toContain('会飞的猪')
  })
})
