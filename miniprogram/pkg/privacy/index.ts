import { del, get, showError } from '../../utils/api'

Page({
  data: { me: {} as any },

  async onLoad() {
    try {
      this.setData({ me: await get('/api/me') })
    } catch (e) {
      showError(e)
    }
  },

  deleteAccount() {
    wx.showModal({
      title: '确定注销吗？',
      content: '所有记录和照片都会被删除，无法恢复。',
      confirmText: '注销',
      confirmColor: '#8A9479',
      success: (r) => {
        if (!r.confirm) return
        wx.showModal({
          title: '再确认一次',
          content: '真的要删除全部数据吗？',
          confirmText: '删除',
          success: async (r2) => {
            if (!r2.confirm) return
            try {
              await del('/api/me')
              wx.clearStorageSync()
              wx.reLaunch({ url: '/pages/today/index' })
            } catch (e) {
              showError(e)
            }
          },
        })
      },
    })
  },
})
