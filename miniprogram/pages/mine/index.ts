import { API_BASE } from '../../utils/config'
import { get, login, showError } from '../../utils/api'
import { selectTab } from '../../utils/tab'

const TIER_NAME: Record<string, string> = { free: '免费版', pro: 'Pro', max: 'Max' }

Page({
  data: {
    me: {} as any,
    tierName: '',
    endText: '',
    challenge: null as any,
    badges: [] as any[],
  },

  onShow() {
    selectTab(this, 4)
    this.load()
  },

  async load() {
    try {
      const [me, challenges, badges] = await Promise.all([get('/api/me'), get('/api/challenges'), get('/api/me/badges')])
      getApp().globalData.me = me
      const end = me.tier_end_at ? new Date(me.tier_end_at) : null
      this.setData({
        me,
        tierName: TIER_NAME[me.tier],
        endText: end ? `${end.getFullYear()}-${end.getMonth() + 1}-${end.getDate()}` : '',
        challenge: challenges.find((c: any) => c.status === 'active') || null,
        badges: badges.slice(0, 8),
      })
    } catch (e) {
      showError(e)
    }
  },

  goProfile() {
    wx.navigateTo({ url: '/pkg/profile/index' })
  },
  goMember() {
    wx.navigateTo({ url: '/pkg/member/index' })
  },
  goPlans() {
    wx.navigateTo({ url: '/pkg/plans/index' })
  },
  goBadges() {
    wx.navigateTo({ url: '/pkg/badges/index' })
  },
  goSymptoms() {
    wx.navigateTo({ url: '/pkg/symptom-detail/index' })
  },
  goPrivacy() {
    wx.navigateTo({ url: '/pkg/privacy/index' })
  },

  async exportData() {
    if (this.data.me.tier === 'free') {
      return showError({ status: 402, message: '数据导出是 Pro 权益' })
    }
    const token = await login()
    wx.showLoading({ title: '正在打包' })
    wx.downloadFile({
      url: API_BASE + '/api/me/export',
      header: { Authorization: `Bearer ${token}` },
      success: (r) => {
        wx.hideLoading()
        if (r.statusCode !== 200) return showError({ status: r.statusCode, message: '导出失败' })
        // 小程序里不能直接存 zip 到相册，转发到聊天里再在电脑上打开
        wx.shareFileMessage({ filePath: r.tempFilePath, fileName: '青柠生活数据.zip', fail: () => wx.showToast({ title: '已取消', icon: 'none' }) })
      },
      fail: () => {
        wx.hideLoading()
        showError({ status: 0, message: '导出失败' })
      },
    })
  },
})
