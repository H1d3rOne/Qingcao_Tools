import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse, InternalAxiosRequestConfig } from 'axios'
import { ElMessage, ElNotification } from 'element-plus'

// 创建实例
const service: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json'
  }
})

const formatApiDetail = (detail: any): string => {
  if (!detail) return ''
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((item: any) => {
      if (typeof item === 'string') return item
      if (item?.msg) {
        const field = Array.isArray(item.loc) ? item.loc.join('.') : ''
        return field ? `${field}: ${item.msg}` : item.msg
      }
      try {
        return JSON.stringify(item)
      } catch {
        return String(item)
      }
    }).join('; ')
  }
  try {
    return JSON.stringify(detail)
  } catch {
    return String(detail)
  }
}

// 请求拦截器
service.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    return config
  },
  (error) => {
    console.error('请求错误:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器
service.interceptors.response.use(
  (response: AxiosResponse) => {
    const { data } = response
    
    // 如果返回的是文件流，直接返回
    if (response.config.responseType === 'blob') {
      return response
    }
    
    // 后端返回格式: { success: true/false, data: ..., error: ... }
    // 成功时直接返回整个响应数据，让调用方自行处理
    if (data.success === true) {
      return data  // 返回 { success: true, data: ... }
    }
    
    // 业务错误：优先展示后端返回的 detail/error/message，避免把 Cookie 缺失等
    // 明确提示吞成通用“请求失败”。
    const errorMsg = formatApiDetail(data.detail || data.error || data.message) || '请求失败'
    ElMessage.error(errorMsg)
    return Promise.reject(new Error(errorMsg))
  },
  (error) => {
    // HTTP 错误处理
    let message = '网络错误'
    
    if (error.response) {
      const responseData = error.response.data || {}
      const apiMessage = formatApiDetail(
        responseData.detail || responseData.error || responseData.message
      )

      if (apiMessage) {
        message = apiMessage
      } else {
        switch (error.response.status) {
          case 400:
            message = '请求参数错误'
            break
          case 401:
            message = '未授权，请重新登录'
            break
          case 403:
            message = '拒绝访问'
            break
          case 404:
            message = '请求资源不存在'
            break
          case 500:
            message = '服务器内部错误'
            break
          case 502:
            message = '网关错误'
            break
          case 503:
            message = '服务不可用'
            break
          default:
            message = `请求失败: ${error.response.status}`
        }
      }
    } else if (error.code === 'ECONNABORTED') {
      message = '请求超时'
    }
    
    ElNotification.error({
      title: '错误',
      message
    })

    error.message = message
    return Promise.reject(error)
  }
)

// 封装请求方法
export const request = {
  get<T = any>(url: string, params?: any, config?: AxiosRequestConfig): Promise<T> {
    return service.get(url, { params, ...config })
  },
  
  post<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return service.post(url, data, config)
  },
  
  put<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return service.put(url, data, config)
  },

  patch<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    return service.patch(url, data, config)
  },

  delete<T = any>(url: string, params?: any, config?: AxiosRequestConfig): Promise<T> {
    return service.delete(url, { params, ...config })
  },
  
  download(url: string, params?: any, filename?: string): Promise<void> {
    return service.get(url, {
      params,
      responseType: 'blob'
    }).then((response: any) => {
      const blob = new Blob([response.data])
      const link = document.createElement('a')
      link.href = URL.createObjectURL(blob)
      link.download = filename || 'download'
      link.click()
      URL.revokeObjectURL(link.href)
    })
  }
}

export default service
