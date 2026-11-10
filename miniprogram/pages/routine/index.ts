import { get, post, showError } from '../../utils/api'
import { TMPL_ROUTINE } from '../../utils/config'
import { selectTab } from '../../utils/tab'
import { askSubscribe } from '../../utils/util'

Page({
  data: {
    list: [] as any[],
    templates: [] as any[],
  },

  onShow() {
    selectTab(this, 3)
    this.load()
  },

  onPullDownRefresh() {
    this.load().finally(() => wx.stopPullDownRefresh())
  },

  async load() {
    try {
      const [list, templates] = await Promise.all([get('/api/routines'), get('/api/routines/templates')])
      const have = new Set(list.map((r: any) => r.name))
      this.setData({ list, templates: templates.filter((t: any) => !have.has(t.name)) })
    } catch (e) {
      showError(e)
    }
  },

  open(e: WechatMiniprogram.TouchEvent) {
    wx.navigateTo({ url: `/pkg/routine-detail/index?id=${e.currentTarget.dataset.id}` })
  },

  async done(e: WechatMiniprogram.TouchEvent) {
    const id = e.currentTarget.dataset.id
    try {
      const r = await post(`/api/routines/${id}/done`, {})
      // 用户自然操作时顺手请求一次提醒授权
      const accepted = await askSubscribe(TMPL_ROUTINE)
      if (accepted) await post(`/api/routines/${id}/subscribed`, { accepted })
      wx.showToast({ title: r.cheer, icon: 'none' })
      this.load()
    } catch (err) {
      showError(err)
    }
  },

  addTemplate(e: WechatMiniprogram.TouchEvent) {
    const t = this.data.templates[e.currentTarget.dataset.index as number]
    wx.navigateTo({ url: `/pkg/routine-edit/index?template=${encodeURIComponent(JSON.stringify(t))}` })
  },

  addCustom() {
    wx.navigateTo({ url: '/pkg/routine-edit/index' })
  },
})
