const JOBS_PAGE_SIZE = 10

Page({
  data: {
    loading: true,
    saving: false,
    running: false,
    configCollapsed: true,
    jobsLoading: false,
    jobsLoadingMore: false,
    config: {
      schedulerEnabled: false,
      schedulerIntervalMinutes: 0.5,
      schedulerMaxRuns: 3,
      maxRecords: 10,
      requestDelayMin: 0.8,
      requestDelayMax: 1.6
    },
    jobs: [],
    jobsPage: 1,
    jobsPageSize: JOBS_PAGE_SIZE,
    jobsTotalCount: 0,
    jobsHasMore: true,
    runState: {}
  },

  onLoad() {
    this.loadAll()
  },

  onPullDownRefresh() {
    this.loadNextJobsPage(() => wx.stopPullDownRefresh())
  },

  getApiBaseUrl() {
    return getApp().globalData.apiBaseUrl
  },

  request(path, method, data, callbacks = {}) {
    wx.request({
      url: `${this.getApiBaseUrl()}${path}`,
      method,
      timeout: 15000,
      header: method === 'POST' ? { 'Content-Type': 'application/json' } : {},
      data,
      success: callbacks.success,
      fail: callbacks.fail,
      complete: callbacks.complete
    })
  },

  loadAll(done) {
    this.setData({ loading: true })
    let completed = 0
    const finishOnce = () => {
      completed += 1
      if (completed >= 2) {
        this.setData({ loading: false })
        if (typeof done === 'function') {
          done()
        }
      }
    }
    this.loadConfig(finishOnce)
    this.loadJobs({ page: 1, append: false, done: finishOnce })
  },

  loadConfig(done) {
    this.request('/api/admin/crawler/config', 'GET', {}, {
      success: (response) => {
        const payload = response.data || {}
        if (payload.code === 0 && payload.data) {
          this.setData({
            config: payload.data
          })
        }
      },
      fail: (error) => {
        console.error('loadConfig failed:', error)
        wx.showToast({ title: '配置加载失败', icon: 'none' })
      },
      complete: done
    })
  },

  loadJobs({ page = 1, append = false, done } = {}) {
    const loadingKey = append ? 'jobsLoadingMore' : 'jobsLoading'
    this.setData({ [loadingKey]: true })
    this.request(`/api/admin/crawler/jobs?page=${page}&limit=${this.data.jobsPageSize}`, 'GET', {}, {
      success: (response) => {
        const payload = response.data || {}
        if (payload.code !== 0) {
          wx.showToast({ title: payload.message || '任务加载失败', icon: 'none' })
          return
        }
        const result = payload.data || {}
        const nextItems = result.items || []
        this.setData({
          jobs: append ? this.data.jobs.concat(nextItems) : nextItems,
          jobsPage: Number(result.page || page),
          jobsPageSize: Number(result.pageSize || this.data.jobsPageSize),
          jobsTotalCount: Number(result.totalCount || 0),
          jobsHasMore: !!result.hasMore,
          runState: result.runState || {},
          running: !!(result.runState && result.runState.running)
        })
      },
      fail: (error) => {
        console.error('loadJobs failed:', error)
        wx.showToast({ title: '任务加载失败', icon: 'none' })
      },
      complete: () => {
        this.setData({ [loadingKey]: false })
        if (typeof done === 'function') {
          done()
        }
      }
    })
  },

  loadNextJobsPage(done) {
    if (this.data.jobsLoadingMore || this.data.jobsLoading) {
      if (typeof done === 'function') {
        done()
      }
      return
    }
    if (!this.data.jobsHasMore) {
      wx.showToast({ title: '没有更多历史记录', icon: 'none' })
      if (typeof done === 'function') {
        done()
      }
      return
    }
    this.loadJobs({
      page: this.data.jobsPage + 1,
      append: true,
      done
    })
  },

  onJobsScrollToLower() {
    this.loadNextJobsPage()
  },

  toggleConfigPanel() {
    this.setData({
      configCollapsed: !this.data.configCollapsed
    })
  },

  updateConfigField(field, value) {
    this.setData({
      [`config.${field}`]: value
    })
  },

  onSchedulerToggle(event) {
    this.updateConfigField('schedulerEnabled', !!event.detail.value)
  },

  onInputInterval(event) {
    this.updateConfigField('schedulerIntervalMinutes', event.detail.value)
  },

  onInputMaxRuns(event) {
    this.updateConfigField('schedulerMaxRuns', event.detail.value)
  },

  onInputMaxRecords(event) {
    this.updateConfigField('maxRecords', event.detail.value)
  },

  onInputDelayMin(event) {
    this.updateConfigField('requestDelayMin', event.detail.value)
  },

  onInputDelayMax(event) {
    this.updateConfigField('requestDelayMax', event.detail.value)
  },

  saveConfig() {
    if (this.data.saving) {
      return
    }
    const config = this.data.config
    this.setData({ saving: true })
    this.request('/api/admin/crawler/config', 'POST', {
      schedulerEnabled: !!config.schedulerEnabled,
      schedulerIntervalMinutes: Number(config.schedulerIntervalMinutes),
      schedulerMaxRuns: Number(config.schedulerMaxRuns),
      maxRecords: Number(config.maxRecords),
      requestDelayMin: Number(config.requestDelayMin),
      requestDelayMax: Number(config.requestDelayMax)
    }, {
      success: (response) => {
        const payload = response.data || {}
        if (payload.code !== 0) {
          wx.showToast({ title: payload.message || '保存失败', icon: 'none' })
          return
        }
        wx.showToast({ title: '保存成功', icon: 'none' })
        this.loadAll()
      },
      fail: (error) => {
        console.error('saveConfig failed:', error)
        wx.showToast({ title: '保存失败', icon: 'none' })
      },
      complete: () => {
        this.setData({ saving: false })
      }
    })
  },

  runCrawlerNow() {
    if (this.data.running) {
      wx.showToast({ title: '任务已在运行中', icon: 'none' })
      return
    }
    this.setData({ running: true })
    this.request('/api/admin/crawler/run', 'POST', {}, {
      success: (response) => {
        const payload = response.data || {}
        if (payload.code !== 0) {
          this.setData({ running: false })
          wx.showToast({ title: payload.message || '启动失败', icon: 'none' })
          return
        }
        wx.showToast({ title: '已启动抓取任务', icon: 'none' })
        this.loadJobs({ page: 1, append: false })
      },
      fail: (error) => {
        console.error('runCrawlerNow failed:', error)
        this.setData({ running: false })
        wx.showToast({ title: '启动失败', icon: 'none' })
      }
    })
  },

  refreshLogs() {
    this.loadJobs({ page: 1, append: false })
  }
})
