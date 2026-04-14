const FAVORITE_STORAGE_KEY = 'oa_notification_favorites'
const SUBSCRIBE_STORAGE_KEY = 'oa_notification_subscribe_templates'

Page({
  data: {
    loading: true,
    errorText: '',
    newsId: '',
    notification: null,
    isFavorite: false,
    departmentSubscribed: false,
    savingDepartmentSubscription: false
  },

  onLoad(options) {
    console.log('detail onLoad options:', options || {})
    const newsId = decodeURIComponent((options && options.newsId) || '')
    console.log('detail onLoad newsId:', newsId)
    if (!newsId) {
      this.setData({
        loading: false,
        errorText: '缺少通知编号'
      })
      return
    }

    this.setData({ newsId })
    this.loadDetail(newsId)
  },

  getAppConfig() {
    const app = getApp()
    return {
      apiBaseUrl: app.globalData.apiBaseUrl,
      userEmail: app.globalData.miniappUserEmail,
      templateIds: app.globalData.subscribeTemplateIds || []
    }
  },

  apiRequest(path, method, data, callbacks = {}) {
    const { apiBaseUrl } = this.getAppConfig()
    wx.request({
      url: `${apiBaseUrl}${path}`,
      method,
      timeout: 10000,
      header: method === 'POST' ? { 'Content-Type': 'application/json' } : {},
      data,
      success: callbacks.success,
      fail: callbacks.fail,
      complete: callbacks.complete
    })
  },

  loadDetail(newsId) {
    this.setData({
      loading: true,
      errorText: ''
    })

    this.apiRequest('/api/notification-detail', 'GET', { newsId }, {
      success: (response) => {
        const payload = response.data || {}
        const result = payload.data
        if (!result) {
          this.setData({
            loading: false,
            errorText: '未找到通知详情'
          })
          return
        }

        this.setData({
          loading: false,
          notification: result,
          isFavorite: this.checkFavorite(newsId)
        })
        this.checkDepartmentSubscription(result.department)
      },
      fail: (error) => {
        const errorMessage = (error && error.errMsg) || '通知详情加载失败'
        this.setData({
          loading: false,
          errorText: errorMessage
        })
      }
    })
  },

  getFavoriteList() {
    try {
      return wx.getStorageSync(FAVORITE_STORAGE_KEY) || []
    } catch (error) {
      return []
    }
  },

  checkFavorite(newsId) {
    return this.getFavoriteList().includes(newsId)
  },

  toggleFavorite() {
    const { newsId, isFavorite } = this.data
    const favorites = this.getFavoriteList()
    let nextFavorites = favorites

    if (isFavorite) {
      nextFavorites = favorites.filter((item) => item !== newsId)
    } else if (!favorites.includes(newsId)) {
      nextFavorites = favorites.concat(newsId)
    }

    wx.setStorageSync(FAVORITE_STORAGE_KEY, nextFavorites)
    this.setData({
      isFavorite: !isFavorite
    })

    wx.showToast({
      title: !isFavorite ? '已收藏' : '已取消收藏',
      icon: 'none'
    })
  },

  getSubscribeStatusMap() {
    try {
      return wx.getStorageSync(SUBSCRIBE_STORAGE_KEY) || {}
    } catch (error) {
      return {}
    }
  },

  updateSubscribeStatus(resultMap) {
    const current = this.getSubscribeStatusMap()
    wx.setStorageSync(SUBSCRIBE_STORAGE_KEY, {
      ...current,
      ...resultMap
    })
  },

  syncMiniappSession(onSuccess) {
    const { userEmail } = this.getAppConfig()
    if (!userEmail) {
      if (typeof onSuccess === 'function') {
        onSuccess()
      }
      return
    }

    wx.login({
      timeout: 10000,
      success: (loginResult) => {
        const code = (loginResult && loginResult.code) || ''
        if (!code) {
          if (typeof onSuccess === 'function') {
            onSuccess()
          }
          return
        }

        this.apiRequest('/api/miniapp/session', 'POST', { userEmail, code }, {
          success: () => {
            if (typeof onSuccess === 'function') {
              onSuccess()
            }
          },
          fail: () => {
            if (typeof onSuccess === 'function') {
              onSuccess()
            }
          }
        })
      },
      fail: () => {
        if (typeof onSuccess === 'function') {
          onSuccess()
        }
      }
    })
  },

  checkDepartmentSubscription(department) {
    const { userEmail } = this.getAppConfig()
    if (!userEmail || !department) {
      this.setData({ departmentSubscribed: false })
      return
    }

    this.apiRequest('/api/subscriptions/departments', 'GET', { userEmail }, {
      success: (response) => {
        const payload = response.data || {}
        const result = payload.data || {}
        const departments = Array.isArray(result.departments) ? result.departments : []
        this.setData({
          departmentSubscribed: departments.includes(department)
        })
      },
      fail: () => {
        this.setData({ departmentSubscribed: false })
      }
    })
  },

  subscribeCurrentDepartment() {
    const notification = this.data.notification || {}
    const department = notification.department || ''
    if (!department) {
      wx.showToast({
        title: '当前通知缺少发布单位',
        icon: 'none'
      })
      return
    }
    if (this.data.departmentSubscribed) {
      return
    }

    wx.showModal({
      title: '订阅发布单位',
      content: '是否订阅并接受消息通知？\n是：通知渠道增加小程序\n否：通知渠道不增加小程序',
      confirmText: '是',
      cancelText: '否',
      success: (result) => {
        if (result.confirm) {
          this.subscribeDepartmentWithMiniapp(department)
          return
        }
        if (result.cancel) {
          this.saveDepartmentSubscription(department, '订阅成功')
        }
      }
    })
  },

  subscribeDepartmentWithMiniapp(department) {
    const { templateIds } = this.getAppConfig()
    if (!templateIds.length) {
      this.saveDepartmentSubscription(department, '订阅成功')
      return
    }

    wx.requestSubscribeMessage({
      tmplIds: templateIds,
      success: (result) => {
        this.updateSubscribeStatus(result)
        const enableWechat = templateIds.every((templateId) => result[templateId] === 'accept')
        if (enableWechat) {
          this.syncMiniappSession(() => {
            this.saveDepartmentSubscription(department, '订阅成功')
          })
          return
        }
        this.saveDepartmentSubscription(department, '订阅成功')
      },
      fail: () => {
        this.saveDepartmentSubscription(department, '订阅成功')
      }
    })
  },

  saveDepartmentSubscription(department, successText) {
    const { userEmail } = this.getAppConfig()
    this.setData({
      savingDepartmentSubscription: true
    })
    this.apiRequest(
      '/api/subscriptions/department',
      'POST',
      {
        userEmail,
        department
      },
      {
        success: (response) => {
          const payload = response.data || {}
          this.setData({
            savingDepartmentSubscription: false
          })
          if (payload.code !== 0) {
            wx.showModal({
              title: '订阅失败',
              content: payload.message || '订阅发布单位失败',
              showCancel: false
            })
            return
          }
          this.setData({
            departmentSubscribed: true
          })
          wx.showToast({
            title: successText,
            icon: 'none'
          })
        },
        fail: (error) => {
          this.setData({
            savingDepartmentSubscription: false
          })
          wx.showModal({
            title: '订阅失败',
            content: (error && error.errMsg) || '订阅发布单位失败',
            showCancel: false
          })
        }
      }
    )
  },

  previewAttachment(event) {
    const { name } = event.currentTarget.dataset
    const notification = this.data.notification || {}
    const detailUrl = notification.detailUrl || ''
    if (!detailUrl) {
      wx.showToast({
        title: '原始链接不存在',
        icon: 'none'
      })
      return
    }

    wx.setClipboardData({
      data: detailUrl,
      success: () => {
        wx.showToast({
          title: `${name || '附件'}已复制原文链接`,
          icon: 'none'
        })
      }
    })
  },

  onShareAppMessage() {
    const notification = this.data.notification || {}
    return {
      title: notification.title || '通知详情',
      path: `/pages/detail/detail?newsId=${encodeURIComponent(this.data.newsId)}`
    }
  },

  onShareTimeline() {
    const notification = this.data.notification || {}
    return {
      title: notification.title || '通知详情',
      query: `newsId=${encodeURIComponent(this.data.newsId)}`
    }
  }
})
