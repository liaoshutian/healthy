import { del, get, post, put, showError, uploadImage } from '../../utils/api'
import { ymd } from '../../utils/util'

Page({
  data: {
    id: 0,
    symptomId: null as number | null,
    form: { visit_date: ymd(), hospital: '', department: '', diagnosis: '' } as Record<string, string>,
    images: [] as { id: number; url: string }[],
  },

  async onLoad(q: Record<string, string | undefined>) {
    if (q.symptom_id) this.setData({ symptomId: Number(q.symptom_id) })
    if (q.id) {
      const list = await get('/api/medical-records').catch(showError)
      const r = (list || []).find((x: any) => x.id === Number(q.id))
      if (r) this.setData({ id: r.id, symptomId: r.symptom_id, images: r.images, form: { visit_date: r.visit_date, hospital: r.hospital || '', department: r.department || '', diagnosis: r.diagnosis || '' } })
    }
  },

  onField(e: WechatMiniprogram.Input) {
    this.setData({ [`form.${e.currentTarget.dataset.key}`]: e.detail.value })
  },
  onDate(e: WechatMiniprogram.PickerChange) {
    this.setData({ 'form.visit_date': e.detail.value as string })
  },
  preview(e: WechatMiniprogram.TouchEvent) {
    wx.previewImage({ urls: this.data.images.map((i) => i.url), current: e.currentTarget.dataset.url })
  },
  removeImage(e: WechatMiniprogram.TouchEvent) {
    const images = this.data.images.slice()
    images.splice(e.currentTarget.dataset.index as number, 1)
    this.setData({ images })
  },

  addImage() {
    wx.chooseMedia({
      count: Math.min(9, 20 - this.data.images.length),
      mediaType: ['image'],
      sizeType: ['compressed'],
      success: async (r) => {
        wx.showLoading({ title: '上传中' })
        try {
          for (const f of r.tempFiles) {
            const up = await uploadImage(f.tempFilePath, 'medical')
            this.setData({ images: [...this.data.images, up] })
          }
        } catch (e) {
          showError(e)
        }
        wx.hideLoading()
      },
    })
  },

  async save() {
    const f = this.data.form
    const body = {
      symptom_id: this.data.symptomId,
      visit_date: f.visit_date,
      hospital: f.hospital || null,
      department: f.department || null,
      diagnosis: f.diagnosis || null,
      image_upload_ids: this.data.images.map((i) => i.id),
    }
    try {
      if (this.data.id) await put(`/api/medical-records/${this.data.id}`, body)
      else await post('/api/medical-records', body)
      wx.navigateBack()
    } catch (e) {
      showError(e)
    }
  },

  remove() {
    wx.showModal({
      title: '删除这次就诊记录？',
      content: '照片也会一起删除',
      success: async (r) => {
        if (!r.confirm) return
        await del(`/api/medical-records/${this.data.id}`).catch(showError)
        wx.navigateBack()
      },
    })
  },
})
