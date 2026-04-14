const FAVORITE_STORAGE_KEY = 'oa_notification_favorites'

Page({
  data: {
    activeSection: 'favorites',
    loading: false,
    savingSubscriptions: false,
    notifications: [],
    favoriteItems: [],
    subscribedItems: [],
    availableDepartments: [],
    subscriptionConfigs: {},
    errorText: ''
  },

  onLoad() {
    this.refreshPage()
  },

  onShow() {
    this.refreshPage()
  },

  getAppConfig() {
    const app = getApp()
    return {
      apiBaseUrl: app.globalData.apiBaseUrl,
      userEmail: app.globalData.miniappUserEmail
    }
  },

  getFavoriteIds() {
    try {
      return wx.getStorageSync(FAVORITE_STORAGE_KEY) || []
    } catch (error) {
      return []
    }
  },

  request(path, method, data, callbacks = {}) {
    const { apiBaseUrl } = this.getAppConfig()
    wx.request({
      url: `${apiBaseUrl}${path}`,
      method,
      timeout: 10000,
      header: method === 'POST' ? { 'Content-Type': 'application/json' } : {},
      data,
      success: callbacks.success,
      fail: callbacks.fail
    })
  },

  buildSubscriptionConfigs(notifications, subscribedItems) {
    const departments = []
    const seen = {}

    notifications.forEach((item) => {
      if (item.department && !seen[item.department]) {
        seen[item.department] = true
        departments.push(item.department)
      }
    })

    subscribedItems.forEach((item) => {
      if (item.department && !seen[item.department]) {
        seen[item.department] = true
        departments.push(item.department)
      }
    })

    departments.sort((a, b) => a.localeCompare(b, 'zh-CN'))

    const subscriptionConfigs = {}
    departments.forEach((department) => {
      subscriptionConfigs[department] = {
        subscribed: false
      }
    })

    subscribedItems.forEach((item) => {
      if (!item.department) {
        return
      }
      subscriptionConfigs[item.department] = {
        subscribed: true
      }
    })

    return {
      departments,
      subscriptionConfigs
    }
  },

  refreshPage() {
    const { userEmail } = this.getAppConfig()

    this.setData({
      loading: true,
      errorText: ''
    })

    let notifications = []
    let subscribedItems = []
    let finished = 0
    let requestFailed = false

    const finish = () => {
      finished += 1
      if (finished < 2) {
        return
      }
      const favoriteIds = this.getFavoriteIds()
      const favoriteItems = notifications.filter((item) => favoriteIds.includes(item.newsId))
      const { departments, subscriptionConfigs } = this.buildSubscriptionConfigs(notifications, subscribedItems)

      this.setData({
        loading: false,
        notifications,
        favoriteItems,
        subscribedItems,
        availableDepartments: departments,
        subscriptionConfigs,
        errorText: requestFailed ? '部分数据加载失败，请稍后重试' : ''
      })
    }

    this.request('/api/notifications', 'GET', { limit: 100 }, {
      success: (response) => {
        const payload = response.data || {}
        const result = payload.data || {}
        notifications = Array.isArray(result.items) ? result.items : []
        finish()
      },
      fail: () => {
        requestFailed = true
        notifications = []
        finish()
      }
    })

    this.request('/api/subscriptions/departments', 'GET', { userEmail }, {
      success: (response) => {
        const payload = response.data || {}
        const result = payload.data || {}
        subscribedItems = Array.isArray(result.items) ? result.items : []
        finish()
      },
      fail: () => {
        requestFailed = true
        subscribedItems = []
        finish()
      }
    })
  },

  switchSection(event) {
    const { section } = event.currentTarget.dataset
    if (!section || section === this.data.activeSection) {
      return
    }
    this.setData({
      activeSection: section
    })
  },

  removeFavorite(event) {
    const { newsId } = event.currentTarget.dataset
    const next = this.getFavoriteIds().filter((item) => item !== newsId)
    wx.setStorageSync(FAVORITE_STORAGE_KEY, next)
    this.refreshPage()
    wx.showToast({
      title: '已取消收藏',
      icon: 'none'
    })
  },

  openDetail(event) {
    const { newsId } = event.currentTarget.dataset
    if (!newsId) {
      return
    }
    wx.navigateTo({
      url: `/pages/detail/detail?newsId=${encodeURIComponent(newsId)}`
    })
  },

  toggleSubscribed(event) {
    const { department } = event.currentTarget.dataset
    if (!department) {
      return
    }
    const current = this.data.subscriptionConfigs[department] || {
      subscribed: false
    }
    this.setData({
      subscriptionConfigs: {
        ...this.data.subscriptionConfigs,
        [department]: {
          ...current,
          subscribed: !!event.detail.value
        }
      }
    })
  },

  saveSubscriptions() {
    const { userEmail } = this.getAppConfig()
    const subscriptions = this.data.availableDepartments.map((department) => {
      const config = this.data.subscriptionConfigs[department] || {}
      return {
        department,
        subscribed: !!config.subscribed
      }
    })

    this.setData({
      savingSubscriptions: true
    })

    this.request('/api/subscriptions/batch', 'POST', { userEmail, subscriptions }, {
      success: (response) => {
        const payload = response.data || {}
        this.setData({
          savingSubscriptions: false
        })
        if (payload.code !== 0) {
          wx.showToast({
            title: payload.message || '订阅设置保存失败',
            icon: 'none'
          })
          return
        }
        wx.showToast({
          title: '订阅设置已保存',
          icon: 'none'
        })
        this.refreshPage()
      },
      fail: (error) => {
        console.error('saveSubscriptions failed:', error)
        this.setData({
          savingSubscriptions: false
        })
        wx.showToast({
          title: '订阅设置保存失败',
          icon: 'none'
        })
      }
    })
  }
})
