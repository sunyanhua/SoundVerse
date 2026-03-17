import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import Layout from './components/Layout'
import AudioList from './pages/audio/AudioList'
import AudioDetail from './pages/audio/AudioDetail'
import Dashboard from './pages/dashboard/Dashboard'
import './App.css'

function App() {
  return (
    <ConfigProvider locale={zhCN}>
      <Router>
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/audio" element={<AudioList />} />
            <Route path="/audio/:id" element={<AudioDetail />} />
            {/* 更多路由可以后续添加 */}
          </Routes>
        </Layout>
      </Router>
    </ConfigProvider>
  )
}

export default App
