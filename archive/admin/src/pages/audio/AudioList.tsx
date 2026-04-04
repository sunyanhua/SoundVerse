import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Table,
  Card,
  Input,
  Button,
  Space,
  Tag,
  Typography,
  Row,
  Col,
  Statistic,
  Select,
  DatePicker,
  Form,
  Modal,
  message,
  Popconfirm,
} from 'antd'
import {
  SearchOutlined,
  ReloadOutlined,
  PlayCircleOutlined,
  EyeOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  DeleteOutlined,
  InfoCircleOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { getAudioSegments, getAudioStats, type AudioSegment } from '../../services/audioService'
import dayjs from 'dayjs'

const { Title, Paragraph } = Typography
const { Option } = Select
const { RangePicker } = DatePicker

const AudioList = () => {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<AudioSegment[]>([])
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 20,
    total: 0,
    showSizeChanger: true,
    showQuickJumper: true,
    pageSizeOptions: ['10', '20', '50', '100'],
    showTotal: (total: number, range: [number, number]) => `${range[0]}-${range[1]} 条，共 ${total} 条`,
  })
  const [searchForm] = Form.useForm()
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [previewVisible, setPreviewVisible] = useState(false)
  const [previewAudio, setPreviewAudio] = useState<AudioSegment | null>(null)
  const [playVisible, setPlayVisible] = useState(false)
  const [playingAudio, setPlayingAudio] = useState<AudioSegment | null>(null)
  const [searchParams, setSearchParams] = useState({
    query: '',
    review_status: '',
    source_name: '',
    date_range: null as [dayjs.Dayjs, dayjs.Dayjs] | null,
  })

  const columns: ColumnsType<AudioSegment> = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 80,
      sorter: true,
    },
    {
      title: '转录文本',
      dataIndex: 'transcription',
      key: 'transcription',
      ellipsis: true,
      width: 300,
      render: (text, record) => (
        <div
          style={{ maxWidth: 300, cursor: 'pointer' }}
          onClick={(e) => {
            e.stopPropagation()
            navigate(`/audio/${record.id}`)
          }}
          onMouseEnter={(e) => e.currentTarget.style.textDecoration = 'underline'}
          onMouseLeave={(e) => e.currentTarget.style.textDecoration = 'none'}
        >
          {text || <span style={{ color: '#999' }}>无文本</span>}
        </div>
      ),
    },
    {
      title: '音频源',
      dataIndex: 'source_title',
      key: 'source_title',
      width: 150,
      render: (text) => (
        <div>
          <div>{text || '未知'}</div>
        </div>
      ),
    },
    {
      title: '审核状态',
      dataIndex: 'review_status',
      key: 'review_status',
      width: 120,
      render: (status) => {
        const statusMap = {
          pending: { color: 'orange', text: '待审核', icon: <ClockCircleOutlined /> },
          approved: { color: 'green', text: '已通过', icon: <CheckCircleOutlined /> },
          rejected: { color: 'red', text: '已拒绝', icon: <DeleteOutlined /> },
        }
        const config = statusMap[status as keyof typeof statusMap] || { color: 'default', text: status }
        return (
          <Tag color={config.color} icon={config.icon}>
            {config.text}
          </Tag>
        )
      },
      filters: [
        { text: '待审核', value: 'pending' },
        { text: '已通过', value: 'approved' },
        { text: '已拒绝', value: 'rejected' },
      ],
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (date) => dayjs(date).format('YYYY-MM-DD HH:mm'),
      sorter: true,
    },
    {
      title: '音频时长',
      dataIndex: 'duration',
      key: 'duration',
      width: 100,
      render: (duration) => `${duration || 0}s`,
    },
    {
      title: '操作',
      key: 'action',
      width: 180,
      fixed: 'right',
      render: (_, record) => (
        <Space size="small">
          <Button
            type="text"
            icon={<EyeOutlined />}
            onClick={() => handlePreview(record)}
            title="预览"
          />
          <Button
            type="text"
            icon={<InfoCircleOutlined />}
            onClick={() => navigate(`/audio/${record.id}`)}
            title="详情"
          />
          <Button
            type="text"
            icon={<PlayCircleOutlined />}
            onClick={() => handlePlay(record)}
            title="播放"
          />
          <Popconfirm
            title="确定要通过审核吗？"
            onConfirm={() => handleApprove(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button
              type="text"
              icon={<CheckCircleOutlined />}
              title="通过审核"
              disabled={record.review_status === 'approved'}
            />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  const loadData = async (params: { page?: number; limit?: number; [key: string]: any } = {}) => {
    setLoading(true)
    try {
      // 优先使用 params 中的 page 和 limit，否则使用 pagination 状态
      const page = params.page || pagination.current
      const pageSize = params.limit || pagination.pageSize
      const result = await getAudioSegments({
        page,
        limit: pageSize,
        ...params,
      })
      setData(result.data)
      setPagination(prev => ({
        ...prev,
        current: page,
        pageSize: pageSize,
        total: result.total,
      }))
    } catch (error) {
      message.error('加载数据失败')
      console.error('加载音频数据失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = (values: any) => {
    const searchParams = {
      query: values.query,
      review_status: values.review_status,
      source_name: values.source_name,
      date_range: values.date_range,
    }
    setSearchParams(searchParams)
    const apiParams = {
      query: values.query,
      review_status: values.review_status,
      source_name: values.source_name,
      start_date: values.date_range?.[0]?.format('YYYY-MM-DD'),
      end_date: values.date_range?.[1]?.format('YYYY-MM-DD'),
      page: 1, // 搜索时重置到第一页
    }
    loadData(apiParams)
  }

  const handleReset = () => {
    searchForm.resetFields()
    setSearchParams({
      query: '',
      review_status: '',
      source_name: '',
      date_range: null,
    })
    loadData({ page: 1 }) // 重置时回到第一页
  }

  const handleTableChange = (newPagination: any, filters: any, sorter: any) => {
    // 翻页时只传分页和排序参数，保持搜索条件
    const params: any = {
      page: newPagination.current,
      limit: newPagination.pageSize,
    }

    // 添加排序参数
    if (sorter.field) {
      params.sort_by = sorter.field
      params.sort_order = sorter.order === 'ascend' ? 'asc' : 'desc'
    }

    // 添加筛选参数（如果有）
    if (filters.review_status && filters.review_status.length > 0) {
      params.review_status = filters.review_status[0]
    }

    // 添加搜索参数
    if (searchParams.query) {
      params.query = searchParams.query
    }
    if (searchParams.source_name) {
      params.source_name = searchParams.source_name
    }
    if (searchParams.date_range) {
      params.start_date = searchParams.date_range[0]?.format('YYYY-MM-DD')
      params.end_date = searchParams.date_range[1]?.format('YYYY-MM-DD')
    }

    // 更新分页状态并加载数据
    setPagination(prev => ({ ...prev, current: newPagination.current, pageSize: newPagination.pageSize }))
    loadData(params)
    // 分页后滚动到顶部
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const handlePreview = (audio: AudioSegment) => {
    setPreviewAudio(audio)
    setPreviewVisible(true)
  }

  const handlePlay = (audio: AudioSegment) => {
    if (audio.oss_url) {
      setPlayingAudio(audio)
      setPlayVisible(true)
    } else {
      message.warning('音频链接不可用')
    }
  }

  const handleApprove = async (id: string) => {
    try {
      // TODO: 调用审核API
      console.log(`审核音频片段 ${id}`)
      message.success('审核通过成功')
      loadData()
    } catch (error) {
      message.error('审核操作失败')
    }
  }

  const handleBatchApprove = () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请选择要操作的记录')
      return
    }
    // TODO: 批量审核
    message.success(`批量通过 ${selectedRowKeys.length} 条记录`)
    setSelectedRowKeys([])
    loadData()
  }

  // 统计数据 - 从后端获取全量统计
  const [stats, setStats] = useState({
    total: 0,
    approved: 0,
    pending: 0,
    rejected: 0,
  })

  const loadStats = async () => {
    try {
      const statsData = await getAudioStats()
      setStats({
        total: statsData.total || 0,
        approved: statsData.approved || 0,
        pending: statsData.pending || 0,
        rejected: statsData.rejected || 0,
      })
    } catch (error) {
      console.error('获取统计数据失败:', error)
      // 设置默认值以避免UI显示为0
      setStats({
        total: 0,
        approved: 0,
        pending: 0,
        rejected: 0,
      })
    }
  }

  useEffect(() => {
    // 页面加载时获取数据和统计
    loadData()
    loadStats()
  }, [])

  const rowSelection = {
    selectedRowKeys,
    onChange: setSelectedRowKeys,
  }

  return (
    <div>
      <Title level={2}>音频管理</Title>
      <Paragraph type="secondary">
        管理所有音频片段，支持搜索、筛选、审核和播放。
      </Paragraph>

      <Card style={{ marginBottom: 16 }}>
        <Form
          form={searchForm}
          layout="inline"
          onFinish={handleSearch}
          initialValues={searchParams}
        >
          <Row gutter={[16, 16]} style={{ width: '100%' }}>
            <Col xs={24} md={8}>
              <Form.Item name="query" style={{ width: '100%' }}>
                <Input
                  placeholder="搜索转录文本或ID"
                  allowClear
                  style={{ width: '100%' }}
                />
              </Form.Item>
            </Col>
            <Col xs={24} sm={8} md={4}>
              <Form.Item name="review_status" style={{ width: '100%' }}>
                <Select placeholder="审核状态" allowClear style={{ width: '100%' }}>
                  <Option value="approved">已通过</Option>
                  <Option value="pending">待审核</Option>
                  <Option value="rejected">已拒绝</Option>
                </Select>
              </Form.Item>
            </Col>
            <Col xs={24} sm={8} md={4}>
              <Form.Item name="source_name" style={{ width: '100%' }}>
                <Input placeholder="音频源名称" allowClear style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col xs={24} sm={8} md={4}>
              <Form.Item name="date_range" style={{ width: '100%' }}>
                <RangePicker style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col xs={24} sm={8} md={4} style={{ textAlign: 'right' }}>
              <Space>
                <Button type="primary" htmlType="submit" icon={<SearchOutlined />}>
                  搜索
                </Button>
                <Button onClick={handleReset}>
                  <ReloadOutlined /> 重置
                </Button>
              </Space>
            </Col>
          </Row>
        </Form>
      </Card>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={6}>
          <Card>
            <Statistic
              title="音频总数"
              value={stats.total}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={6}>
          <Card>
            <Statistic
              title="已审核"
              value={stats.approved}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={6}>
          <Card>
            <Statistic
              title="待审核"
              value={stats.pending}
              valueStyle={{ color: '#faad14' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={6}>
          <Card>
            <Statistic
              title="已拒绝"
              value={stats.rejected}
              valueStyle={{ color: '#ff4d4f' }}
            />
          </Card>
        </Col>
      </Row>

      <Card
        title="音频列表"
        extra={
          <Space>
            <span>已选择 {selectedRowKeys.length} 项</span>
            <Button
              type="primary"
              onClick={handleBatchApprove}
              disabled={selectedRowKeys.length === 0}
            >
              <CheckCircleOutlined /> 批量通过
            </Button>
          </Space>
        }
      >
        <Table
          columns={columns}
          dataSource={data}
          rowKey="id"
          loading={loading}
          pagination={pagination}
          onChange={handleTableChange}
          rowSelection={rowSelection}
          scroll={{ x: 1300 }}
        />
      </Card>

      <Modal
        title="音频详情"
        open={previewVisible}
        onCancel={() => setPreviewVisible(false)}
        footer={[
          <Button key="close" onClick={() => setPreviewVisible(false)}>
            关闭
          </Button>,
          <Button
            key="detail"
            onClick={() => {
              if (previewAudio) {
                setPreviewVisible(false)
                navigate(`/audio/${previewAudio.id}`)
              }
            }}
          >
            查看详情
          </Button>,
          <Button
            key="play"
            type="primary"
            onClick={() => {
              if (previewAudio) {
                setPreviewVisible(false)
                handlePlay(previewAudio)
              }
            }}
          >
            <PlayCircleOutlined /> 播放音频
          </Button>,
        ]}
        width={700}
      >
        {previewAudio && (
          <div>
            <p><strong>ID:</strong> {previewAudio.id}</p>
            <p><strong>转录文本:</strong> {previewAudio.transcription}</p>
            <p><strong>音频源:</strong> {previewAudio.source_title || '未知'}</p>
            <p><strong>节目名称:</strong> {previewAudio.source_title || '未知'}</p>
            <p><strong>审核状态:</strong> {previewAudio.review_status}</p>
            <p><strong>创建时间:</strong> {dayjs(previewAudio.created_at).format('YYYY-MM-DD HH:mm:ss')}</p>
            <p><strong>音频时长:</strong> {previewAudio.duration || 0} 秒</p>
            <p><strong>OSS URL:</strong>
              <a href={previewAudio.oss_url} target="_blank" rel="noreferrer" style={{ marginLeft: 8 }}>
                {previewAudio.oss_url ? '访问链接' : '无链接'}
              </a>
            </p>
          </div>
        )}
      </Modal>

      {/* 音频播放弹窗 */}
      <Modal
        title="播放音频"
        open={playVisible}
        onCancel={() => setPlayVisible(false)}
        footer={[
          <Button key="close" onClick={() => setPlayVisible(false)}>
            关闭
          </Button>,
          <Button
            key="detail"
            onClick={() => {
              if (playingAudio) {
                setPlayVisible(false)
                navigate(`/audio/${playingAudio.id}`)
              }
            }}
          >
            查看详情
          </Button>,
        ]}
        width={500}
      >
        {playingAudio && (
          <div style={{ textAlign: 'center' }}>
            <p><strong>音频片段 ID: {playingAudio.id}</strong></p>
            <p style={{ marginBottom: 16 }}>
              {playingAudio.transcription ? (
                <div style={{ maxHeight: 100, overflow: 'auto', textAlign: 'left', padding: 8, background: '#f5f5f5', borderRadius: 4 }}>
                  {playingAudio.transcription}
                </div>
              ) : '无转录文本'}
            </p>
            <audio
              controls
              autoPlay
              style={{ width: '100%', marginBottom: 16 }}
              src={playingAudio.oss_url}
              onError={(e) => {
                message.error('音频加载失败，请检查链接')
                console.error('音频加载失败:', e)
              }}
            >
              您的浏览器不支持音频播放。
            </audio>
            <p><small>音频时长: {playingAudio.duration || 0} 秒</small></p>
            <p>
              <a href={playingAudio.oss_url} target="_blank" rel="noreferrer">
                在新窗口中打开音频
              </a>
            </p>
          </div>
        )}
      </Modal>
    </div>
  )
}

export default AudioList