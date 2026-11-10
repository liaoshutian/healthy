import { get, post, showError } from '../../utils/api'
import { ensureConsent, pad, ymd } from '../../utils/util'

const now = new Date()

Page({
  data: {
    bodyParts: [] as any[],
    tags: [] as string[],
    parts: [] as any[],
    picked: {} as Record<string, boolean>,
    severity: 4,
    today: ymd(),
    startDate: ymd(),
    startTime: `${pad(now.getHours())}:${pad(now.getMinutes())}`,
    temperature: '',
    note: '',
    lastHint: '',
    saving: false,
  },

  async onLoad() {
    const app = getApp()
    const me = app.globalData.me || (await app.loadMe().catch(() => null))
    const ok = await ensureConsent('medical', !!(me && me.medical_consent))
    if (!ok) {
      wx.navigateBack()
      return
    }
    if (me) me.medical_consent = true
    try {
      const meta = await app.loadMeta()
      this.setData({ bodyParts: meta.body_parts, tags: meta.symptom_tags })
    } catch (e) {
      showError(e)
    }
  },

  onParts(e: WechatMiniprogram.CustomEvent) {
    this.setData({ parts: e.detail.value })
    const last = e.detail.value[e.detail.value.length - 1]
    if (last) this.checkLast(last.code)
  },

  onFocus(e: WechatMiniprogram.CustomEvent) {
    this.checkLast(e.detail.code)
  },

  /** 同一部位再不舒服时提示“上次也是这里” */
  async checkLast(code: string) {
    try {
      const r = await get('/api/symptoms/last-at', { code })
      this.setData({ lastHint: r ? r.text : '' })
    } catch (e) {
      /* 提示失败不影响记录 */
    }
  },

  toggleTag(e: WechatMiniprogram.TouchEvent) {
    const v = e.currentTarget.dataset.v as string
    this.setData({ [`picked.${v}`]: !this.data.picked[v] })
  },
  onSeverity(e: WechatMiniprogram.SliderChange) {
    this.setData({ severity: e.detail.value })
  },
  onDate(e: WechatMiniprogram.PickerChange) {
    this.setData({ startDate: e.detail.value as string })
  },
  onTime(e: WechatMiniprogram.PickerChange) {
    this.setData({ startTime: e.detail.value as string })
  },
  onTemp(e: WechatMiniprogram.Input) {
    this.setData({ temperature: e.detail.value })
  },
  onNote(e: WechatMiniprogram.Input) {
    this.setData({ note: e.detail.value })
  },

  async save() {
    if (!this.data.parts.length) return wx.showToast({ title: '先在人体图上点一下哪里不舒服', icon: 'none' })
    this.setData({ saving: true })
    try {
      const t = parseFloat(this.data.temperature)
      const s = await post('/api/symptoms', {
        parts: this.data.parts.map((p: any) => ({ code: p.code, note: p.note || null })),
        symptoms: Object.keys(this.data.picked).filter((k) => this.data.picked[k]),
        severity: this.data.severity,
        started_at: `${this.data.startDate}T${this.data.startTime}:00+08:00`,
        temperature: isNaN(t) ? null : t,
        note: this.data.note || null,
      })
      wx.redirectTo({ url: `/pkg/symptom-detail/index?id=${s.id}` })
    } catch (e) {
      this.setData({ saving: false })
      showError(e)
    }
  },
})
