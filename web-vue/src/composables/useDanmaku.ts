/**
 * 高性能 Canvas 弹幕引擎
 * 特性：
 * - 基于 Canvas 渲染，支持数千条弹幕流畅显示
 * - 智能轨道分配，避免弹幕重叠
 * - 支持多种弹幕类型和样式
 * - 平滑滚动动画
 */

export interface DanmakuItem {
  id: string | number
  content: string
  type?: 'chat' | 'gift' | 'like' | 'follow' | 'member' | 'system'
  color?: string
  fontSize?: number
  speed?: number
  avatar?: string
  nickname?: string
}

interface Track {
  y: number
  lastEndTime: number
}

export class DanmakuEngine {
  private canvas: HTMLCanvasElement | null = null
  private ctx: CanvasRenderingContext2D | null = null
  private items: DanmakuItem[] = []
  private tracks: Track[] = []
  private animationId: number = 0
  private isRunning: boolean = false
  private width: number = 0
  private height: number = 0
  private dpr: number = 1
  private itemPool: Map<string | number, {
    x: number
    y: number
    item: DanmakuItem
    width: number
    speed: number
    opacity: number
  }> = new Map()
  
  // 配置
  private config = {
    trackHeight: 32,
    fontSize: 16,
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    speed: 80, // 像素/秒
    maxItems: 200,
    opacity: 1,
    topMargin: 10,
    rightMargin: 20,
  }

  // 类型颜色配置
  private typeColors: Record<string, string> = {
    chat: '#ffffff',
    gift: '#ff6b6b',
    like: '#ffb347',
    follow: '#4ecdc4',
    member: '#45b7d1',
    system: '#ffd700',
  }

  constructor(canvas: HTMLCanvasElement) {
    this.canvas = canvas
    this.ctx = canvas.getContext('2d')
    this.dpr = window.devicePixelRatio || 1
    this.resize()
  }

  resize() {
    if (!this.canvas) return
    const rect = this.canvas.getBoundingClientRect()
    this.width = rect.width
    this.height = rect.height
    this.canvas.width = this.width * this.dpr
    this.canvas.height = this.height * this.dpr
    if (this.ctx) {
      this.ctx.scale(this.dpr, this.dpr)
    }
    // 重新计算轨道
    this.initTracks()
  }

  private initTracks() {
    this.tracks = []
    const trackCount = Math.floor((this.height - this.config.topMargin) / this.config.trackHeight)
    for (let i = 0; i < trackCount; i++) {
      this.tracks.push({
        y: this.config.topMargin + i * this.config.trackHeight + this.config.trackHeight / 2,
        lastEndTime: 0
      })
    }
  }

  add(item: DanmakuItem) {
    if (this.items.length >= this.config.maxItems) {
      // 移除最早的弹幕
      const firstKey = this.items[0].id
      this.itemPool.delete(firstKey)
      this.items.shift()
    }
    this.items.push(item)
    this.createItem(item)
  }

  private createItem(item: DanmakuItem) {
    if (!this.ctx) return
    
    const fontSize = item.fontSize || this.config.fontSize
    this.ctx.font = `bold ${fontSize}px ${this.config.fontFamily}`
    
    // 计算弹幕宽度
    let textWidth = this.ctx.measureText(item.content).width
    if (item.nickname) {
      textWidth += this.ctx.measureText(item.nickname + ': ').width
    }
    
    // 找一个可用的轨道
    const track = this.findAvailableTrack(textWidth, item.speed || this.config.speed)
    if (!track) return
    
    const poolItem = {
      x: this.width + this.config.rightMargin,
      y: track.y,
      item,
      width: textWidth + 20,
      speed: item.speed || this.config.speed,
      opacity: 1
    }
    
    this.itemPool.set(item.id, poolItem)
    track.lastEndTime = Date.now() + (textWidth + this.width) / poolItem.speed * 1000
  }

  private findAvailableTrack(textWidth: number, speed: number): Track | null {
    const now = Date.now()
    
    // 随机选择轨道，避免都挤在上面
    const shuffled = [...this.tracks].sort(() => Math.random() - 0.5)
    
    for (const track of shuffled) {
      // 检查轨道是否可用
      const estimatedTime = (textWidth + this.width) / speed * 1000
      if (now > track.lastEndTime - estimatedTime * 0.3) {
        return track
      }
    }
    
    // 如果没有可用轨道，返回随机一个
    return this.tracks[Math.floor(Math.random() * this.tracks.length)]
  }

  start() {
    if (this.isRunning) return
    this.isRunning = true
    this.lastTime = performance.now()
    this.animate()
  }

  stop() {
    this.isRunning = false
    if (this.animationId) {
      cancelAnimationFrame(this.animationId)
    }
  }

  clear() {
    this.items = []
    this.itemPool.clear()
    this.tracks.forEach(t => t.lastEndTime = 0)
    if (this.ctx) {
      this.ctx.clearRect(0, 0, this.width, this.height)
    }
  }

  private lastTime: number = 0

  private animate = () => {
    if (!this.isRunning || !this.ctx) return
    
    const now = performance.now()
    const deltaTime = (now - this.lastTime) / 1000
    this.lastTime = now
    
    // 清空画布
    this.ctx.clearRect(0, 0, this.width, this.height)
    
    // 更新和绘制所有弹幕
    const toRemove: (string | number)[] = []
    
    this.itemPool.forEach((poolItem, id) => {
      // 更新位置
      poolItem.x -= poolItem.speed * deltaTime
      
      // 检查是否超出屏幕
      if (poolItem.x + poolItem.width < 0) {
        toRemove.push(id)
        return
      }
      
      // 绘制弹幕
      this.drawItem(poolItem)
    })
    
    // 移除超出屏幕的弹幕
    toRemove.forEach(id => {
      this.itemPool.delete(id)
      const idx = this.items.findIndex(i => i.id === id)
      if (idx > -1) this.items.splice(idx, 1)
    })
    
    this.animationId = requestAnimationFrame(this.animate)
  }

  private drawItem(poolItem: {
    x: number
    y: number
    item: DanmakuItem
    width: number
    speed: number
    opacity: number
  }) {
    if (!this.ctx) return
    
    const { x, y, item } = poolItem
    const fontSize = item.fontSize || this.config.fontSize
    const type = item.type || 'chat'
    const color = item.color || this.typeColors[type] || '#ffffff'
    
    this.ctx.save()
    
    // 绘制背景（可选）
    if (type === 'gift' || type === 'follow') {
      const bgWidth = poolItem.width
      this.ctx.fillStyle = type === 'gift' 
        ? 'rgba(254, 44, 85, 0.2)' 
        : 'rgba(78, 205, 196, 0.2)'
      this.ctx.beginPath()
      this.ctx.roundRect(x - 10, y - fontSize / 2 - 4, bgWidth, fontSize + 8, 12)
      this.ctx.fill()
    }
    
    // 设置字体
    this.ctx.font = `bold ${fontSize}px ${this.config.fontFamily}`
    this.ctx.textBaseline = 'middle'
    
    let currentX = x
    
    // 绘制昵称
    if (item.nickname) {
      this.ctx.fillStyle = '#409eff'
      this.ctx.fillText(item.nickname + ': ', currentX, y)
      currentX += this.ctx.measureText(item.nickname + ': ').width
    }
    
    // 绘制内容
    this.ctx.fillStyle = color
    this.ctx.fillText(item.content, currentX, y)
    
    this.ctx.restore()
  }

  destroy() {
    this.stop()
    this.clear()
    this.canvas = null
    this.ctx = null
  }
}

// 创建全局实例
let engineInstance: DanmakuEngine | null = null

export function createDanmakuEngine(canvas: HTMLCanvasElement): DanmakuEngine {
  if (engineInstance) {
    engineInstance.destroy()
  }
  engineInstance = new DanmakuEngine(canvas)
  return engineInstance
}

export function getDanmakuEngine(): DanmakuEngine | null {
  return engineInstance
}
