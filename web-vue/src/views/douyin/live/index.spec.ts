import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

const currentDir = dirname(fileURLToPath(import.meta.url))
const source = readFileSync(resolve(currentDir, 'index.vue'), 'utf-8')

describe('Douyin live layout', () => {
  it('keeps search and loading states vertically centered with viewport-based height', () => {
    expect(source).toContain('min-height: calc(100vh - 48px);')
    expect(source).toContain('.search-page {')
    expect(source).toContain('.loading-page {')
    expect(source).toContain('flex: 1;')
  })

  it('uses an elevated centered search card with refined spacing and responsive feature layout', () => {
    expect(source).toContain('padding: 32px 24px;')
    expect(source).toContain('box-shadow: 0 24px 60px rgba(15, 23, 42, 0.18);')
    expect(source).toContain('min-height: 52px;')
    expect(source).toContain('grid-template-columns: repeat(3, minmax(0, 1fr));')
    expect(source).toContain('max-width: 420px;')
  })

  it('renders loading state as an elevated glass card with richer feedback copy', () => {
    expect(source).toContain('class="loading-subtext"')
    expect(source).toContain('padding: 36px 32px;')
    expect(source).toContain('min-width: min(100%, 420px);')
    expect(source).toContain('box-shadow: 0 24px 60px rgba(15, 23, 42, 0.16);')
    expect(source).toContain('letter-spacing: 0.08em;')
  })
})
