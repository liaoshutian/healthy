import { del, get, post, put, showError, uploadImage } from '../../utils/api'
import { TMPL_MEDICATION } from '../../utils/config'
import { askSubscribe, chooseImage, ymd } from '../../utils/util'

Page({
  data: {
    id: 0,
    symptomId: null as number | null,
    form: { name: '', spec: '', dose: '', times_per_day: '', course_days: '', start_date: ymd(), remind: false } as Record<string, any>,
    photoId: null as number | null,
    photoUrl: '',
    usage: '',
    scanning: false,
  },

  async onLoad(q: Record<string, string | undefined>) {
    if (q.symptom_id) this.setData({ symptomId: Number(q.symptom_id) })
    if (q.id) {
      const meds = await get('/api/medications').catch(showError)
      const m = (meds || []).find((x: any) => x.id === Number(q.id))
      if (m) {
        this.setData({
          id: m.id,
          symptomId: m.symptom_id,
          photoUrl: m.photo_url || '',
          photoId: m.photo_upload_id || null,
          form: { name: m.name, spec: m.spec || '', dose: m.dose || '', times_per_day: m.times_per_day || '', course_days: m.course_days || '', start_date: m.start_date, remind: m.remind },
        })
      }
    }
  },

  onField(e: WechatMiniprogram.Input) {
    this.setData({ [`form.${e.currentTarget.dataset.key}`]: e.detail.value })
  },
  onDate(e: WechatMiniprogram.PickerChange) {
    this.setData({ 'form.start_date': e.detail.value as string })
  },
  onRemind(e: WechatMiniprogram.SwitchChange) {
    this.setData({ 'form.remind': e.detail.value })
  },

  async scan() {
    if (this.data.scanning) return
    let path: string
    try {
      path = await chooseImage()
    } catch (e) {
      return
    }
    this.setData({ scanning: true })
    try {
      const up = await uploadImage(path, 'medicine')
      this.setData({ photoId: up.id, photoUrl: up.url })
      const r = await post('/api/medications/recognize', { upload_id: up.id })
      if (r.fallback) wx.showToast({ title: r.message, icon: 'none' })
      else this.setData({ 'form.name': r.name, 'form.spec': r.spec || '', usage: r.usage || '' })
    } catch (e) {
      showError(e)
    }
    this.setData({ scanning: false })
  },

  async save() {
    const f = this.data.form
    if (!f.name.trim()) return wx.showToast({ title: '填一下药名', icon: 'none' })
    const body = {
      symptom_id: this.data.symptomId,
      name: f.name.trim(),
      spec: f.spec || null,
      dose: f.dose || null,
      times_per_day: parseInt(f.times_per_day, 10) || null,
      course_days: parseInt(f.course_days, 10) || null,
      start_date: f.start_date,
      remind: !!f.remind,
      photo_upload_id: this.data.photoId,
    }
    try {
      const m = this.data.id ? await put(`/api/medications/${this.data.id}`, body) : await post('/api/medications', body)
      if (body.remind) {
        const accepted = await askSubscribe(TMPL_MEDICATION)
        if (accepted) await post(`/api/medications/${m.id}/subscribed`, { accepted })
      }
      wx.navigateBack()
    } catch (e) {
      showError(e)
    }
  },

  remove() {
    wx.showModal({
      title: '删除这条用药记录？',
      success: async (r) => {
        if (!r.confirm) return
        await del(`/api/medications/${this.data.id}`).catch(showError)
        wx.navigateBack()
      },
    })
  },
})
