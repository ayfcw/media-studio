// antd v5 静态 message 无法消费主题上下文（控制台警告）。
// 这里桥接 App.useApp() 的 message 实例，调用方照常 import { message } from './message'
import type { MessageInstance } from 'antd/es/message/interface'

let inst: MessageInstance | null = null

export function setMessageInstance(m: MessageInstance) {
  inst = m
}

export const message = {
  success: (content: string) => inst?.success(content),
  error: (content: string) => inst?.error(content),
  warning: (content: string) => inst?.warning(content),
  info: (content: string) => inst?.info(content),
}
