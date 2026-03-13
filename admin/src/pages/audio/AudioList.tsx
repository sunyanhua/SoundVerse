import { useState, useEffect } from 'react'
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
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { getAudioSegments, type AudioSegment } from '../../services/audioService'
import dayjs from 'dayjs'

const { Title, Paragraph } = Typography
const { Search } = Input
const { Option } = Select
const { RangePicker } = DatePicker

const AudioList = () => {
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<AudioSegment[]>([])
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 20,
    total: 0,
  })
  const [searchForm] = Form.useForm()
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [previewVisible, setPreviewVisible] = useState(false)
  const [previewAudio, setPreviewAudio] = useState<AudioSegment | null>(null)
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
      render: (text) => (
        <div style={{ maxWidth: 300 }}>
          {text || <span style={{ color: '#999' }}>无文本</span>}
        </div>
      ),
    },
    {
      title: '音频源',
      dataIndex: ['source', 'name'],
      key: 'source_name',
      width: 150,
      render: (text, record) => (
        <div>
          <div>{text || '未知'}</div>
          <div style={{ fontSize: 12, color: '#999' }}>
            {record.source?.program_name || ''}
          </div>
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
      width: 150,
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

  const loadData = async (params = {}) => {
    setLoading(true)
    try {
      const result = await getAudioSegments({
        page: pagination.current,
        limit: pagination.pageSize,
        ...params,
      })
      setData(result.data)
      setPagination({
        ...pagination,
        total: result.total,
      })
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
    loadData()
  }

  const handleTableChange = (newPagination: any, filters: any, sorter: any) => {
    setPagination(newPagination)
    const params = {
      ...searchParams,
      page: newPagination.current,
      limit: newPagination.pageSize,
      sort_by: sorter.field,
      sort_order: sorter.order === 'ascend' ? 'asc' : 'desc',
      ...filters,
    }
    loadData(params)
  }

  const handlePreview = (audio: AudioSegment) => {
    setPreviewAudio(audio)
    setPreviewVisible(true)
  }

  const handlePlay = (audio: AudioSegment) => {
    if (audio.oss_url) {
      window.open(audio.oss_url, '_blank')
    } else {
      message.warning('音频链接不可用')
    }
  }

  const handleApprove = async (id: number) => {
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

  useEffect(() => {
    loadData()
  }, [])

  const rowSelection = {
    selectedRowKeys,
    onChange: setSelectedRowKeys,
  }

  const stats = {
    total: pagination.total,
    approved: data.filter(item => item.review_status === 'approved').length,
    pending: data.filter(item => item.review_status === 'pending').length,
    rejected: data.filter(item => item.review_status === 'rejected').length,
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
              <Form.Item name="query">
                <Search
                  placeholder="搜索转录文本或ID"
                  allowClear
                  enterButton={<SearchOutlined />}
                  onSearch={() => searchForm.submit()}
                />
              </Form.Item>
            </Col>
            <Col xs={24} sm={12} md={6}>
              <Form.Item name="review_status">
                <Select placeholder="审核状态" allowClear>
                  <Option value="approved">已通过</Option>
                  <Option value="pending">待审核</Option>
                  <Option value="rejected">已拒绝</Option>
                </Select>
              </Form.Item>
            </Col>
            <Col xs={24} sm={12} md={6}>
              <Form.Item name="source_name">
                <Input placeholder="音频源名称" allowClear />
              </Form.Item>
            </Col>
            <Col xs={24} sm={12} md={6}>
              <Form.Item name="date_range">
                <RangePicker style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col xs={24} style={{ textAlign: 'right' }}>
              <Space>
                <Button onClick={handleReset}>
                  <ReloadOutlined /> 重置
                </Button>
                <Button type="primary" onClick={() => searchForm.submit()}>
                  <SearchOutlined /> 搜索
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
            key="play"
            type="primary"
            onClick={() => previewAudio && handlePlay(previewAudio)}
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
            <p><strong>音频源:</strong> {previewAudio.source?.name || '未知'}</p>
            <p><strong>节目名称:</strong> {previewAudio.source?.program_name || '未知'}</p>
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
    </div>
  )
}

export default AudioList