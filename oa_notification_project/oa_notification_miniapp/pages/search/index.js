const HISTORY_STORAGE_KEY = 'oa_notification_search_history'

Page({
  data: {
    keyword: '',
    loading: false,
    history: [],
    sourceItems: [],
    resultItems: []
  },

  onLoad() {
    this.setData({
      history: wx.getStorageSync(HISTORY_STORAGE_KEY) || []
    })
    this.loadSourceItems()
  },

  getAppConfig() {
    const app = getApp()
    return {
      apiBaseUrl: app.globalData.apiBaseUrl
    }
  },

  loadSourceItems() {
    const { apiBaseUrl } = this.getAppConfig()
    this.setData({ loading: true })
    wx.request({
      url: `${apiBaseUrl}/api/notifications`,
      method: 'GET',
      timeout: 10000,
      data: { limit: 100 },
      success: (response) => {
        const payload = response.data || {}
        const result = payload.data || {}
        this.setData({
          loading: false,
          sourceItems: Array.isArray(result.items) ? result.items : []
        })
      },
      fail: () => {
        this.setData({ loading: false })
      }
    })
  },

  onKeywordInput(event) {
    this.setData({
      keyword: (event.detail.value || '').trim()
    })
  },

  runSearch() {
    const keyword = this.data.keyword.trim()
    if (!keyword) {
      this.setData({ resultItems: [] })
      return
    }
    const history = [keyword].concat(this.data.history.filter((item) => item !== keyword)).slice(0, 10)
    wx.setStorageSync(HISTORY_STORAGE_KEY, history)
    const resultItems = this.data.sourceItems.filter((item) => {
      return [item.title, item.department, item.summary].some((field) => String(field || '').includes(keyword))
    })
    this.setData({
      history,
      resultItems
    })
  },

  useHistory(event) {
    const { keyword } = event.currentTarget.dataset
    this.setData({ keyword: keyword || '' })
    this.runSearch()
  },

  openDetail(event) {
    const { newsId } = event.currentTarget.dataset
    if (!newsId) {
      return
    }
    wx.navigateTo({
      url: `/pages/detail/detail?newsId=${encodeURIComponent(newsId)}`
    })
  }
})
