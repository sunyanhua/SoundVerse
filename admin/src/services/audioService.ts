import axios from 'axios'

// API基础URL
const API_BASE_URL = 'http://localhost:8000/api/v1'

// 创建axios实例
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 类型定义
export interface AudioSource {
  id: number
  name: string
  program_name?: string
  broadcast_date?: string
  created_at: string
  updated_at: string
}

export interface AudioSegment {
  id: number
  source_id: number
  transcription: string
  oss_url: string
  oss_key: string
  duration: number
  start_time: number
  end_time: number
  review_status: 'pending' | 'approved' | 'rejected'
  embedding?: number[]
  created_at: string
  updated_at: string
  source?: AudioSource
}

export interface PaginatedResponse<T> {
  data: T[]
  total: number
  page: number
  limit: number
  total_pages: number
}

export interface SearchParams {
  query?: string
  page?: number
  limit?: number
  review_status?: string
  source_name?: string
  start_date?: string
  end_date?: string
  sort_by?: string
  sort_order?: 'asc' | 'desc'
}

// 模拟数据（用于开发）
const mockAudioSegments: AudioSegment[] = Array.from({ length: 50 }, (_, i) => ({
  id: i + 1,
  source_id: Math.floor(i / 10) + 1,
  transcription: `音频片段 ${i + 1} 的转录文本，这是测试数据用于展示音频管理功能。`,
  oss_url: `https://example.com/audio/segment_${i}.mp3`,
  oss_key: `audio/segment_${i}.mp3`,
  duration: Math.floor(Math.random() * 30) + 5,
  start_time: Math.floor(Math.random() * 1000),
  end_time: Math.floor(Math.random() * 1000) + 1000,
  review_status: i % 3 === 0 ? 'pending' : i % 3 === 1 ? 'approved' : 'rejected',
  created_at: new Date(Date.now() - Math.floor(Math.random() * 30) * 24 * 60 * 60 * 1000).toISOString(),
  updated_at: new Date(Date.now() - Math.floor(Math.random() * 7) * 24 * 60 * 60 * 1000).toISOString(),
  source: {
    id: Math.floor(i / 10) + 1,
    name: `音频源 ${Math.floor(i / 10) + 1}`,
    program_name: ['一路畅通', '行走天下', '北京新闻'][Math.floor(Math.random() * 3)],
    broadcast_date: new Date(Date.now() - Math.floor(Math.random() * 30) * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    created_at: new Date(Date.now() - Math.floor(Math.random() * 60) * 24 * 60 * 60 * 1000).toISOString(),
    updated_at: new Date(Date.now() - Math.floor(Math.random() * 30) * 24 * 60 * 60 * 1000).toISOString(),
  },
}))

// 音频服务
export const audioService = {
  // 获取音频片段列表
  async getSegments(params: SearchParams = {}): Promise<PaginatedResponse<AudioSegment>> {
    const {
      page = 1,
      limit = 20,
      query = '',
      review_status = '',
      source_name = '',
      start_date = '',
      end_date = '',
    } = params

    try {
      // 实际API调用
      const response = await api.get('/audio/segments', {
        params: {
          page,
          limit,
          query,
          review_status,
          source_name,
          start_date,
          end_date,
        },
      })
      return response.data
    } catch (error) {
      console.error('获取音频片段失败，使用模拟数据:', error)

      // 模拟筛选
      let filteredData = [...mockAudioSegments]

      if (query) {
        filteredData = filteredData.filter(item =>
          item.transcription.toLowerCase().includes(query.toLowerCase()) ||
          item.id.toString().includes(query)
        )
      }

      if (review_status) {
        filteredData = filteredData.filter(item => item.review_status === review_status)
      }

      if (source_name) {
        filteredData = filteredData.filter(item =>
          item.source?.name?.toLowerCase().includes(source_name.toLowerCase()) ||
          item.source?.program_name?.toLowerCase().includes(source_name.toLowerCase())
        )
      }

      // 模拟分页
      const start = (page - 1) * limit
      const end = start + limit
      const paginatedData = filteredData.slice(start, end)

      return {
        data: paginatedData,
        total: filteredData.length,
        page,
        limit,
        total_pages: Math.ceil(filteredData.length / limit),
      }
    }
  },

  // 搜索音频
  async searchSegments(query: string, limit: number = 10): Promise<AudioSegment[]> {
    try {
      const response = await api.get('/audio/search', {
        params: { query, limit },
      })
      return response.data
    } catch (error) {
      console.error('搜索音频失败，使用模拟数据:', error)

      // 模拟搜索
      return mockAudioSegments
        .filter(item => item.transcription.toLowerCase().includes(query.toLowerCase()))
        .slice(0, limit)
    }
  },

  // 获取单个音频片段
  async getSegment(id: number): Promise<AudioSegment> {
    try {
      const response = await api.get(`/audio/segments/${id}`)
      return response.data
    } catch (error) {
      console.error(`获取音频片段 ${id} 失败，使用模拟数据:`, error)

      // 返回模拟数据
      const segment = mockAudioSegments.find(item => item.id === id)
      if (segment) return segment
      throw new Error(`音频片段 ${id} 不存在`)
    }
  },

  // 更新音频片段审核状态
  async updateReviewStatus(id: number, status: 'pending' | 'approved' | 'rejected'): Promise<void> {
    try {
      await api.patch(`/audio/segments/${id}/review`, { status })
    } catch (error) {
      console.error(`更新审核状态失败:`, error)
      // 模拟成功
      console.log(`模拟更新音频片段 ${id} 审核状态为 ${status}`)
    }
  },

  // 批量更新审核状态
  async batchUpdateReviewStatus(ids: number[], status: 'pending' | 'approved' | 'rejected'): Promise<void> {
    try {
      await api.post('/audio/segments/batch-review', { ids, status })
    } catch (error) {
      console.error(`批量更新审核状态失败:`, error)
      // 模拟成功
      console.log(`模拟批量更新音频片段 ${ids.join(',')} 审核状态为 ${status}`)
    }
  },

  // 获取统计信息
  async getStats() {
    try {
      const response = await api.get('/audio/stats')
      return response.data
    } catch (error) {
      console.error('获取统计信息失败:', error)

      // 模拟统计
      const total = mockAudioSegments.length
      const approved = mockAudioSegments.filter(item => item.review_status === 'approved').length
      const pending = mockAudioSegments.filter(item => item.review_status === 'pending').length
      const rejected = mockAudioSegments.filter(item => item.review_status === 'rejected').length

      return {
        total,
        approved,
        pending,
        rejected,
        sources: Array.from(new Set(mockAudioSegments.map(item => item.source?.program_name))).filter(Boolean).length,
      }
    }
  },
}

// 导出常用函数
export const getAudioSegments = audioService.getSegments
export const searchAudio = audioService.searchSegments
export const getAudioSegment = audioService.getSegment
export const updateAudioReviewStatus = audioService.updateReviewStatus
export const batchUpdateAudioReviewStatus = audioService.batchUpdateReviewStatus
export const getAudioStats = audioService.getStats

export default audioService