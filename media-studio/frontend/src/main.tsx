import React from 'react'
import ReactDOM from 'react-dom/client'
import { App as AntApp, ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import App from './App'
import { setMessageInstance } from './message'

// 桥接 antd App 组件的 message 实例（静态 message 无法消费主题上下文）
function MessageBridge({ children }: { children: React.ReactNode }) {
  const { message } = AntApp.useApp()
  setMessageInstance(message)
  return <>{children}</>
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider locale={zhCN} theme={{ token: { colorPrimary: '#0a7d3e' } }}>
      <AntApp>
        <MessageBridge>
          <App />
        </MessageBridge>
      </AntApp>
    </ConfigProvider>
  </React.StrictMode>
)
