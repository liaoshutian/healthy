import { get, post, put, showError } from '../../utils/api'
import { TMPL_ROUTINE } from '../../utils/config'
import { askSubscribe, ymd } from '../../utils/util'

Page({
  data: {
    id: 0,
    today: ymd(),
    icons: ['✂️', '🪥', '🦷', '🩺', '🛏️', '💅', '👁️', '🐾', '🩸', '💧', '🌱', '🧹', '🚗', '💊', '📚', '⭐'],
    form: { name: '', icon: '⭐', cycle_days: '30', remind_days_before: '1', last_done_date: '' } as Record<string, string>,
    saving: false,
  },

  async onLoad(q: Record<string, string | undefined>) {
    if (q.template) {
      const t = JSON.parse(decodeURIComponent(q.template))
      this.setData({ form: { ...this.data.form, name: t.name, icon: t.icon, cycle_days: String(t.cycle_days), remind_days_before: String(t.remind_days_before) } })
    }
    if (q.id) {
      const r = await get(`/api/routines/${q.id}`).catch(showError)
      if (r) this.setData({ id: r.id, form: { name: r.name, icon: r.icon, cycle_days: String(r.cycle_days), remind_days_before: String(r.remind_days_before), last_done_date: r.last_done_date || '' } })
    }
  },

  onField(e: WechatMiniprogram.Input) {
    this.setData({ [`form.${e.currentTarget.dataset.key}`]: e.detail.value })
  },
  pickIcon(e: WechatMiniprogram.TouchEvent) {
    this.setData({ 'form.icon': e.currentTarget.dataset.v })
  },
  pickDate(e: WechatMiniprogram.PickerChange) {
    this.setData({ 'form.last_done_date': e.detail.value as string })
  },

  body() {
    const f = this.data.form
    return {
      name: f.name.trim(),
      icon: f.icon,
      cycle_days: parseInt(f.cycle_days, 10) || 30,
      remind_days_before: parseInt(f.remind_days_before, 10) || 0,
      last_done_date: f.last_done_date || null,
    }
  },

  async save() {
    const body = this.body()
    if (!body.name) return wx.showToast({ title: '起个名字吧', icon: 'none' })
    this.setData({ saving: true })
    try {
      const r = this.data.id ? await put(`/api/routines/${this.data.id}`, body) : await post('/api/routines', body)
      const accepted = await askSubscribe(TMPL_ROUTINE)
      if (accepted) await post(`/api/routines/${r.id}/subscribed`, { accepted })
      wx.navigateBack()
    } catch (e) {
      this.setData({ saving: false })
      showError(e)
    }
  },

  /** 写进系统日历：不消耗订阅次数，缺点是完成日变了不会自动更新。
   *  系统日历只支持按天/周/月/年重复，其他周期只写下一次。 */
  addCalendar() {
    const b = this.body()
    if (!b.name) return wx.showToast({ title: '先起个名字', icon: 'none' })
    const base = b.last_done_date ? new Date(b.last_done_date.replace(/-/g, '/')) : new Date()
    const start = new Date(base.getTime() + b.cycle_days * 86400000)
    start.setHours(10, 0, 0, 0)
    const startTime = Math.floor(start.getTime() / 1000)
    const title = `${b.icon} ${b.name}（青柠生活）`
    const done = {
      success: () => wx.showToast({ title: '已写进手机日历', icon: 'none' }),
      fail: () => wx.showToast({ title: '没写进去，检查一下日历权限', icon: 'none' }),
    }
    const interval: Record<number, 'day' | 'week' | 'month' | 'year'> = { 1: 'day', 7: 'week', 28: 'month', 30: 'month', 31: 'month', 365: 'year' }
    const repeat = interval[b.cycle_days]
    if (repeat) {
      wx.addPhoneRepeatCalendar({ title, startTime, repeatInterval: repeat, alarm: true, alarmOffset: b.remind_days_before * 86400, ...done })
    } else {
      wx.addPhoneCalendar({ title, startTime, alarm: true, alarmOffset: b.remind_days_before * 86400, ...done })
    }
  },
})
