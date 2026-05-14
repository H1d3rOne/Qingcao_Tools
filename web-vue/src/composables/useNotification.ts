import { ElNotification, ElMessage } from 'element-plus'

type NotificationType = 'success' | 'warning' | 'info' | 'error'

export function useNotification() {
  function notify(
    type: NotificationType,
    title: string,
    message?: string,
    duration = 3000
  ) {
    ElNotification({
      type,
      title,
      message,
      duration
    })
  }

  function success(title: string, message?: string) {
    notify('success', title, message)
  }

  function warning(title: string, message?: string) {
    notify('warning', title, message)
  }

  function info(title: string, message?: string) {
    notify('info', title, message)
  }

  function error(title: string, message?: string) {
    notify('error', title, message, 5000)
  }

  function toast(message: string, type: NotificationType = 'info') {
    ElMessage({
      message,
      type,
      duration: 2000
    })
  }

  return {
    notify,
    success,
    warning,
    info,
    error,
    toast
  }
}
