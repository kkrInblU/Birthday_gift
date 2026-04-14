const REFRESH_PERIODS = ['1分钟', '5分钟', '半小时', '1小时']

const PERIOD_TO_MINUTES = {
  '1分钟': 1,
  '5分钟': 5,
  '半小时': 30,
  '1小时': 60
}

const MINUTES_TO_PERIOD = {
  1: '1分钟',
  5: '5分钟',
  30: '半小时',
  60: '1小时'
}

Page({
  data: {
    loading: true,
    savingRefreshPeriod: false,
    savingEmailEnabled: false,
    savingMiniappEnabled: false,
    profile: {},
    settings: {
      emailEnabled: true,
      miniappEnabled: true,
      refreshPeriod: '1小时'
    }
  },

  onLoad() {
    const app = getApp()
    this.setData({
      profile: app.globalData.profile || {}
    })
    this.loadUserSettings()
  },

  getAppConfig() {
    const app = getApp()
    return {
      apiBaseUrl: app.globalData.apiBaseUrl,
      userEmail: app.globalData.miniappUserEmail
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

  loadUserSettings() {
    const { userEmail } = this.getAppConfig()
    if (!userEmail) {
      this.setData({ loading: false })
      return
    }

    this.setData({ loading: true })
    this.apiRequest('/api/users/settings', 'GET', { userEmail }, {
      success: (response) => {
        const payload = response.data || {}
        const result = payload.data || {}
        const refreshPeriod = MINUTES_TO_PERIOD[result.refreshIntervalMinutes] || '1小时'
        this.setData({
          loading: false,
          settings: {
            emailEnabled: result.emailEnabled !== false,
            miniappEnabled: result.miniappEnabled !== false,
            refreshPeriod
          }
        })
      },
      fail: (error) => {
        console.error('loadUserSettings failed:', error)
        this.setData({ loading: false })
        wx.showToast({
          title: '设置加载失败',
          icon: 'none'
        })
      }
    })
  },

  saveUserSettings(partialSettings, savingKey, successText) {
    const { userEmail } = this.getAppConfig()
    if (!userEmail) {
      wx.showToast({
        title: '缺少用户邮箱',
        icon: 'none'
      })
      return
    }

    const nextSettings = {
      ...this.data.settings,
      ...partialSettings
    }

    this.setData({
      [savingKey]: true,
      settings: nextSettings
    })

    const requestBody = {
      userEmail
    }

    if (Object.prototype.hasOwnProperty.call(partialSettings, 'emailEnabled')) {
      requestBody.emailEnabled = !!partialSettings.emailEnabled
    }
    if (Object.prototype.hasOwnProperty.call(partialSettings, 'miniappEnabled')) {
      requestBody.miniappEnabled = !!partialSettings.miniappEnabled
    }
    if (Object.prototype.hasOwnProperty.call(partialSettings, 'refreshPeriod')) {
      requestBody.refreshIntervalMinutes = PERIOD_TO_MINUTES[partialSettings.refreshPeriod] || 60
    }

    this.apiRequest('/api/users/settings', 'POST', requestBody, {
      success: (response) => {
        const payload = response.data || {}
        this.setData({
          [savingKey]: false
        })
        if (payload.code !== 0) {
          wx.showToast({
            title: payload.message || '保存失败',
            icon: 'none'
          })
          this.loadUserSettings()
          return
        }
        wx.showToast({
          title: successText,
          icon: 'none'
        })
      },
      fail: (error) => {
        console.error('saveUserSettings failed:', error)
        this.setData({
          [savingKey]: false
        })
        wx.showToast({
          title: '保存失败',
          icon: 'none'
        })
        this.loadUserSettings()
      }
    })
  },

  toggleEmail(event) {
    this.saveUserSettings(
      { emailEnabled: !!event.detail.value },
      'savingEmailEnabled',
      '邮件提醒设置已保存'
    )
  },

  toggleMiniapp(event) {
    this.saveUserSettings(
      { miniappEnabled: !!event.detail.value },
      'savingMiniappEnabled',
      '小程序提醒设置已保存'
    )
  },

  changeRefreshPeriod(event) {
    const nextValue = REFRESH_PERIODS[event.detail.value] || '1小时'
    this.saveUserSettings(
      { refreshPeriod: nextValue },
      'savingRefreshPeriod',
      `已切换为${nextValue}`
    )
  },

  openAdminCrawlerPage() {
    wx.navigateTo({
      url: '/pages/admin-crawler/index'
    })
  }
})
