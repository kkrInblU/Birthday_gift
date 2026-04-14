const READ_STORAGE_KEY = 'oa_notification_read_ids'

Page({
  data: {
    loading: false,
    errorText: '',
    lastSync: '--:--',
    activeView: 'all',
    activeAudience: 'all',
    activeAudienceLabel: '全部人群',
    activeAudienceIndex: 0,
    audienceOptions: [
      { label: '全部人群', value: 'all', path: '/api/notifications' },
      { label: '本科生', value: 'undergraduate', path: '/api/notifications/undergraduate' },
      { label: '研究生', value: 'graduate', path: '/api/notifications/graduate' },
      { label: '教职工', value: 'staff', path: '/api/notifications/staff' }
    ],
    allNotifications: [],
    filteredNotifications: [],
    displayedNotifications: [],
    subscribedDepartments: [],
    totalCount: 0,
    unreadCount: 0,
    pageSize: 10,
    currentLimit: 10
  },

  onLoad() {
    this.refreshPage()
  },

  onShow() {
    if (this.data.allNotifications.length) {
      this.applyFilters()
    } else {
      this.refreshPage()
    }
  },

  onPullDownRefresh() {
    this.refreshPage(true)
  },

  getAppConfig() {
    const app = getApp()
    return {
      apiBaseUrl: app.globalData.apiBaseUrl,
      userEmail: app.globalData.miniappUserEmail
    }
  },

  getReadIds() {
    try {
      return wx.getStorageSync(READ_STORAGE_KEY) || []
    } catch (error) {
      return []
    }
  },

  saveReadId(newsId) {
    if (!newsId) {
      return
    }
    const readIds = this.getReadIds()
    if (readIds.includes(newsId)) {
      return
    }
    wx.setStorageSync(READ_STORAGE_KEY, readIds.concat(newsId))
  },

  request(path, data, callbacks = {}) {
    const { apiBaseUrl } = this.getAppConfig()
    wx.request({
      url: `${apiBaseUrl}${path}`,
      method: 'GET',
      timeout: 10000,
      data,
      success: callbacks.success,
      fail: callbacks.fail,
      complete: callbacks.complete
    })
  },

  refreshPage(fromPullDown = false) {
    if (this.data.loading) {
      if (fromPullDown) {
        wx.stopPullDownRefresh()
      }
      return
    }

    const { userEmail } = this.getAppConfig()

    this.setData({
      loading: true,
      errorText: ''
    })

    let notificationsLoaded = false
    let subscriptionsLoaded = false
    let notificationsResult = []
    let subscriptionsResult = []
    let lastSync = '--:--'
    let requestFailed = false

    const finishIfReady = () => {
      if (!notificationsLoaded || !subscriptionsLoaded || requestFailed) {
        return
      }
      this.setData({
        loading: false,
        lastSync,
        allNotifications: notificationsResult,
        subscribedDepartments: subscriptionsResult,
        currentLimit: this.data.pageSize
      })
      this.applyFilters()
    }

    const audienceOption = this.data.audienceOptions.find((item) => item.value === this.data.activeAudience)
      || this.data.audienceOptions[0]

    this.request(audienceOption.path, { limit: 100 }, {
      success: (response) => {
        const payload = response.data || {}
        const result = payload.data || {}
        const items = Array.isArray(result.items) ? result.items : []
        notificationsResult = items
        lastSync = result.lastSync || '--:--'
        notificationsLoaded = true
        finishIfReady()
      },
      fail: (error) => {
        requestFailed = true
        this.handleLoadFailed(error, fromPullDown)
      },
      complete: () => {
        if (fromPullDown) {
          wx.stopPullDownRefresh()
        }
      }
    })

    this.request('/api/subscriptions/departments', { userEmail }, {
      success: (response) => {
        const payload = response.data || {}
        const result = payload.data || {}
        subscriptionsResult = Array.isArray(result.departments) ? result.departments : []
        subscriptionsLoaded = true
        finishIfReady()
      },
      fail: () => {
        subscriptionsResult = []
        subscriptionsLoaded = true
        finishIfReady()
      }
    })
  },

  handleLoadFailed(error, fromPullDown) {
    const errorMessage = (error && error.errMsg) || '通知列表加载失败'
    this.setData({
      loading: false,
      errorText: errorMessage,
      allNotifications: [],
      filteredNotifications: [],
      displayedNotifications: [],
      totalCount: 0,
      unreadCount: 0
    })
    if (fromPullDown) {
      wx.stopPullDownRefresh()
    }
    wx.showToast({
      title: '加载失败',
      icon: 'none'
    })
  },

  applyFilters() {
    const readIds = this.getReadIds()
    const { allNotifications, activeView, subscribedDepartments, currentLimit } = this.data
    const source = allNotifications.map((item) => ({
      ...item,
      unread: !readIds.includes(item.newsId)
    }))

    const filteredNotifications = activeView === 'subscribed'
      ? source.filter((item) => subscribedDepartments.includes(item.department))
      : source

    const displayedNotifications = filteredNotifications.slice(0, currentLimit)

    this.setData({
      filteredNotifications,
      displayedNotifications,
      totalCount: filteredNotifications.length,
      unreadCount: filteredNotifications.filter((item) => item.unread).length
    })
  },

  switchView(event) {
    const { view } = event.currentTarget.dataset
    if (!view || view === this.data.activeView) {
      return
    }
    this.setData({
      activeView: view,
      currentLimit: this.data.pageSize
    })
    this.applyFilters()
  },

  changeAudience(event) {
    const index = Number(event.detail.value)
    const option = this.data.audienceOptions[index]
    if (!option || option.value === this.data.activeAudience) {
      return
    }
    this.setData({
      activeAudience: option.value,
      activeAudienceLabel: option.label,
      activeAudienceIndex: index,
      currentLimit: this.data.pageSize
    })
    this.refreshPage()
  },

  openSearch() {
    wx.navigateTo({
      url: '/pages/search/index'
    })
  },

  loadMore() {
    const { currentLimit, pageSize, filteredNotifications, loading } = this.data
    if (loading || currentLimit >= filteredNotifications.length) {
      return
    }
    this.setData({
      currentLimit: currentLimit + pageSize
    })
    this.applyFilters()
  },

  openDetail(event) {
    const { newsId } = event.currentTarget.dataset
    if (!newsId) {
      wx.showToast({
        title: '缺少通知编号',
        icon: 'none'
      })
      return
    }

    this.saveReadId(newsId)
    this.applyFilters()

    wx.navigateTo({
      url: `/pages/detail/detail?newsId=${encodeURIComponent(newsId)}`
    })
  }
})
