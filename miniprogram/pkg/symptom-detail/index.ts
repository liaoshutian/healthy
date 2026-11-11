import { del, get, post, showError } from '../../utils/api'
import { ensureConsent } from '../../utils/util'

function fmt(s: string) {
  const d = new Date(s)
  return `${d.getMonth() + 1}月${d.getDate()}日`
}

Page({
  data: {
    id: 0,
    symptoms: [] as any[],
    meds: [] as any[],
    records: [] as any[],
    s: {} as any,
    title: '',
    when: '',
    follow: 3,
    followNote: '',
    curve: [] as any[],
    timeline: [] as any[],
    canvasW: 375,
    canvasH: 600,
  },

  async onLoad(q: Record<string, string | undefined>) {
    this.setData({ id: Number(q.id || 0) })
    const app = getApp()
    const me = app.globalData.me || (await app.loadMe().catch(() => null))
    const ok = await ensureConsent('medical', !!(me && me.medical_consent))
    if (!ok) {
      wx.navigateBack()
      return
    }
    if (me) me.medical_consent = true
    this.load()
  },

  onShow() {
    if (this.data.s.id || this.data.symptoms.length) this.load()
  },

  async load() {
    try {
      if (!this.data.id) {
        const [symptoms, meds, records] = await Promise.all([get('/api/symptoms'), get('/api/medications'), get('/api/medical-records')])
        this.setData({
          symptoms: symptoms.map((s: any) => ({ ...s, title: s.parts.map((p: any) => p.label.split(' · ').pop()).join('、') + (s.symptoms.length ? ' · ' + s.symptoms.join('、') : ''), when: fmt(s.started_at) })),
          meds,
          records,
        })
        return
      }
      const s = await get(`/api/symptoms/${this.data.id}`)
      const timeline: any[] = []
      s.updates.forEach((u: any) => timeline.push({ key: 'u' + u.date, icon: '🩹', date: u.date, text: `难受程度 ${u.severity}/10${u.temperature ? ' · ' + u.temperature + '℃' : ''}${u.note ? ' · ' + u.note : ''}` }))
      s.medications.forEach((m: any) => timeline.push({ key: 'm' + m.id, icon: '💊', date: m.start_date, text: `${m.name} ${m.spec || ''} 每次${m.dose || '?'} 每天${m.times_per_day || '?'}次${m.course_days ? '，' + m.course_days + '天' : ''}` }))
      s.records.forEach((r: any) => timeline.push({ key: 'r' + r.id, icon: '🏥', date: r.visit_date, text: `${r.hospital || ''}${r.department || ''} ${r.diagnosis || ''}`, images: r.images }))
      timeline.sort((a, b) => (a.date < b.date ? 1 : -1))
      this.setData({
        s,
        title: s.parts.map((p: any) => p.label.split(' · ').pop()).join('、') + (s.symptoms.length ? ' · ' + s.symptoms.join('、') : ''),
        when: fmt(s.started_at),
        follow: s.severity,
        curve: s.updates.map((u: any) => ({ date: u.date, severity: u.severity, label: u.date.slice(5) })),
        timeline,
      })
    } catch (e) {
      showError(e)
    }
  },

  open(e: WechatMiniprogram.TouchEvent) {
    wx.navigateTo({ url: `/pkg/symptom-detail/index?id=${e.currentTarget.dataset.id}` })
  },
  openMed(e: WechatMiniprogram.TouchEvent) {
    wx.navigateTo({ url: `/pkg/medication-edit/index?id=${e.currentTarget.dataset.id}` })
  },
  openRecord(e: WechatMiniprogram.TouchEvent) {
    wx.navigateTo({ url: `/pkg/medical-edit/index?id=${e.currentTarget.dataset.id}` })
  },
  newSymptom() {
    wx.navigateTo({ url: '/pkg/symptom-edit/index' })
  },
  newMed() {
    wx.navigateTo({ url: `/pkg/medication-edit/index?symptom_id=${this.data.id || ''}` })
  },
  newRecord() {
    wx.navigateTo({ url: `/pkg/medical-edit/index?symptom_id=${this.data.id || ''}` })
  },
  preview(e: WechatMiniprogram.TouchEvent) {
    wx.previewImage({ urls: [e.currentTarget.dataset.url] })
  },

  onFollow(e: WechatMiniprogram.SliderChange) {
    this.setData({ follow: e.detail.value })
  },
  onFollowNote(e: WechatMiniprogram.Input) {
    this.setData({ followNote: e.detail.value })
  },

  async saveFollow() {
    try {
      await post(`/api/symptoms/${this.data.id}/updates`, { severity: this.data.follow, note: this.data.followNote || null })
      wx.showToast({ title: '记下了，照顾好自己', icon: 'none' })
      this.setData({ followNote: '' })
      this.load()
    } catch (e) {
      showError(e)
    }
  },

  async heal() {
    try {
      const r = await post(`/api/symptoms/${this.data.id}/heal`)
      wx.showToast({ title: r.cheer, icon: 'none', duration: 2500 })
      this.load()
    } catch (e) {
      showError(e)
    }
  },

  remove() {
    wx.showModal({
      title: '删除这条记录？',
      success: async (r) => {
        if (!r.confirm) return
        await del(`/api/symptoms/${this.data.id}`).catch(showError)
        wx.navigateBack()
      },
    })
  },

  /** 把病情摘要画成一张图，存到相册，就诊时给医生看 */
  async makeSummary() {
    let sum: any
    try {
      sum = await get(`/api/symptoms/${this.data.id}/summary`)
    } catch (e) {
      return showError(e)
    }
    const W = 375
    const lineH = 22
    const wrapAt = 22
    const lines: string[] = []
    sum.lines.forEach((l: string) => {
      for (let i = 0; i < l.length; i += wrapAt) lines.push(l.slice(i, i + wrapAt))
    })
    const H = 120 + lines.length * lineH + 60
    this.setData({ canvasW: W, canvasH: H })
    setTimeout(() => {
      this.createSelectorQuery()
        .select('#summary')
        .fields({ node: true, size: true })
        .exec((res) => {
          const canvas = res[0].node as WechatMiniprogram.Canvas
          const ctx = canvas.getContext('2d') as any
          const dpr = 2
          canvas.width = W * dpr
          canvas.height = H * dpr
          ctx.scale(dpr, dpr)
          ctx.fillStyle = '#FFFFFF'
          ctx.fillRect(0, 0, W, H)
          ctx.fillStyle = '#7DBE3C'
          ctx.fillRect(0, 0, W, 6)
          ctx.fillStyle = '#2F3A24'
          ctx.font = 'bold 20px sans-serif'
          ctx.fillText(sum.title, 20, 46)
          ctx.font = '12px sans-serif'
          ctx.fillStyle = '#8A9479'
          ctx.fillText('吃饱睡好簿 · ' + new Date(sum.generated_at).toLocaleDateString(), 20, 70)
          ctx.fillStyle = '#2F3A24'
          ctx.font = '15px sans-serif'
          lines.forEach((l, i) => ctx.fillText(l, 20, 110 + i * lineH))
          ctx.fillStyle = '#8A9479'
          ctx.font = '12px sans-serif'
          ctx.fillText(sum.disclaimer, 20, H - 24)
          wx.canvasToTempFilePath({
            canvas,
            success: (r) => {
              wx.previewImage({ urls: [r.tempFilePath] })
              wx.saveImageToPhotosAlbum({ filePath: r.tempFilePath, success: () => wx.showToast({ title: '已存到相册', icon: 'none' }) })
            },
          })
        })
    }, 50)
  },
})
