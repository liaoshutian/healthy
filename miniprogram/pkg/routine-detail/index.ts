import { del, get, post, put, showError, uploadImage } from '../../utils/api'
import { TMPL_ROUTINE } from '../../utils/config'
import { askSubscribe, chooseImage } from '../../utils/util'

Page({
  data: { id: 0, d: {} as any, regularity: '-', note: '', cost: '', photos: [] as { id: number; url: string }[] },

  onLoad(q: Record<string, string | undefined>) {
    this.setData({ id: Number(q.id) })
  },

  onShow() {
    this.load()
  },

  async load() {
    try {
      const d = await get(`/api/routines/${this.data.id}`)
      this.setData({ d, regularity: d.regularity === null ? '-' : Math.round(d.regularity * 100) + '%' })
    } catch (e) {
      showError(e)
    }
  },

  onNote(e: WechatMiniprogram.Input) {
    this.setData({ note: e.detail.value })
  },
  onCost(e: WechatMiniprogram.Input) {
    this.setData({ cost: e.detail.value })
  },

  async addPhoto() {
    try {
      const path = await chooseImage()
      wx.showLoading({ title: '上传中' })
      const up = await uploadImage(path, 'routine')
      this.setData({ photos: [...this.data.photos, up] })
    } catch (e) {
      if ((e as any)?.message) showError(e)
    } finally {
      wx.hideLoading()
    }
  },

  async done() {
    try {
      const r = await post(`/api/routines/${this.data.id}/done`, {
        note: this.data.note || null,
        cost: this.data.cost ? parseFloat(this.data.cost) : null,
        photo_upload_ids: this.data.photos.map((p) => p.id),
      })
      const accepted = await askSubscribe(TMPL_ROUTINE)
      if (accepted) await post(`/api/routines/${this.data.id}/subscribed`, { accepted })
      wx.showToast({ title: r.cheer, icon: 'none' })
      this.setData({ note: '', cost: '', photos: [] })
      this.load()
    } catch (e) {
      showError(e)
    }
  },

  async snooze() {
    try {
      await post(`/api/routines/${this.data.id}/snooze`, { days: 3 })
      wx.showToast({ title: '好的，晚 3 天再说', icon: 'none' })
      this.load()
    } catch (e) {
      showError(e)
    }
  },

  async applySuggestion() {
    const avg = Math.round(this.data.d.average_cycle)
    const d = this.data.d
    try {
      await put(`/api/routines/${this.data.id}`, { name: d.name, icon: d.icon, cycle_days: avg, remind_days_before: d.remind_days_before, last_done_date: d.last_done_date })
      wx.showToast({ title: `改成每 ${avg} 天了`, icon: 'none' })
      this.load()
    } catch (e) {
      showError(e)
    }
  },

  preview(e: WechatMiniprogram.TouchEvent) {
    wx.previewImage({ urls: [e.currentTarget.dataset.url] })
  },

  edit() {
    wx.navigateTo({ url: `/pkg/routine-edit/index?id=${this.data.id}` })
  },

  archive() {
    wx.showModal({
      title: '不再管这件事？',
      content: '历史记录会保留',
      success: async (r) => {
        if (!r.confirm) return
        await del(`/api/routines/${this.data.id}`).catch(showError)
        wx.navigateBack()
      },
    })
  },
})
