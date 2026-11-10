import { post, showError, uploadImage } from '../../utils/api'
import { chooseImage, ensureConsent, ymd } from '../../utils/util'

const FIELDS = [
  { key: 'weight_kg', label: '体重', unit: 'kg' },
  { key: 'body_fat_pct', label: '体脂率', unit: '%' },
  { key: 'skeletal_muscle_kg', label: '骨骼肌', unit: 'kg' },
  { key: 'body_fat_kg', label: '体脂肪量', unit: 'kg' },
  { key: 'bmi', label: 'BMI', unit: '' },
  { key: 'visceral_fat_level', label: '内脏脂肪等级', unit: '级' },
  { key: 'bmr_kcal', label: '基础代谢', unit: 'kcal' },
  { key: 'fat_free_mass_kg', label: '去脂体重', unit: 'kg' },
  { key: 'body_water_kg', label: '身体水分', unit: 'kg' },
  { key: 'protein_kg', label: '蛋白质', unit: 'kg' },
  { key: 'mineral_kg', label: '无机盐', unit: 'kg' },
  { key: 'inbody_score', label: 'InBody 得分', unit: '分' },
]

Page({
  data: {
    modes: [
      { key: 'inbody', label: '拍报告' },
      { key: 'weight', label: '只记体重' },
      { key: 'manual', label: '手动填写' },
    ],
    mode: 'inbody',
    fields: FIELDS,
    form: {} as Record<string, string>,
    low: {} as Record<string, boolean>,
    lowCount: 0,
    date: ymd(),
    recognized: false,
    loading: false,
    saving: false,
    imageUploadId: null as number | null,
    imageUrl: '',
    segments: null as any,
    confidence: null as any,
  },

  async onLoad(q: Record<string, string | undefined>) {
    if (q.mode) this.setData({ mode: q.mode })
    const me = getApp().globalData.me || (await getApp().loadMe().catch(() => null))
    const ok = await ensureConsent('health', !!(me && me.health_consent))
    if (!ok) {
      wx.navigateBack()
      return
    }
    if (me) me.health_consent = true
  },

  switchMode(e: WechatMiniprogram.TouchEvent) {
    this.setData({ mode: e.currentTarget.dataset.key })
  },
  pickDate(e: WechatMiniprogram.PickerChange) {
    this.setData({ date: e.detail.value as string })
  },
  onField(e: WechatMiniprogram.Input) {
    const key = e.currentTarget.dataset.key as string
    this.setData({ [`form.${key}`]: e.detail.value, [`low.${key}`]: false })
  },
  previewImage() {
    wx.previewImage({ urls: [this.data.imageUrl] })
  },
  shoot() {
    this.pick(['camera'])
  },
  album() {
    this.pick(['album'])
  },

  async pick(source: ('album' | 'camera')[]) {
    let path: string
    try {
      path = await chooseImage(source)
    } catch (e) {
      return
    }
    this.setData({ loading: true })
    try {
      const up = await uploadImage(path, 'inbody')
      const r = await post('/api/body/recognize', { upload_id: up.id })
      if (r.fallback) {
        wx.showToast({ title: r.message, icon: 'none', duration: 2500 })
        this.setData({ mode: 'manual', loading: false, imageUploadId: up.id, imageUrl: up.url })
        return
      }
      const form: Record<string, string> = {}
      const low: Record<string, boolean> = {}
      FIELDS.forEach((f) => {
        const v = r.fields[f.key]
        if (v !== null && v !== undefined) form[f.key] = String(v)
      })
      ;(r.low_confidence as string[]).forEach((k) => (low[k] = true))
      const measured = r.fields.measured_at ? String(r.fields.measured_at).slice(0, 10) : this.data.date
      this.setData({
        form,
        low,
        lowCount: Object.keys(low).length,
        recognized: true,
        loading: false,
        imageUploadId: r.image_upload_id,
        imageUrl: r.image_url,
        segments: r.segments,
        confidence: r.confidence,
        date: /^\d{4}-\d{2}-\d{2}$/.test(measured) ? measured : this.data.date,
      })
    } catch (e) {
      this.setData({ loading: false })
      showError(e)
    }
  },

  async save(confirmBig = false) {
    if (this.data.saving) return
    const body: Record<string, unknown> = {
      source: this.data.mode === 'weight' ? 'weight' : this.data.recognized ? 'inbody' : 'manual',
      image_upload_id: this.data.imageUploadId,
      segments: this.data.segments,
      confidence: this.data.confidence,
      confirm_big_change: confirmBig === true,
    }
    if (this.data.date !== ymd()) body.measured_at = this.data.date + 'T08:00:00+08:00'
    let any = false
    FIELDS.forEach((f) => {
      const v = parseFloat(this.data.form[f.key])
      if (!isNaN(v)) {
        body[f.key] = v
        any = true
      }
    })
    if (!any) return wx.showToast({ title: '至少填一项吧', icon: 'none' })
    this.setData({ saving: true })
    try {
      const r = await post('/api/body', body)
      if (r.celebrate) wx.showToast({ title: '🎉 比上次更好啦', icon: 'none' })
      else wx.showToast({ title: '记好啦', icon: 'none' })
      setTimeout(() => wx.redirectTo({ url: `/pkg/body-detail/index?id=${r.id}` }), 700)
    } catch (e: any) {
      this.setData({ saving: false })
      if (e.status === 409) {
        wx.showModal({ title: '确认一下', content: e.message, confirmText: '没填错', success: (m) => m.confirm && this.save(true) })
        return
      }
      showError(e)
    }
  },
})
