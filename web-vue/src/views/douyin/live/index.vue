<script setup lang="ts">
import { ref, onUnmounted, nextTick, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { 
  User, 
  Present, 
  ChatDotRound, 
  StarFilled, 
  Connection,
  MoreFilled,
  MagicStick,
  VideoPlay,
  Present as GiftIcon,
  Share,
  Search,
  Iphone,
  UserFilled,
  ChatLineRound,
  Iphone as Phone,
  TrendCharts,
  Trophy,
  View,
  Hide
} from '@element-plus/icons-vue'
import { 
  getLiveInfo, 
  createLiveWebSocket,
  type LiveMessage, 
  type LiveRoomInfo,
  type WebSocketCallbacks,
  type BadgeImage
} from '@/api/modules/live'
import { useNotification } from '@/composables'
import { createDanmakuEngine, DanmakuEngine, DanmakuItem } from '@/composables/useDanmaku'
import flvjs from 'flv.js'

const route = useRoute()
const { error, success } = useNotification()

const inputUrl = ref('')
const loading = ref(false)
const liveInfo = ref<LiveRoomInfo | null>(null)

// 检查是否从搜索页面跳转过来
const isFromSearch = ref(false)
const isMonitoring = ref(false)
const messages = ref<LiveMessage[]>([])
const danmakuListRef = ref<HTMLElement | null>(null)
const videoRef = ref<HTMLVideoElement | null>(null)
const flvPlayer = ref<any>(null)

const currentStreamUrl = ref('')
const streamType = ref<'flv' | 'hls'>('flv')

// Canvas 弹幕引擎
const danmakuCanvasRef = ref<HTMLCanvasElement | null>(null)
const danmakuEngine = ref<DanmakuEngine | null>(null)
const danmakuIdCounter = ref(0)

// 聊天列表消息（右侧面板）- 只有聊天和礼物消息
const chatMessages = ref<LiveMessage[]>([])

// 通知消息（输入框上方）- 点赞、关注、进入直播间
const notificationMessage = ref<LiveMessage | null>(null)
let notificationTimer: number | null = null

// 在线人数
const onlineCount = ref(0)

// 输入消息
const inputMessage = ref('')

// 弹幕开关
const danmakuEnabled = ref(true)

// WebSocket 连接
let wsConnection: ReturnType<typeof createLiveWebSocket> | null = null

function copyStreamUrl() {
  if (currentStreamUrl.value) {
    navigator.clipboard.writeText(currentStreamUrl.value)
    success('视频流地址已复制')
  }
}

function openStreamUrl() {
  if (currentStreamUrl.value) {
    window.open(currentStreamUrl.value, '_blank')
  }
}

function sendMessage() {
  if (!inputMessage.value.trim() || !wsConnection) {
    return
  }
  
  // 发送消息到 WebSocket
  const message = {
    type: 'chat',
    content: inputMessage.value.trim(),
    timestamp: Date.now()
  }
  
  // 添加到本地消息列表
  chatMessages.value.push({
    type: 'chat',
    nickname: '我',
    content: inputMessage.value.trim(),
    timestamp: Date.now()
  })
  
  // 清空输入框
  inputMessage.value = ''
  
  // 滚动到底部
  nextTick(() => {
    if (danmakuListRef.value) {
      danmakuListRef.value.scrollTop = danmakuListRef.value.scrollHeight
    }
  })
  
  success('消息已发送')
}

function initFlvPlayer(url: string) {
  if (!videoRef.value) return
  
  if (flvPlayer.value) {
    flvPlayer.value.destroy()
    flvPlayer.value = null
  }
  
  if (!flvjs.isSupported()) {
    error('浏览器不支持 FLV 播放')
    return
  }
  
  flvPlayer.value = flvjs.createPlayer({
    type: 'flv',
    url: url,
    isLive: true,
    hasAudio: true,
    hasVideo: true,
    enableStashBuffer: false,
  }, {
    enableWorker: true,
    enableStashBuffer: false,
    stashInitialSize: 128,
    lazyLoad: false,
  })
  
  flvPlayer.value.attachMediaElement(videoRef.value)
  flvPlayer.value.load()
  
  flvPlayer.value.on(flvjs.Events.ERROR, (errType: any, errDetail: any) => {
    // console.error('FLV 播放错误:', errType, errDetail)
    error('视频播放失败，请尝试在新窗口播放')
  })
  
  flvPlayer.value.play().catch((e: any) => {
    // console.log('自动播放失败，需要用户交互:', e)
  })
}

function destroyPlayer() {
  if (flvPlayer.value) {
    flvPlayer.value.destroy()
    flvPlayer.value = null
  }
}

// 初始化 Canvas 弹幕引擎
function initDanmakuEngine() {
  if (!danmakuCanvasRef.value) return
  
  danmakuEngine.value = createDanmakuEngine(danmakuCanvasRef.value)
  danmakuEngine.value.start()
  // console.log('弹幕引擎已启动')
}

// 添加弹幕到 Canvas
function addDanmaku(msg: LiveMessage) {
  if (!danmakuEngine.value || !danmakuEnabled.value) return
  
  const danmakuId = danmakuIdCounter.value++
  const type = msg.type
  
  let content = ''
  let color = '#ffffff'
  
  // 获取昵称（兼容新旧格式）
  const nickname = msg.nickname || msg.user?.nickname || ''
  
  switch (type) {
    case 'chat':
      content = msg.content || ''
      color = '#ffffff'
      break
    case 'gift':
      content = `🎁 送出 ${msg.gift_name || msg.gift?.name || '礼物'} x${msg.combo_count || msg.count || 1}`
      color = '#ff6b6b'
      break
    case 'like':
      content = `❤️ 点赞了`
      color = '#ffb347'
      break
    case 'follow':
      content = '✨ 关注了主播'
      color = '#4ecdc4'
      break
    case 'member':
      content = `👋 进入直播间`
      color = '#45b7d1'
      break
    case 'room_stats':
      content = msg.display_long || ''
      color = '#ffd700'
      break
    default:
      return
  }
  
  if (!content) return
  
  const danmakuItem: DanmakuItem = {
    id: danmakuId,
    content,
    type: type as any,
    color,
    nickname,
    speed: 80 + Math.random() * 40,
  }
  
  danmakuEngine.value.add(danmakuItem)
}

// 添加消息到聊天列表（只有聊天和礼物消息）
function addChatMessage(msg: LiveMessage) {
  if (chatMessages.value.length >= 50) {
    chatMessages.value.shift()
  }
  chatMessages.value.push(msg)
  
  nextTick(() => {
    if (danmakuListRef.value) {
      danmakuListRef.value.scrollTop = danmakuListRef.value.scrollHeight
    }
  })
}

// 显示通知消息（点赞、关注、进入直播间）
function showNotification(msg: LiveMessage) {
  notificationMessage.value = msg
  
  // 清除之前的定时器
  if (notificationTimer) {
    clearTimeout(notificationTimer)
  }
  
  // 3秒后消失
  notificationTimer = window.setTimeout(() => {
    notificationMessage.value = null
  }, 3000)
}

// 更新在线人数
function updateOnlineCount(count: number) {
  if (count > 0) {
    onlineCount.value = count
    if (liveInfo.value) {
      liveInfo.value.user_count = count
    }
  }
}

// 处理消息
function handleMessage(msg: LiveMessage) {
  // console.log('handleMessage 被调用:', msg.type, msg.nickname)
  
  // 添加到 Canvas 弹幕
  addDanmaku(msg)
  
  // 根据显示类型处理
  const displayType = msg.display_type
  
  // console.log('display_type:', displayType)
  
  if (displayType === 'message') {
    // 聊天消息和礼物消息 - 显示在消息窗口
    // console.log('添加到聊天列表:', msg.type)
    addChatMessage(msg)
  } else if (displayType === 'notification') {
    // 点赞、关注、进入直播间 - 显示在输入框上方
    // console.log('显示通知:', msg.type)
    showNotification(msg)
    
    // 进入直播间消息 - 更新在线人数
    if (msg.type === 'member' && msg.member_count) {
      updateOnlineCount(msg.member_count)
    }
  } else if (displayType === 'stats') {
    // 房间信息消息 - 更新在线人数
    if (msg.total) {
      updateOnlineCount(msg.total)
    }
  } else {
    // 兼容旧格式
    // console.log('兼容旧格式:', msg.type)
    switch (msg.type) {
      case 'chat':
      case 'gift':
        addChatMessage(msg)
        break
      case 'like':
      case 'follow':
      case 'member':
        showNotification(msg)
        if (msg.type === 'member' && msg.member_count) {
          updateOnlineCount(msg.member_count)
        }
        break
      case 'room_stats':
        if (msg.total) {
          updateOnlineCount(msg.total)
        }
        break
    }
  }
}

// 获取徽章显示
function getBadgeDisplay(badgeList?: BadgeImage[]): string {
  if (!badgeList || badgeList.length === 0) return ''
  const badge = badgeList[0]
  if (badge.level > 0) {
    return `Lv.${badge.level}`
  }
  return badge.name || ''
}

async function handleSearch() {
  if (!inputUrl.value.trim()) {
    error('请输入直播间链接')
    return
  }

  const liveUrl = inputUrl.value.trim()
  
  // 验证是否为有效的直播链接
  if (!liveUrl.includes('live.douyin.com') && !liveUrl.includes('v.douyin.com') && !/^\d+$/.test(liveUrl)) {
    if (/^\d+$/.test(liveUrl)) {
      inputUrl.value = `https://live.douyin.com/${liveUrl}`
    } else {
      error('请输入正确的抖音直播链接')
      return
    }
  }

  loading.value = true
  liveInfo.value = null
  messages.value = []
  chatMessages.value = []
  onlineCount.value = 0
  destroyPlayer()
  disconnectWebSocket()
  
  // 清空弹幕
  if (danmakuEngine.value) {
    danmakuEngine.value.clear()
  }
  
  try {
    const res = await getLiveInfo(inputUrl.value.trim())
    liveInfo.value = res
    onlineCount.value = res.user_count || 0
    
    if (res.stream_url?.flv) {
      currentStreamUrl.value = res.stream_url.flv
      streamType.value = 'flv'
    } else if (res.stream_url?.hls) {
      currentStreamUrl.value = res.stream_url.hls
      streamType.value = 'hls'
    } else if (res.stream_url?.rtmp) {
      currentStreamUrl.value = res.stream_url.rtmp
      streamType.value = 'flv'
    }
    
    success('查询成功')
    
    // console.log('直播间状态:', res.status, '是否直播中:', res.status === 2)
    
    if (res.status === 2) {
      nextTick(() => {
        if (streamType.value === 'flv' && currentStreamUrl.value) {
          initFlvPlayer(currentStreamUrl.value)
        }
        initDanmakuEngine()
      })
      // console.log('准备启动 WebSocket...')
      startWebSocket()
      isMonitoring.value = true
    } else if (res.status === 4) {
      // console.log('直播间未开播')
      error('主播未开播,无法获取实时弹幕。请等待主播开播后再试!')
    } else {
      // console.log('直播间状态异常:', res.status)
      error('直播间状态异常,请稍后重试')
    }
  } catch (err: any) {
    const errorMsg = err?.message || err?.error || '查询失败，请检查输入是否正确'
    if (errorMsg.includes('timeout')) {
      error('请求超时，请稍后重试')
    } else {
      error(errorMsg)
    }
    // console.error('查询失败:', err)
  } finally {
    loading.value = false
  }
}

function startWebSocket() {
  const liveUrl = inputUrl.value.trim()
  
  // console.log('startWebSocket 被调用, liveUrl:', liveUrl)
  
  // 定义回调
  const callbacks: WebSocketCallbacks = {
    onConnected: (roomInfo) => {
      // console.log('WebSocket 已连接, room_id:', roomInfo.room_id)
      isMonitoring.value = true
    },
    onMessage: (msg) => {
      // console.log('onMessage 回调:', msg.type)
      handleMessage(msg)
    },
    onError: (errMsg) => {
      // console.error('WebSocket 错误:', errMsg)
      error(errMsg)
      isMonitoring.value = false
    },
    onDisconnected: () => {
      // console.log('WebSocket 已断开')
      isMonitoring.value = false
    }
  }
  
  // console.log('创建 WebSocket 连接...')
  // 创建 WebSocket 连接
  wsConnection = createLiveWebSocket(liveUrl, callbacks)
  // console.log('调用 wsConnection.connect()')
  wsConnection.connect()
  // console.log('WebSocket connect() 已调用')
}

function disconnectWebSocket() {
  if (wsConnection) {
    wsConnection.disconnect()
    wsConnection = null
  }
  isMonitoring.value = false
  
  // 清除通知定时器
  if (notificationTimer) {
    clearTimeout(notificationTimer)
    notificationTimer = null
  }
}

function getDanmakuContent(msg: LiveMessage) {
  const nickname = msg.nickname || msg.user?.nickname || ''
  switch (msg.type) {
    case 'chat': 
      return msg.content || ''
    case 'gift': 
      return `${nickname} 送出 ${msg.gift_name || msg.gift?.name || '礼物'} x${msg.combo_count || msg.count || 1}`
    case 'like': 
      return `${nickname} 点赞了`
    case 'follow': 
      return `${nickname} 关注了主播`
    case 'member': 
      return `${nickname} 进入了直播间`
    case 'room_stats': 
      return msg.display_long || `在线人数: ${msg.total || 0}`
    default: 
      return ''
  }
}

function handleVideoError() {
  error('视频加载失败，请尝试在新窗口播放或复制地址到播放器中打开')
}

// 格式化数字
function formatCount(num: number): string {
  if (num >= 10000) {
    return (num / 10000).toFixed(1) + 'w'
  }
  if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'k'
  }
  return num.toString()
}

// 窗口大小变化时重置弹幕引擎
function handleResize() {
  if (danmakuEngine.value && danmakuCanvasRef.value) {
    danmakuEngine.value.resize()
  }
}

onMounted(() => {
  window.addEventListener('resize', handleResize)
  
  // 检查路由参数，如果有 room_id 则自动加载直播间
  const roomId = route.query.room_id as string
  const hlsUrl = route.query.hls as string
  const flvUrl = route.query.flv as string
  const rtmpUrl = route.query.rtmp as string
  const title = route.query.title as string
  const nickname = route.query.nickname as string
  const avatar = route.query.avatar as string
  const cover = route.query.cover as string
  
  if (roomId) {
    isFromSearch.value = true
    loading.value = true
    inputUrl.value = `https://live.douyin.com/${roomId}`
    
    // 如果有直播流地址，直接使用，不需要重新获取
    if (hlsUrl || flvUrl || rtmpUrl) {
      liveInfo.value = {
        web_rid: roomId,
        room_id: roomId,
        title: title || '',
        owner: {
          nickname: nickname || '',
          avatar: avatar || '',
          sec_uid: '',
          uid: '',
          follow_count: 0,
          follower_count: 0,
          total_likes: 0,
          signature: '',
          verified: false,
          verify_type: -1,
          city: '',
          province: '',
          country: '',
          location: '',
          age: 0,
          gender: 0
        },
        stream_url: {
          hls: hlsUrl || '',
          flv: flvUrl || '',
          rtmp: rtmpUrl || ''
        },
        user_count: 0,
        status: 2  // 直播中
      }
      
      // 设置直播流地址
      if (flvUrl) {
        currentStreamUrl.value = flvUrl
        streamType.value = 'flv'
      } else if (hlsUrl) {
        currentStreamUrl.value = hlsUrl
        streamType.value = 'hls'
      } else if (rtmpUrl) {
        currentStreamUrl.value = rtmpUrl
        streamType.value = 'flv'
      }
      
      loading.value = false
      success('加载成功')
      
      // 初始化播放器和弹幕
      nextTick(() => {
        if (streamType.value === 'flv' && currentStreamUrl.value) {
          initFlvPlayer(currentStreamUrl.value)
        }
        initDanmakuEngine()
      })
      
      // 启动 WebSocket
      startWebSocket()
      isMonitoring.value = true
    } else {
      // 没有直播流地址，需要从后端获取
      handleSearch()
    }
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  destroyPlayer()
  disconnectWebSocket()
  
  // 清除通知定时器
  if (notificationTimer) {
    clearTimeout(notificationTimer)
    notificationTimer = null
  }
  
  if (danmakuEngine.value) {
    danmakuEngine.value.destroy()
  }
})
</script>

<template>
  <div class="live-container">
    <!-- 加载状态 - 从搜索页面跳转时显示 -->
    <div v-if="loading && isFromSearch" class="loading-page">
      <div class="search-background">
        <div class="bg-circle bg-circle-1"></div>
        <div class="bg-circle bg-circle-2"></div>
        <div class="bg-circle bg-circle-3"></div>
      </div>
      <div class="loading-content">
        <span class="loading-badge">LIVE CONNECTING</span>
        <el-icon class="loading-icon"><VideoPlay /></el-icon>
        <p class="loading-text">正在加载直播间...</p>
        <p class="loading-subtext">正在建立直播流与实时消息通道，请稍候片刻。</p>
      </div>
    </div>
    
    <!-- 输入页面 -->
    <div v-else-if="!liveInfo" class="search-page">
      <div class="search-background">
        <div class="bg-circle bg-circle-1"></div>
        <div class="bg-circle bg-circle-2"></div>
        <div class="bg-circle bg-circle-3"></div>
      </div>
      
      <div class="search-box-wrapper">
        <div class="search-header">
          <div class="logo-icon">
            <el-icon><VideoPlay /></el-icon>
          </div>
          <h1 class="search-title">直播间</h1>
          <p class="search-subtitle">探索精彩直播内容</p>
        </div>
        
        <div class="search-input-wrapper">
          <div class="search-input-container">
            <el-input
              v-model="inputUrl"
              placeholder="输入抖音直播链接，如 https://live.douyin.com/802236344116"
              size="large"
              clearable
              @keyup.enter="handleSearch"
              class="search-input"
            >
              <template #prefix>
                <el-icon class="search-icon"><Search /></el-icon>
              </template>
            </el-input>
            <el-button 
              type="primary" 
              @click="handleSearch" 
              :loading="loading"
              class="search-button"
            >
              <span v-if="!loading">开始探索</span>
              <span v-else>搜索中...</span>
            </el-button>
          </div>
        </div>
        
        <div class="search-features">
          <div class="feature-item">
            <el-icon class="feature-icon"><TrendCharts /></el-icon>
            <span class="feature-text">实时弹幕</span>
          </div>
          <div class="feature-item">
            <el-icon class="feature-icon"><Trophy /></el-icon>
            <span class="feature-text">高清直播</span>
          </div>
          <div class="feature-item">
            <el-icon class="feature-icon"><User /></el-icon>
            <span class="feature-text">观众互动</span>
          </div>
        </div>
      </div>
    </div>

    <div v-else class="live-page">
      <div class="video-section">
        <div class="video-container">
          <video
            ref="videoRef"
            class="video-player"
            controls
            autoplay
            muted
            @error="handleVideoError"
          ></video>
          
          <!-- Canvas 弹幕层 -->
          <canvas
            ref="danmakuCanvasRef"
            class="danmaku-canvas"
          ></canvas>
          
          <!-- 直播状态指示 -->
          <div class="live-status-badge" :class="{ 'is-live': liveInfo.status === 2 }">
            <span class="status-dot"></span>
            {{ liveInfo.status === 2 ? '直播中' : '未开播' }}
          </div>
          
          <!-- 观看人数 -->
          <div class="viewer-count">
            <el-icon><User /></el-icon>
            {{ formatCount(onlineCount || liveInfo.user_count || 0) }}
          </div>
          
          <!-- 直播间标题 -->
          <div class="live-title-overlay">
            {{ liveInfo.title || '直播间' }}
          </div>
        </div>
        
        <!-- 视频下方控制栏 -->
        <div class="video-controls">
          <div class="control-item" @click="danmakuEnabled = !danmakuEnabled" :title="danmakuEnabled ? '关闭弹幕' : '开启弹幕'">
            <el-icon class="control-icon" :class="{ active: danmakuEnabled }">
              <View v-if="danmakuEnabled" />
              <Hide v-else />
            </el-icon>
            <span class="control-text">{{ danmakuEnabled ? '弹幕开' : '弹幕关' }}</span>
          </div>
        </div>
      </div>
      
      <div class="sidebar">
        <div class="room-header">
          <div class="anchor-info">
            <el-avatar 
              :size="48" 
              :src="liveInfo.owner?.avatar"
              class="anchor-avatar"
            >
              <el-icon><UserFilled /></el-icon>
            </el-avatar>
            <div class="anchor-details">
              <h3 class="anchor-name">{{ liveInfo.owner?.nickname || '主播' }}</h3>
              <p class="room-title">{{ liveInfo.title || '直播间' }}</p>
            </div>
          </div>
          
          <!-- 分享按钮 -->
          <div class="share-icon-button" @click="copyStreamUrl" title="复制视频流地址">
            <el-icon><Share /></el-icon>
          </div>
          
          <div class="action-buttons">
            <el-button 
              type="primary" 
              :icon="VideoPlay"
              @click="openStreamUrl"
              size="small"
            >
              新窗口播放
            </el-button>
          </div>
        </div>
        
        <div class="danmaku-list" ref="danmakuListRef">
          <div 
            v-for="(msg, index) in chatMessages" 
            :key="index"
            class="message-item"
            :class="msg.type"
          >
            <template v-if="msg.type === 'chat'">
              <!-- 聊天消息: badge_image_list, nickname, content -->
              <span v-if="getBadgeDisplay(msg.badge_image_list)" class="badge">{{ getBadgeDisplay(msg.badge_image_list) }}</span>
              <span class="user-name">{{ msg.nickname || msg.user?.nickname }}:</span>
              <span class="message-content">{{ msg.content }}</span>
            </template>
            
            <template v-else-if="msg.type === 'gift'">
              <!-- 礼物消息: badge_image_list, nickname送出gift_name x combo_count -->
              <el-icon class="gift-icon"><Present /></el-icon>
              <span v-if="getBadgeDisplay(msg.badge_image_list)" class="badge">{{ getBadgeDisplay(msg.badge_image_list) }}</span>
              <span class="user-name">{{ msg.nickname || msg.user?.nickname }}</span>
              <span class="gift-text">送出 {{ msg.gift_name || msg.gift?.name }} x{{ msg.combo_count || msg.count }}</span>
            </template>
          </div>
          
          <div v-if="chatMessages.length === 0" class="empty-messages">
            <el-icon><ChatDotRound /></el-icon>
            <span>等待弹幕消息...</span>
          </div>
        </div>
        
        <!-- 通知消息区域（输入框上方） -->
        <div class="notification-area" :class="{ visible: notificationMessage }">
          <div v-if="notificationMessage" class="notification-item" :class="notificationMessage.type">
            <template v-if="notificationMessage.type === 'like'">
              <!-- 点赞消息: badge_image_list, nickname给主播点赞了 -->
              <el-icon class="like-icon"><StarFilled /></el-icon>
              <span v-if="getBadgeDisplay(notificationMessage.badge_image_list)" class="badge">{{ getBadgeDisplay(notificationMessage.badge_image_list) }}</span>
              <span class="user-name">{{ notificationMessage.nickname || notificationMessage.user?.nickname }}</span>
              <span class="like-text">给主播点赞了</span>
            </template>
            
            <template v-else-if="notificationMessage.type === 'follow'">
              <!-- 关注消息: badge_image_list, nickname给主播点关注了 -->
              <el-icon class="follow-icon"><Connection /></el-icon>
              <span v-if="getBadgeDisplay(notificationMessage.badge_image_list)" class="badge">{{ getBadgeDisplay(notificationMessage.badge_image_list) }}</span>
              <span class="user-name">{{ notificationMessage.nickname || notificationMessage.user?.nickname }}</span>
              <span class="follow-text">给主播点关注了</span>
            </template>
            
            <template v-else-if="notificationMessage.type === 'member'">
              <!-- 进入直播间消息: badge_image_list, nickname来了 -->
              <el-icon class="member-icon"><User /></el-icon>
              <span v-if="getBadgeDisplay(notificationMessage.badge_image_list)" class="badge">{{ getBadgeDisplay(notificationMessage.badge_image_list) }}</span>
              <span class="user-name">{{ notificationMessage.nickname || notificationMessage.user?.nickname }}</span>
              <span class="member-text">来了</span>
            </template>
          </div>
        </div>
        
        <!-- 消息输入框 -->
        <div class="message-input-area">
          <el-input
            v-model="inputMessage"
            placeholder="说点什么..."
            @keyup.enter="sendMessage"
            clearable
          >
            <template #suffix>
              <el-button 
                type="primary" 
                size="small"
                @click="sendMessage"
                :disabled="!inputMessage.trim()"
              >
                发送
              </el-button>
            </template>
          </el-input>
        </div>
        
        <div class="connection-status">
          <span class="status-indicator" :class="{ connected: isMonitoring }"></span>
          {{ isMonitoring ? '已连接' : '未连接' }}
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.live-container {
  width: 100%;
  min-height: calc(100vh - 48px);
  display: flex;
  flex-direction: column;
  background: linear-gradient(135deg, rgb(var(--app-bg-rgb)) 0%, rgb(var(--app-bg-deep-rgb)) 100%);
  overflow: hidden;
}

.loading-page {
  width: 100%;
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  padding: 32px 24px;
  box-sizing: border-box;
  background: linear-gradient(135deg, rgb(var(--app-bg-rgb)) 0%, rgb(var(--app-bg-deep-rgb)) 100%);
}

.loading-content {
  position: relative;
  z-index: 1;
  text-align: center;
  padding: 36px 32px;
  min-width: min(100%, 420px);
  background: linear-gradient(180deg, rgba(var(--app-surface-rgb) / 0.96), rgba(var(--app-surface-alt-rgb) / 0.92));
  border: 1px solid rgba(var(--app-border-rgb) / 0.78);
  border-radius: 28px;
  backdrop-filter: blur(18px);
  box-shadow: 0 24px 60px rgba(15, 23, 42, 0.16);
}

.loading-icon {
  font-size: 52px;
  color: rgb(var(--primary-color-rgb));
  margin-top: 10px;
  animation: pulse 2s ease-in-out infinite;
}

.loading-text {
  margin-top: 22px;
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: rgb(var(--app-text-strong-rgb));
}

.loading-subtext {
  margin: 10px auto 0;
  max-width: 320px;
  font-size: 14px;
  line-height: 1.7;
  color: rgb(var(--app-text-muted-rgb));
}

.loading-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 28px;
  padding: 0 14px;
  border-radius: 999px;
  background: rgba(var(--primary-color-rgb) / 0.12);
  border: 1px solid rgba(var(--primary-color-rgb) / 0.18);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: rgb(var(--primary-color-rgb));
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.search-page {
  width: 100%;
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  padding: 32px 24px;
  box-sizing: border-box;
}

.search-background {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  overflow: hidden;
  pointer-events: none;
}

.bg-circle {
  position: absolute;
  border-radius: 50%;
  opacity: 0.08;
}

.bg-circle-1 {
  width: 400px;
  height: 400px;
  background: radial-gradient(circle, rgba(var(--primary-color-rgb) / 0.3), transparent 70%);
  top: -100px;
  left: -100px;
  animation: float 20s ease-in-out infinite;
}

.bg-circle-2 {
  width: 300px;
  height: 300px;
  background: radial-gradient(circle, rgba(var(--app-accent-alt-rgb) / 0.3), transparent 70%);
  bottom: -50px;
  right: -50px;
  animation: float 15s ease-in-out infinite reverse;
}

.bg-circle-3 {
  width: 200px;
  height: 200px;
  background: radial-gradient(circle, rgba(var(--app-accent-soft-rgb) / 0.3), transparent 70%);
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  animation: pulse 10s ease-in-out infinite;
}

@keyframes float {
  0%, 100% { transform: translateY(0) rotate(0deg); }
  50% { transform: translateY(-30px) rotate(180deg); }
}

.search-box-wrapper {
  position: relative;
  z-index: 1;
  text-align: center;
  padding: 44px 44px 32px;
  background: linear-gradient(180deg, rgba(var(--app-surface-rgb) / 0.96), rgba(var(--app-surface-alt-rgb) / 0.92));
  backdrop-filter: blur(18px);
  border-radius: 28px;
  border: 1px solid rgba(var(--app-border-rgb) / 0.78);
  box-shadow: 0 24px 60px rgba(15, 23, 42, 0.18);
  max-width: 680px;
  width: min(100%, 680px);
}

.search-header {
  margin-bottom: 34px;
}

.logo-icon {
  width: 88px;
  height: 88px;
  margin: 0 auto 22px;
  background: linear-gradient(135deg, rgb(var(--primary-color-rgb)), rgb(var(--app-accent-soft-rgb)));
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 42px;
  color: rgb(var(--utility-white-rgb));
  box-shadow: 0 18px 34px rgba(var(--primary-color-rgb) / 0.28);
}

.search-title {
  font-size: 36px;
  font-weight: 700;
  color: rgb(var(--app-text-strong-rgb));
  line-height: 1.1;
  letter-spacing: -0.03em;
  margin: 0 0 12px;
}

.search-subtitle {
  font-size: 15px;
  color: rgb(var(--app-text-muted-rgb));
  line-height: 1.7;
  max-width: 420px;
  margin: 0 auto;
}

.search-input-wrapper {
  margin-bottom: 26px;
}

.search-input-container {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px;
  border-radius: 22px;
  border: 1px solid rgba(var(--app-border-rgb) / 0.72);
  background: rgba(var(--app-bg-rgb) / 0.74);
  box-shadow: inset 0 1px 0 rgba(var(--utility-white-rgb) / 0.3);
}

.search-input {
  flex: 1;
}

.search-input :deep(.el-input__wrapper) {
  min-height: 52px;
  border-radius: 16px;
  background: rgba(var(--app-surface-rgb) / 0.96);
  border: 1px solid rgba(var(--app-border-rgb) / 0.62);
  box-shadow: none;
  padding: 0 16px;
}

.search-input :deep(.el-input__inner) {
  color: rgb(var(--app-text-strong-rgb));
  font-size: 15px;
}

.search-input :deep(.el-input__inner::placeholder) {
  color: rgb(var(--app-text-subtle-rgb));
}

.search-button {
  min-height: 52px;
  padding: 0 28px;
  background: linear-gradient(135deg, rgb(var(--primary-color-rgb)), rgb(var(--app-accent-soft-rgb)));
  border: none;
  font-weight: 600;
  border-radius: 16px;
  box-shadow: 0 16px 28px rgba(var(--primary-color-rgb) / 0.22);
}

.search-button:hover {
  filter: brightness(1.1);
}

.search-features {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.feature-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 18px 14px;
  border-radius: 18px;
  background: rgba(var(--app-surface-rgb) / 0.78);
  border: 1px solid rgba(var(--app-border-rgb) / 0.62);
}

.feature-icon {
  font-size: 24px;
  color: rgb(var(--primary-color-rgb));
}

.feature-text {
  font-size: 14px;
  color: rgb(var(--app-text-muted-rgb));
  font-weight: 500;
}

@media (max-width: 768px) {
  .loading-page {
    padding: 24px 16px;
  }

  .loading-content {
    min-width: auto;
    width: 100%;
    padding: 32px 20px;
    border-radius: 24px;
  }

  .loading-text {
    font-size: 20px;
  }

  .search-page {
    padding: 24px 16px;
  }

  .search-box-wrapper {
    padding: 32px 20px 24px;
    border-radius: 24px;
  }

  .search-title {
    font-size: 30px;
  }

  .search-input-container {
    flex-direction: column;
    align-items: stretch;
  }

  .search-button {
    width: 100%;
  }

  .search-features {
    grid-template-columns: 1fr;
  }
}

.live-page {
  flex: 1;
  display: flex;
  min-height: 0;
  gap: 1px;
  background: rgba(var(--app-border-rgb) / 0.3);
}

.video-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 20px;
  gap: 12px;
  background: rgba(var(--app-bg-rgb) / 1);
}

.video-container {
  position: relative;
  flex: 1;
  background: #000;
  border-radius: 14px;
  overflow: hidden;
  border: 1px solid rgba(var(--app-border-rgb) / 0.4);
  box-shadow: 0 8px 24px rgba(var(--app-shadow-rgb) / 0.1);
}

.video-controls {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 18px;
  background: rgba(var(--app-surface-rgb) / 0.96);
  border-radius: 14px;
  border: 1px solid rgba(var(--app-border-rgb) / 0.5);
  box-shadow: 0 4px 12px rgba(var(--app-shadow-rgb) / 0.06);
}

.control-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  background: rgba(var(--app-surface-alt-rgb) / 0.92);
  border-radius: 10px;
  border: 1px solid rgba(var(--app-border-rgb) / 0.3);
  cursor: pointer;
  transition: all 0.3s ease;
  user-select: none;
}

.control-item:hover {
  background: rgba(var(--primary-color-rgb) / 0.14);
  border-color: rgba(var(--primary-color-rgb) / 0.3);
}

.control-icon {
  font-size: 16px;
  color: rgb(var(--app-text-muted-rgb));
  transition: color 0.3s ease;
}

.control-icon.active {
  color: rgb(var(--primary-color-rgb));
}

.control-text {
  font-size: 12px;
  color: rgb(var(--app-text-muted-rgb));
}

.video-player {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.danmaku-canvas {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.live-status-badge {
  position: absolute;
  top: 16px;
  left: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  background: rgba(0, 0, 0, 0.65);
  backdrop-filter: blur(8px);
  border-radius: 20px;
  color: rgb(var(--app-text-muted-rgb));
  font-size: 12px;
  font-weight: 500;
}

.live-status-badge.is-live {
  background: rgba(255, 68, 68, 0.9);
  color: white;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
}

.is-live .status-dot {
  animation: blink 1s ease-in-out infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.viewer-count {
  position: absolute;
  top: 16px;
  right: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  background: rgba(0, 0, 0, 0.65);
  backdrop-filter: blur(8px);
  border-radius: 20px;
  color: white;
  font-size: 12px;
  font-weight: 500;
}

.sidebar {
  width: 380px;
  background: rgba(var(--app-surface-rgb) / 0.98);
  border-left: 1px solid rgba(var(--app-border-rgb) / 0.7);
  display: flex;
  flex-direction: column;
}

.room-header {
  padding: 22px;
  border-bottom: 1px solid rgba(var(--app-border-rgb) / 0.5);
  position: relative;
}

.anchor-info {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 18px;
  padding-right: 44px;
}

.anchor-avatar {
  flex-shrink: 0;
}

.anchor-details {
  flex: 1;
  min-width: 0;
}

.anchor-name {
  font-size: 16px;
  font-weight: 600;
  color: rgb(var(--app-text-strong-rgb));
  margin: 0 0 6px;
}

.room-title {
  font-size: 13px;
  color: rgb(var(--app-text-muted-rgb));
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.share-icon-button {
  position: absolute;
  top: 22px;
  right: 22px;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(var(--app-surface-alt-rgb) / 0.92);
  border-radius: 50%;
  border: 1px solid rgba(var(--app-border-rgb) / 0.3);
  color: rgb(var(--app-text-muted-rgb));
  font-size: 16px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.share-icon-button:hover {
  background: rgba(var(--primary-color-rgb) / 0.14);
  color: rgb(var(--primary-color-rgb));
  border-color: rgba(var(--primary-color-rgb) / 0.3);
  transform: scale(1.1);
}

.action-buttons {
  display: flex;
  gap: 10px;
}

.danmaku-list {
  flex: 1;
  overflow-y: auto;
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.message-item {
  padding: 12px 14px;
  background: rgba(var(--app-surface-alt-rgb) / 0.92);
  border-radius: 10px;
  border: 1px solid rgba(var(--app-border-rgb) / 0.25);
  font-size: 13px;
  animation: fadeIn 0.3s ease;
  line-height: 1.5;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.message-item.gift {
  background: rgba(255, 107, 107, 0.12);
  border-color: rgba(255, 107, 107, 0.2);
}

.message-item.like {
  background: rgba(255, 179, 71, 0.12);
  border-color: rgba(255, 179, 71, 0.2);
}

.message-item.follow {
  background: rgba(var(--primary-color-rgb) / 0.12);
  border-color: rgba(var(--primary-color-rgb) / 0.2);
}

.message-item.member {
  background: rgba(var(--app-accent-alt-rgb) / 0.12);
  border-color: rgba(var(--app-accent-alt-rgb) / 0.2);
}

.user-name {
  color: rgb(var(--primary-color-rgb));
  font-weight: 600;
}

.message-content {
  color: rgb(var(--app-text-rgb));
  margin-left: 8px;
}

.gift-icon,
.like-icon,
.follow-icon,
.member-icon {
  margin-right: 6px;
  vertical-align: middle;
}

.gift-icon { color: #ff6b6b; }
.like-icon { color: #ffb347; }
.follow-icon { color: rgb(var(--primary-color-rgb)); }
.member-icon { color: rgb(var(--app-accent-alt-rgb)); }

.gift-text,
.like-text,
.follow-text,
.member-text {
  color: rgb(var(--app-text-muted-rgb));
  margin-left: 8px;
}

.stats-text {
  color: #ffd700;
  font-weight: 500;
}

.empty-messages {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: rgb(var(--app-text-subtle-rgb));
  gap: 10px;
}

.empty-messages .el-icon {
  font-size: 36px;
}

.notification-area {
  padding: 10px 18px;
  min-height: 40px;
  background: rgba(var(--app-surface-alt-rgb) / 0.92);
  border-top: 1px solid rgba(var(--app-border-rgb) / 0.5);
  display: flex;
  align-items: center;
  opacity: 0;
  transform: translateY(-10px);
  transition: all 0.3s ease;
}

.notification-area.visible {
  opacity: 1;
  transform: translateY(0);
}

.notification-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 500;
  animation: slideIn 0.3s ease;
}

@keyframes slideIn {
  from { opacity: 0; transform: translateX(-20px); }
  to { opacity: 1; transform: translateX(0); }
}

.notification-item.like { color: #ffb347; }
.notification-item.follow { color: rgb(var(--primary-color-rgb)); }
.notification-item.member { color: rgb(var(--app-accent-alt-rgb)); }

.badge {
  display: inline-block;
  padding: 2px 8px;
  background: linear-gradient(135deg, rgb(var(--primary-color-rgb)), rgb(var(--app-accent-soft-rgb)));
  border-radius: 10px;
  font-size: 10px;
  color: rgb(var(--utility-white-rgb));
  font-weight: 600;
  margin-right: 6px;
}

.message-input-area {
  padding: 14px 18px;
  background: rgba(var(--app-surface-alt-rgb) / 0.92);
  border-top: 1px solid rgba(var(--app-border-rgb) / 0.5);
}

.message-input-area :deep(.el-input__wrapper) {
  background: rgba(var(--app-bg-rgb) / 0.92);
  border: 1px solid rgba(var(--app-border-rgb) / 0.8);
  box-shadow: none;
}

.message-input-area :deep(.el-input__inner) {
  color: rgb(var(--app-text-strong-rgb));
}

.message-input-area :deep(.el-input__inner::placeholder) {
  color: rgb(var(--app-text-subtle-rgb));
}

.connection-status {
  padding: 14px 18px;
  border-top: 1px solid rgba(var(--app-border-rgb) / 0.5);
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: rgb(var(--app-text-muted-rgb));
}

.status-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: rgb(var(--app-text-subtle-rgb));
}

.status-indicator.connected {
  background: rgb(var(--primary-color-rgb));
  animation: pulse 2s ease-in-out infinite;
}
</style>
