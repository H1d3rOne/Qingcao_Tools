import { config } from '@vue/test-utils'

config.global.stubs = {
  transition: false,
  'router-link': { template: '<a><slot /></a>' },
  'router-view': { template: '<div />' },
}
