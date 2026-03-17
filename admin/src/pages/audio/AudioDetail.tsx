import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Card,
  Descriptions,
  Tag,
  Button,
  Space,
  Typography,
  Spin,
  message,
  Row,
  Col,
  Divider,
  Statistic,
} from 'antd'
import {
  PlayCircleOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  EditOutlined,
  ArrowLeftOutlined,
  EyeOutlined,
  DownloadOutlined,
  ShareAltOutlined,
} from '@ant-design/icons'
import { getAudioSegment, updateAudioReviewStatus, type AudioSegment } from '../../services/audioService'
import dayjs from 'dayjs'

const { Title, Paragraph, Text } = Typography

const AudioDetail = () => {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [audio, setAudio] = useState<AudioSegment | null>(null)
  const [audioError, setAudioError] = useState<string | null>(null)

  // 加载音频详情
  const loadAudioDetail = async () => {
    if (!id) return
    setLoading(true)
    try {
      const data = await getAudioSegment(id)
      setAudio(data)
      setAudioError(null)
    } catch (error: any) {
      console.error('加载音频详情失败:', error)
      setAudioError(error.message || '加载音频详情失败')
      message.error('加载音频详情失败')
    } finally {
      setLoading(false)
    }
  }

  // 处理审核操作
  const handleReview = async (status: 'approved' | 'rejected') => {
    if (!id || !audio) return
    try {
      await updateAudioReviewStatus(id, status)
      message.success(`已${status === 'approved' ? '通过' : '拒绝'}审核`)
      // 重新加载数据
      loadAudioDetail()
    } catch (error) {
      console.error('审核操作失败:', error)
      message.error('审核操作失败')
    }
  }

  // 播放音频
  const handlePlay = () => {
    if (audio?.oss_url) {
      window.open(audio.oss_url, '_blank')
    } else {
      message.warning('音频链接不可用')
    }
  }

  // 下载音频
  const handleDownload = () => {
    if (audio?.oss_url) {
      const link = document.createElement('a')
      link.href = audio.oss_url
      link.download = `audio_${audio.id}.mp3`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
    } else {
      message.warning('音频链接不可用')
    }
  }

  // 复制分享链接
  const handleShare = () => {
    const url = window.location.href
    navigator.clipboard.writeText(url)
      .then(() => message.success('链接已复制到剪贴板'))
      .catch(() => message.error('复制失败'))
  }

  useEffect(() => {
    loadAudioDetail()
  }, [id])

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '100px' }}>
        <Spin size="large" />
        <p style={{ marginTop: 16 }}>加载音频详情中...</p>
      </div>
    )
  }

  if (audioError || !audio) {
    return (
      <div style={{ textAlign: 'center', padding: '100px' }}>
        <Title level={3}>加载失败</Title>
        <Paragraph type="secondary">{audioError || '音频不存在'}</Paragraph>
        <Button type="primary" onClick={() => navigate('/audio')}>
          返回音频列表
        </Button>
      </div>
    )
  }

  return (
    <div>
      {/* 页面标题和操作 */}
      <Row justify="space-between" align="middle" style={{ marginBottom: 24 }}>
        <Col>
          <Space>
            <Button
              type="text"
              icon={<ArrowLeftOutlined />}
              onClick={() => navigate('/audio')}
            >
              返回列表
            </Button>
            <Title level={2} style={{ margin: 0 }}>音频详情</Title>
            <Text type="secondary">ID: {audio.id}</Text>
          </Space>
        </Col>
        <Col>
          <Space>
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={handlePlay}
              disabled={!audio.oss_url}
            >
              播放音频
            </Button>
            <Button
              icon={<DownloadOutlined />}
              onClick={handleDownload}
              disabled={!audio.oss_url}
            >
              下载
            </Button>
            <Button
              icon={<ShareAltOutlined />}
              onClick={handleShare}
            >
              分享
            </Button>
          </Space>
        </Col>
      </Row>

      {/* 基本信息卡片 */}
      <Card title="基本信息" style={{ marginBottom: 24 }}>
        <Descriptions column={2} bordered>
          <Descriptions.Item label="ID">{audio.id}</Descriptions.Item>
          <Descriptions.Item label="音频源">
            {audio.source_title || '未知'}
            {audio.source?.program_name && (
              <div><small>节目: {audio.source.program_name}</small></div>
            )}
          </Descriptions.Item>
          <Descriptions.Item label="审核状态">
            <Tag
              color={
                audio.review_status === 'approved' ? 'green' :
                audio.review_status === 'rejected' ? 'red' : 'orange'
              }
            >
              {audio.review_status === 'approved' ? '已通过' :
               audio.review_status === 'rejected' ? '已拒绝' : '待审核'}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="创建时间">
            {dayjs(audio.created_at).format('YYYY-MM-DD HH:mm:ss')}
          </Descriptions.Item>
          <Descriptions.Item label="更新时间">
            {dayjs(audio.updated_at).format('YYYY-MM-DD HH:mm:ss')}
          </Descriptions.Item>
          <Descriptions.Item label="音频时长">
            {audio.duration || 0} 秒
          </Descriptions.Item>
          <Descriptions.Item label="开始时间" span={2}>
            {audio.start_time || 0} 秒
          </Descriptions.Item>
          <Descriptions.Item label="结束时间" span={2}>
            {audio.end_time || 0} 秒
          </Descriptions.Item>
          <Descriptions.Item label="OSS URL" span={2}>
            {audio.oss_url ? (
              <a href={audio.oss_url} target="_blank" rel="noreferrer">
                {audio.oss_url}
              </a>
            ) : '无链接'}
          </Descriptions.Item>
          <Descriptions.Item label="OSS Key" span={2}>
            {audio.oss_key || '无'}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {/* 转录文本卡片 */}
      <Card title="转录文本" style={{ marginBottom: 24 }}>
        <div style={{
          padding: 16,
          background: '#f5f5f5',
          borderRadius: 4,
          maxHeight: 300,
          overflow: 'auto',
          whiteSpace: 'pre-wrap',
          lineHeight: 1.6,
        }}>
          {audio.transcription || <Text type="secondary">无转录文本</Text>}
        </div>
      </Card>

      {/* 元数据卡片 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} md={12}>
          <Card title="音频元数据">
            <Descriptions column={1}>
              <Descriptions.Item label="语言">
                {audio.language || '未设置'}
              </Descriptions.Item>
              <Descriptions.Item label="说话人">
                {audio.speaker || '未设置'}
              </Descriptions.Item>
              <Descriptions.Item label="情感">
                {audio.emotion || '未设置'}
              </Descriptions.Item>
              <Descriptions.Item label="情感得分">
                {audio.sentiment_score !== null ? audio.sentiment_score.toFixed(2) : '未设置'}
              </Descriptions.Item>
              <Descriptions.Item label="关键词">
                {audio.keywords?.join(', ') || '无'}
              </Descriptions.Item>
            </Descriptions>
          </Card>
        </Col>
        <Col xs={24} md={12}>
          <Card title="统计信息">
            <Row gutter={[16, 16]}>
              <Col xs={12}>
                <Statistic
                  title="播放次数"
                  value={audio.play_count || 0}
                  valueStyle={{ color: '#1890ff' }}
                />
              </Col>
              <Col xs={12}>
                <Statistic
                  title="收藏次数"
                  value={audio.favorite_count || 0}
                  valueStyle={{ color: '#52c41a' }}
                />
              </Col>
              <Col xs={12}>
                <Statistic
                  title="分享次数"
                  value={audio.share_count || 0}
                  valueStyle={{ color: '#722ed1' }}
                />
              </Col>
              <Col xs={12}>
                <Statistic
                  title="审核人"
                  value={audio.reviewer_id ? '已审核' : '未审核'}
                />
              </Col>
            </Row>
          </Card>
        </Col>
      </Row>

      {/* 操作卡片 */}
      <Card title="操作">
        <Space size="large">
          <Button
            type="primary"
            icon={<CheckCircleOutlined />}
            onClick={() => handleReview('approved')}
            disabled={audio.review_status === 'approved'}
          >
            通过审核
          </Button>
          <Button
            danger
            icon={<CloseCircleOutlined />}
            onClick={() => handleReview('rejected')}
            disabled={audio.review_status === 'rejected'}
          >
            拒绝审核
          </Button>
          <Button
            icon={<EditOutlined />}
            onClick={() => message.info('编辑功能开发中')}
          >
            编辑信息
          </Button>
          <Button
            icon={<EyeOutlined />}
            onClick={() => navigate(`/audio?preview=${audio.id}`)}
          >
            在列表中预览
          </Button>
        </Space>
        <Divider />
        <Paragraph type="secondary">
          提示：审核操作将立即生效。通过审核后音频将在小程序中可见。
        </Paragraph>
      </Card>

      {/* 内嵌音频播放器 */}
      {audio.oss_url && (
        <Card title="音频播放器" style={{ marginTop: 24 }}>
          <div style={{ textAlign: 'center' }}>
            <audio
              controls
              style={{ width: '100%', maxWidth: 600, margin: '0 auto' }}
              src={audio.oss_url}
              onError={(e) => {
                message.error('音频加载失败，请检查链接')
                console.error('音频加载失败:', e)
              }}
            >
              您的浏览器不支持音频播放。
            </audio>
            <p style={{ marginTop: 8, color: '#666' }}>
              支持格式: MP3, WAV, OGG 等
            </p>
          </div>
        </Card>
      )}
    </div>
  )
}

export default AudioDetail