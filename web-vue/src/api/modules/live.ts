import { request } from '../request'

// 直播间信息
export interface LiveRoomInfo {
  web_rid: string  // 房间短ID
  room_id: string  // 房间长ID，用于弹幕WebSocket
  user_id?: string
  title?: string
  owner?: {
    nickname: string
    avatar: string
  }
  stream_url?: {
    rtmp: string
    hls: string
    flv: string
  }
  user_count?: number
  status: number  // 2=直播中, 4=未开播
}

// 徽章图片
export interface BadgeImage {
  name: string
  url: string
  level: number
  alternative_text: string
}

// 直播消息
export interface LiveMessage {
  type: 'gift' | 'chat' | 'member' | 'like' | 'follow' | 'room_stats' | 'connected' | 'ready' | 'error' | 'disconnected' | 'pong'
  display_type?: 'message' | 'notification' | 'stats'  // 消息显示类型
  
  // 用户相关
  badge_image_list?: BadgeImage[]  // 徽章图片列表
  nickname?: string  // 昵称
  
  // 聊天消息
  content?: string  // 消息内容
  
  // 礼物消息
  gift_name?: string  // 礼物名称
  combo_count?: number  // 礼物数量
  to_user_nickname?: string  // 接收者昵称
  
  // 进入直播间消息
  member_count?: number  // 在线人数
  
  // 房间信息消息
  total?: number  // 在线人数
  
  // 兼容旧字段
  user?: {
    sec_uid: string
    nickname: string
    avatar?: string
  }
  gift?: {
    id: string
    name: string
    icon?: string
  }
  count?: number
  to_user?: {
    sec_uid: string
    nickname: string
  }
  room_info?: LiveRoomInfo
  message?: string
  display_long?: string
}

// WebSocket 连接回调
export interface WebSocketCallbacks {
  onConnected?: (roomInfo: LiveRoomInfo) => void
  onMessage?: (msg: LiveMessage) => void
  onError?: (error: string) => void
  onDisconnected?: () => void
}

/**
 * 获取直播间信息
 * @param liveUrl 抖音直播链接，如 https://live.douyin.com/802236344116
 */
export async function getLiveInfo(liveUrl: string): Promise<LiveRoomInfo> {
  const res = await request.post<{ data: LiveRoomInfo }>('/douyin/live/info', { input: liveUrl })
  return res.data
}

/**
 * 创建 WebSocket 连接
 * @param liveUrl 抖音直播链接
 * @param callbacks 回调函数
 * @returns WebSocket 实例和控制函数
 */
export function createLiveWebSocket(
  liveUrl: string,
  callbacks: WebSocketCallbacks = {}
): {
  ws: WebSocket | null
  connect: () => void
  disconnect: () => void
  send: (data: string) => void
  isConnected: () => boolean
} {
  let ws: WebSocket | null = null
  let reconnectTimer: number | null = null
  let heartbeatTimer: number | null = null
  const maxReconnectDelay = 30000 // 最大重连延迟 30 秒
  let reconnectAttempts = 0

  function connect() {
    console.log('connect() 被调用, 当前 ws 状态:', ws?.readyState)
    
    if (ws && (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN)) {
      console.log('WebSocket 已存在且正在连接或已连接，跳过')
      return
    }

    // 构建 WebSocket URL
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${location.host}/api/v1/douyin/live/ws/${encodeURIComponent(liveUrl)}`
    
    console.log('WebSocket 连接 URL:', wsUrl)
    
    try {
      console.log('创建 WebSocket 实例...')
      ws = new WebSocket(wsUrl)
      console.log('WebSocket 实例已创建, readyState:', ws.readyState)
      
      ws.onopen = () => {
        console.log('WebSocket 已连接')
        reconnectAttempts = 0
        // 启动心跳
        startHeartbeat()
      }
      
      ws.onmessage = (event) => {
        try {
          const msg: LiveMessage = JSON.parse(event.data)
          console.log('WebSocket 收到消息:', msg.type, msg)
          
          switch (msg.type) {
            case 'connected':
              console.log('房间信息:', msg.room_info)
              callbacks.onConnected?.(msg.room_info!)
              break
            case 'ready':
              console.log('弹幕连接就绪')
              break
            case 'pong':
              // 心跳响应
              break
            case 'error':
              console.error('错误消息:', msg.message)
              callbacks.onError?.(msg.message || '未知错误')
              break
            case 'disconnected':
              callbacks.onDisconnected?.()
              break
            case 'chat':
            case 'gift':
            case 'like':
            case 'follow':
            case 'member':
            case 'room_stats':
              console.log('调用 onMessage 回调:', msg.type, msg.nickname, msg.content || msg.gift_name)
              callbacks.onMessage?.(msg)
              break
            default:
              console.log('未知消息类型:', msg.type, msg)
              callbacks.onMessage?.(msg)
          }
        } catch (e) {
          console.error('解析消息失败:', e, event.data)
        }
      }
      
      ws.onerror = (error) => {
        console.error('WebSocket 错误:', error)
        callbacks.onError?.('WebSocket 连接错误')
      }
      
      ws.onclose = (event) => {
        console.log('WebSocket 已关闭:', event.code, event.reason)
        stopHeartbeat()
        
        // 非正常关闭时尝试重连
        if (event.code !== 1000 && event.code !== 1001) {
          scheduleReconnect()
        } else {
          callbacks.onDisconnected?.()
        }
      }
      
    } catch (error) {
      console.error('创建 WebSocket 失败:', error)
      callbacks.onError?.('创建 WebSocket 失败')
    }
  }
  
  function disconnect() {
    stopHeartbeat()
    clearReconnectTimer()
    
    if (ws) {
      // 发送停止命令
      if (ws.readyState === WebSocket.OPEN) {
        ws.send('stop')
      }
      ws.close(1000, '用户主动断开')
      ws = null
    }
  }
  
  function send(data: string) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(data)
    }
  }
  
  function isConnected(): boolean {
    return ws !== null && ws.readyState === WebSocket.OPEN
  }
  
  function startHeartbeat() {
    stopHeartbeat()
    heartbeatTimer = window.setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send('ping')
      }
    }, 30000) // 30 秒发送一次心跳
  }
  
  function stopHeartbeat() {
    if (heartbeatTimer) {
      clearInterval(heartbeatTimer)
      heartbeatTimer = null
    }
  }
  
  function scheduleReconnect() {
    clearReconnectTimer()
    
    // 指数退避重连
    const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), maxReconnectDelay)
    reconnectAttempts++
    
    console.log(`${delay / 1000} 秒后尝试重连...`)
    
    reconnectTimer = window.setTimeout(() => {
      console.log('尝试重新连接...')
      connect()
    }, delay)
  }
  
  function clearReconnectTimer() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }
  
  return {
    ws,
    connect,
    disconnect,
    send,
    isConnected
  }
}
