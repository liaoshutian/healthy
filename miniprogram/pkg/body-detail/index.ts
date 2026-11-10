import { del, get, post, showError } from '../../utils/api'

const LABELS: Record<string, [string, string]> = {
  weight_kg: ['体重', 'kg'],
  body_fat_pct: ['体脂率', '%'],
  skeletal_muscle_kg: ['骨骼肌', 'kg'],
  body_fat_kg: ['体脂肪量', 'kg'],
  bmi: ['BMI', ''],
  visceral_fat_level: ['内脏脂肪等级', '级'],
  bmr_kcal: ['基础代谢', 'kcal'],
  fat_free_mass_kg: ['去脂体重', 'kg'],
  body_water_kg: ['身体水分', 'kg'],
  protein_kg: ['蛋白质', 'kg'],
  mineral_kg: ['无机盐', 'kg'],
  inbody_score: ['InBody 得分', '分'],
}
const SOURCE: Record<string, string> = { inbody: '体测报告', manual: '手动填写', weight: '体重' }

Page({
  data: { id: 0, d: {} as any, rows: [] as any[], when: '', sourceText: '', ai: null as any, aiLoading: false },

  async onLoad(q: Record<string, string | undefined>) {
    this.setData({ id: Number(q.id) })
    try {
      const d = await get(`/api/body/${q.id}`)
      const rows = Object.keys(LABELS)
        .filter((k) => d.fields[k] && d.fields[k].value !== null)
        .map((k) => {
          const f = d.fields[k]
          const delta = f.delta ? (f.delta > 0 ? '比上次 +' : '比上次 ') + f.delta : ''
          return { key: k, label: LABELS[k][0], unit: LABELS[k][1], value: f.value, level: f.level, delta }
        })
      const t = new Date(d.measured_at)
      this.setData({ d, rows, when: `${t.getFullYear()}年${t.getMonth() + 1}月${t.getDate()}日`, sourceText: SOURCE[d.source] })
    } catch (e) {
      showError(e)
    }
  },

  async interpret() {
    if (this.data.aiLoading) return
    this.setData({ aiLoading: true })
    try {
      this.setData({ ai: await post(`/api/body/${this.data.id}/interpret`) })
    } catch (e) {
      showError(e)
    }
    this.setData({ aiLoading: false })
  },

  previewImage() {
    wx.previewImage({ urls: [this.data.d.image_url] })
  },

  remove() {
    wx.showModal({
      title: '删除这条记录？',
      success: async (r) => {
        if (!r.confirm) return
        await del(`/api/body/${this.data.id}`).catch(showError)
        wx.navigateBack()
      },
    })
  },
})
