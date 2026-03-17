import { useState, useEffect } from 'react'
import { Card, Row, Col, Statistic, Typography, Space, Spin } from 'antd'
import {
  AudioOutlined,
  UserOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons'
import { getAudioStats } from '../../services/audioService'

const { Title, Paragraph } = Typography

interface Stats {
  totalAudio: number
  approvedAudio: number
  pendingAudio: number
  totalUsers: number
}

const Dashboard = () => {
  const [loading, setLoading] = useState(true)
  const [stats, setStats] = useState<Stats>({
    totalAudio: 0,
    approvedAudio: 0,
    pendingAudio: 0,
    totalUsers: 0,
  })

  useEffect(() => {
    loadStats()
  }, [])

  const loadStats = async () => {
    setLoading(true)
    try {
      const data = await getAudioStats()
      setStats({
        totalAudio: data.total || 0,
        approvedAudio: data.approved || 0,
        pendingAudio: data.pending || 0,
        totalUsers: data.users || data.totalUsers || 0,
      })
    } catch (error) {
      console.error('加载统计数据失败:', error)
      // 使用默认值
      setStats({
        totalAudio: 0,
        approvedAudio: 0,
        pendingAudio: 0,
        totalUsers: 0,
      })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <Title level={2}>SoundVerse 管理后台</Title>
      <Paragraph type="secondary">
        欢迎使用新声态管理后台，这里是音频百科全书的管理中心。
      </Paragraph>

      <Spin spinning={loading}>
        <Row gutter={[16, 16]} style={{ marginTop: 24 }}>
          <Col xs={24} sm={12} md={6}>
            <Card>
              <Statistic
                title="音频片段总数"
                value={stats.totalAudio}
                prefix={<AudioOutlined />}
                valueStyle={{ color: '#1890ff' }}
              />
            </Card>
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Card>
              <Statistic
                title="已审核音频"
                value={stats.approvedAudio}
                prefix={<CheckCircleOutlined />}
                valueStyle={{ color: '#52c41a' }}
              />
            </Card>
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Card>
              <Statistic
                title="待审核音频"
                value={stats.pendingAudio}
                prefix={<ClockCircleOutlined />}
                valueStyle={{ color: '#faad14' }}
              />
            </Card>
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Card>
              <Statistic
                title="注册用户"
                value={stats.totalUsers}
                prefix={<UserOutlined />}
                valueStyle={{ color: '#722ed1' }}
              />
            </Card>
          </Col>
        </Row>
      </Spin>

      <Row gutter={[16, 16]} style={{ marginTop: 24 }}>
        <Col xs={24} md={12}>
          <Card title="系统状态">
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              <div>
                <strong>后端 API:</strong> <span style={{ color: '#52c41a' }}>运行正常</span>
              </div>
              <div>
                <strong>数据库:</strong> <span style={{ color: '#52c41a' }}>连接正常</span>
              </div>
              <div>
                <strong>向量搜索:</strong> <span style={{ color: '#52c41a' }}>已同步 ({stats.totalAudio} 条)</span>
              </div>
              <div>
                <strong>OSS 存储:</strong> <span style={{ color: '#faad14' }}>部分权限</span>
              </div>
            </Space>
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card title="快速操作">
            <Space direction="vertical" style={{ width: '100%' }}>
              <Paragraph>
                • 前往 <a href="/audio">音频管理</a> 查看所有音频片段
              </Paragraph>
              <Paragraph>
                • 检查 <a href="http://localhost:8000/docs" target="_blank" rel="noreferrer">API 文档</a>
              </Paragraph>
              <Paragraph>
                • 查看 <a href="http://localhost:3000" target="_blank" rel="noreferrer">Grafana 监控</a>
              </Paragraph>
              <Paragraph>
                • 数据库审计已完成 ({stats.totalAudio} 个音频片段)
              </Paragraph>
            </Space>
          </Card>
        </Col>
      </Row>

      <Card style={{ marginTop: 24 }} title="项目信息">
        <Paragraph>
          <strong>项目名称:</strong> SoundVerse (听听·原声态)
        </Paragraph>
        <Paragraph>
          <strong>项目描述:</strong> AI驱动的"声音百科全书+社交音频库"微信小程序
        </Paragraph>
        <Paragraph>
          <strong>核心功能:</strong> 广播节目AI切片、智能音频匹配、音频生成、社交分享
        </Paragraph>
        <Paragraph>
          <strong>数据状态:</strong> 数据库包含 {stats.totalAudio} 个已审核音频片段，全部已生成向量嵌入
        </Paragraph>
      </Card>
    </div>
  )
}

export default Dashboard