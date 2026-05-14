import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1/quark',
  timeout: 120000,
  headers: {}
})

api.interceptors.request.use(
  config => {
    if (typeof FormData !== 'undefined' && config.data instanceof FormData) {
      if (config.headers) {
        delete (config.headers as any)['Content-Type']
      }
    }
    return config
  },
  error => Promise.reject(error)
)

api.interceptors.response.use(
  response => response.data,
  error => Promise.reject(error)
)

const formatApiDetail = (detail: any): string => {
  if (!detail) return ''
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const messages = detail.map((item: any) => {
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
    })
    return messages.join('; ')
  }
  try {
    return JSON.stringify(detail)
  } catch {
    return String(detail)
  }
}

const uploadBinaryWithAxios = async (
  endpoint: string,
  params: Record<string, string | undefined>,
  file: File,
  onProgress?: (progress: number) => void
): Promise<any> => {
  try {
    // 构建查询参数
    const searchParams = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== '') {
        searchParams.set(key, value)
      }
    })
    const queryString = searchParams.toString()
    const url = queryString ? `${endpoint}?${queryString}` : endpoint

    const response = await api.post(url, file, {
      headers: {
        'Content-Type': 'application/octet-stream'
      },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          onProgress(Math.round((progressEvent.loaded * 100) / progressEvent.total))
        }
      }
    })
    return response
  } catch (error: any) {
    const detail = error.response?.data?.detail
    return {
      success: false,
      message: formatApiDetail(detail) || error.message || '上传失败'
    }
  }
}

export interface LoginRequest {
  method: string
  cookies?: string
}

export interface LoginResponse {
  success: boolean
  message: string
  qrcode_url?: string
  login_token?: string
}

export interface QRCodeResponse {
  success: boolean
  message: string
  qrcode_url?: string
  qrcode_token?: string
  qrcode_image?: string
}

export interface CheckLoginRequest {
  qrcode_token: string
}

export interface CheckLoginResponse {
  success: boolean
  message: string
  is_logged_in: boolean
  login_token?: string
}

export interface AuthStatusResponse {
  is_logged_in: boolean
  user_info?: any
}

export interface LogoutResponse {
  success: boolean
  message: string
}

export interface FileListResponse {
  success: boolean
  data?: any
  message?: string
}

export interface StorageInfoResponse {
  success: boolean
  data?: any
  message?: string
}

export interface ShareResponse {
  success: boolean
  data?: any
  message?: string
}

export const authAPI = {
  getQRCode: (): Promise<QRCodeResponse> => {
    return api.get('/auth/qrcode')
  },
  
  checkLogin: (data: CheckLoginRequest): Promise<CheckLoginResponse> => {
    return api.post('/auth/check-login', data)
  },
  
  login: (data: LoginRequest): Promise<LoginResponse> => {
    return api.post('/auth/login', data)
  },
  
  autoLogin: (): Promise<LoginResponse> => {
    return api.post('/auth/auto-login')
  },
  
  getStatus: (): Promise<AuthStatusResponse> => {
    return api.get('/auth/status')
  },
  
  logout: (): Promise<LogoutResponse> => {
    return api.post('/auth/logout')
  }
}

export const filesAPI = {
  getUserInfo: (): Promise<any> => {
    return api.get('/files/user-info')
  },
  
  listFiles: (folderId: string = '0', page: number = 1, size: number = 200): Promise<FileListResponse> => {
    return api.get('/files/list', {
      params: { folder_id: folderId, page, size }
    })
  },
  
  createFolder: (folderName: string, parentId: string = '0'): Promise<FileListResponse> => {
    return api.post('/files/folder', {
      folder_name: folderName,
      parent_id: parentId
    })
  },
  
  deleteFiles: (fileIds: string[]): Promise<FileListResponse> => {
    return api.delete('/files/delete', {
      data: { file_ids: fileIds }
    })
  },
  
  renameFile: (fileId: string, newName: string): Promise<FileListResponse> => {
    return api.put('/files/rename', {
      file_id: fileId,
      new_name: newName
    })
  },
  
  moveFiles: (fileIds: string[], targetFolderId: string): Promise<FileListResponse> => {
    return api.post('/files/move', {
      file_ids: fileIds,
      target_folder_id: targetFolderId
    })
  },
  
  searchFiles: (keyword: string, page: number = 1, size: number = 50): Promise<FileListResponse> => {
    return api.get('/files/search', {
      params: { keyword, page, size }
    })
  },
  
  getStorageInfo: (): Promise<StorageInfoResponse> => {
    return api.get('/files/storage')
  },
  
  getDownloadUrl: (fileId: string, fileName?: string, savePath?: string): Promise<any> => {
    const params: any = {}
    if (fileName) params.file_name = fileName
    if (savePath) params.save_path = savePath
    return api.get(`/files/download/${fileId}`, { params })
  },
  
  downloadFolder: (folderId: string, folderName?: string, savePath?: string): Promise<any> => {
    const params: any = {}
    if (folderName) params.folder_name = folderName
    if (savePath) params.save_path = savePath
    return api.get(`/files/download-folder/${folderId}`, { params })
  },
  
  getFolderTree: (folderId: string = '0', maxDepth: number = 3): Promise<FileListResponse> => {
    return api.get('/files/tree', {
      params: { folder_id: folderId, max_depth: maxDepth }
    })
  },
  
  createShare: (fileIds: string[], title: string = '', expireDays: number = 0, password?: string): Promise<ShareResponse> => {
    return api.post('/files/share', {
      file_ids: fileIds,
      title,
      expire_days: expireDays,
      password
    })
  },
  
  getMyShares: (page: number = 1, size: number = 50): Promise<ShareResponse> => {
    return api.get('/files/shares', {
      params: { page, size }
    })
  },
  
  deleteShare: (shareId: string): Promise<ShareResponse> => {
    return api.delete(`/files/share/${shareId}`)
  },
  
  // 分享链接相关
  getShareInfo: (shareId: string, passcode?: string, pdirFid?: string, token?: string): Promise<any> => {
    const params: any = { share_id: shareId }
    if (passcode) params.passcode = passcode
    if (pdirFid) params.pdir_fid = pdirFid
    if (token) params.token = token
    return api.get('/files/share-info', { params })
  },
  
  transferShare: (shareId: string, passcode: string | undefined, fileIds: string[], shareFidTokens: string[], targetFolderId: string | undefined, pdirFid: string, token: string): Promise<any> => {
    const data: any = {
      share_id: shareId,
      passcode: passcode || undefined,
      file_ids: fileIds,
      share_fid_tokens: shareFidTokens,
      pdir_fid: pdirFid,
      token: token
    }
    if (targetFolderId) data.target_folder_id = targetFolderId
    return api.post('/files/transfer-share', data)
  },
  
  downloadShare: (shareId: string, passcode: string, fileIds: string[], token?: string, mode?: string, targetFolderId?: string): Promise<any> => {
    const data: any = {
      share_id: shareId,
      passcode,
      file_ids: fileIds
    }
    if (token) data.token = token
    if (mode) data.mode = mode
    if (targetFolderId) data.target_folder_id = targetFolderId
    return api.post('/files/download-share', data)
  },
  
  uploadFile: async (
    file: File,
    parentFolderId?: string,
    onProgress?: (progress: number) => void,
    relativePath?: string
  ): Promise<any> => {
    const nativePath = (file as any).path as string | undefined
    if (nativePath) {
      try {
        if (onProgress) {
          onProgress(5)
        }
        if (import.meta.env.DEV) {
          console.log('[upload-local-path]', {
            localPath: nativePath,
            parentFolderId: parentFolderId || '',
            relativePath: relativePath || '',
            baseURL: api.defaults.baseURL
          })
        }

        const response = await api.post('/files/upload-local', {
          local_path: nativePath,
          parent_folder_id: parentFolderId,
          relative_path: relativePath
        })

        if (onProgress) {
          onProgress(100)
        }

        return response
      } catch (error: any) {
        console.error('本地路径上传失败，回退原始字节流上传:', error)
      }
    }

    // 使用原始字节流上传
    return await uploadBinaryWithAxios(
      '/files/upload-raw',
      {
        file_name: file.name,
        parent_folder_id: parentFolderId,
        relative_path: relativePath
      },
      file,
      onProgress
    )
  }
}
