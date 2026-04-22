import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  listXianyuManageItems: vi.fn(),
  syncXianyuManageItemsPage: vi.fn(),
  syncXianyuManageItemsAll: vi.fn(),
  updateXianyuManageItem: vi.fn(),
  setXianyuManageItemMultiQuantityDelivery: vi.fn(),
  deleteXianyuManageItem: vi.fn(),
  messageSuccess: vi.fn(),
  messageError: vi.fn(),
  confirmMock: vi.fn(),
}))

vi.mock('@/api/modules/xianyu', () => ({
  listXianyuManageItems: mocks.listXianyuManageItems,
  syncXianyuManageItemsPage: mocks.syncXianyuManageItemsPage,
  syncXianyuManageItemsAll: mocks.syncXianyuManageItemsAll,
  updateXianyuManageItem: mocks.updateXianyuManageItem,
  setXianyuManageItemMultiQuantityDelivery: mocks.setXianyuManageItemMultiQuantityDelivery,
  deleteXianyuManageItem: mocks.deleteXianyuManageItem,
}))

vi.mock('element-plus', () => ({
  ElMessage: {
    success: mocks.messageSuccess,
    error: mocks.messageError,
  },
  ElMessageBox: {
    confirm: mocks.confirmMock,
  },
}))

import XianyuManageItemsPanel from './XianyuManageItemsPanel.vue'

function buildWrapper() {
  return mount(XianyuManageItemsPanel, {
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
          template: '<button class="switch" @click="$emit(\'change\', !modelValue)"><slot /></button>',
        },
        'el-dialog': {
          props: ['modelValue'],
          template: '<div v-if="modelValue" class="dialog"><slot /><slot name="footer" /></div>',
        },
        'el-input': {
          props: ['modelValue'],
          template: '<textarea :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)"></textarea>',
        },
        'el-empty': {
          template: '<div class="empty"><slot />empty</div>',
        },
        'el-pagination': {
          props: ['currentPage', 'pageSize', 'total'],
          template: '<button class="pager" @click="$emit(\'current-change\', 2)">pager {{ currentPage }}/{{ total }}</button>',
        },
      },
    },
  })
}

describe('XianyuManageItemsPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.listXianyuManageItems.mockResolvedValue({
      data: {
        items: [
          {
            item_id: '1001',
            item_title: '商品1',
            item_price: '10',
            item_image: 'https://example.com/item-1.jpg',
            item_status: 'onsale',
            item_detail: '详情1',
            multi_quantity_delivery: false,
            synced_at: 1,
            updated_at: 1,
          },
          {
            item_id: '1002',
            item_title: '商品2',
            item_price: '',
            item_image: '',
            item_status: 'onsale',
            item_detail: '',
            multi_quantity_delivery: true,
            synced_at: 2,
            updated_at: 2,
          },
        ],
        total: 25,
        page: 1,
        page_size: 20,
        has_more: true,
      },
    })
    mocks.confirmMock.mockResolvedValue('confirm')
    mocks.deleteXianyuManageItem.mockResolvedValue({ data: { deleted: true } })
    mocks.syncXianyuManageItemsPage.mockResolvedValue({ data: {} })
    mocks.syncXianyuManageItemsAll.mockResolvedValue({ data: { synced: 25, pages: 2 } })
    mocks.updateXianyuManageItem.mockResolvedValue({ data: {} })
    mocks.setXianyuManageItemMultiQuantityDelivery.mockResolvedValue({ data: {} })
  })

  it('supports pagination and deleting items', async () => {
    const wrapper = buildWrapper()
    await flushPromises()

    expect(mocks.listXianyuManageItems).toHaveBeenCalledWith({ page: 1, page_size: 20 })
    expect(wrapper.text()).toContain('商品总数')
    expect(wrapper.text()).toContain('25')
    expect(wrapper.text()).toContain('删除')

    await wrapper.get('.pager').trigger('click')
    await flushPromises()

    expect(mocks.listXianyuManageItems).toHaveBeenLastCalledWith({ page: 2, page_size: 20 })

    const firstItem = wrapper.findAll('.mg-item')[0]
    const deleteButton = firstItem.findAll('button').find((node) => node.text().includes('删除'))
    await deleteButton!.trigger('click')
    await flushPromises()

    expect(mocks.confirmMock).toHaveBeenCalled()
    expect(mocks.deleteXianyuManageItem).toHaveBeenCalledWith('1001')
    expect(mocks.messageSuccess).toHaveBeenCalled()
  })

  it('renders cover, placeholder and price states', async () => {
    const wrapper = buildWrapper()
    await flushPromises()

    const images = wrapper.findAll('img.mg-item__cover-image')
    expect(images).toHaveLength(1)
    expect(images[0].attributes('src')).toBe('https://example.com/item-1.jpg')

    expect(wrapper.findAll('.mg-item__cover-placeholder')).toHaveLength(1)
    expect(wrapper.find('.mg-item__price-pill').text()).toContain('¥10')
    expect(wrapper.find('.mg-item__price-pill--muted').text()).toContain('未设置价格')
  })
  it('renders unified toolbar and helper aside for item operations', async () => {
    const wrapper = buildWrapper()
    await flushPromises()

    expect(wrapper.find('.mg-section__toolbar').exists()).toBe(true)
    expect(wrapper.find('.mg-items-shell').exists()).toBe(true)
    expect(wrapper.find('.mg-items-aside').exists()).toBe(true)
    expect(wrapper.find('.mg-item__detail').classes()).toContain('mg-item__detail--clamp')
  })


  it('renders item meta strip, highlighted price block and primary action row', async () => {
    const wrapper = buildWrapper()
    await flushPromises()

    expect(wrapper.find('.mg-item__meta').exists()).toBe(true)
    expect(wrapper.find('.mg-item__price-block').exists()).toBe(true)
    expect(wrapper.find('.mg-item__status').text()).toContain('在售')
    expect(wrapper.find('.mg-item__primary-action').text()).toContain('多数量发货')
  })
})
