import { get, post, showError } from '../../utils/api'

const TIER_NAME: Record<string, string> = { free: '免费版', pro: 'Pro', max: 'Max' }
const FEATURE: Record<string, string> = { food: '拍食物', inbody: '拍体测报告', medicine: '拍药盒' }

Page({
  data: { d: { benefits: {} } as any, tierName: '', quotas: [] as any[], code: '', redeeming: false, highlight: '' },

  onLoad(q: Record<string, string | undefined>) {
    this.setData({ highlight: q.highlight || '' })
    this.load()
  },

  async load() {
    try {
      const d = await get('/api/membership')
      this.setData({ d, tierName: TIER_NAME[d.tier], quotas: d.quotas.map((x: any) => ({ ...x, label: FEATURE[x.feature] || x.feature })) })
    } catch (e) {
      showError(e)
    }
  },

  onCode(e: WechatMiniprogram.Input) {
    this.setData({ code: e.detail.value })
  },

  copyId() {
    wx.setClipboardData({ data: this.data.d.member_id })
  },

  async redeem() {
    const code = this.data.code.trim()
    if (!code || this.data.redeeming) return
    this.setData({ redeeming: true })
    try {
      const r = await post('/api/membership/redeem', { code })
      wx.showToast({ title: r.message, icon: 'none' })
      getApp().globalData.me = null
      this.setData({ code: '' })
      this.load()
    } catch (e) {
      showError(e)
    }
    this.setData({ redeeming: false })
  },
})
