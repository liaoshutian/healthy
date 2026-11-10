import { del, get, post, put, showError } from '../../utils/api'
import { guessMealType, ymd } from '../../utils/util'

interface Item {
  key: string
  food_id: number | null
  name: string
  category: string
  grams: number
  unit_name: string
  unit_count: number
  kcal: number
  display: string
  estimated: boolean
  candidates?: string[]
  per100g?: Record<string, number> | null
  x?: number | null
  y?: number | null
  rice_equivalent?: string
}

let seq = 0
const withKey = (it: any): Item => ({ ...it, key: 'k' + seq++ })

Page({
  data: {
    id: 0,
    mealTypes: [
      { key: 'breakfast', label: '早餐' },
      { key: 'lunch', label: '午餐' },
      { key: 'dinner', label: '晚餐' },
      { key: 'snack', label: '加餐' },
    ],
    mealType: guessMealType(),
    date: ymd(),
    items: [] as Item[],
    photoUploadId: null as number | null,
    photoUrl: '',
    source: 'manual',
    summary: {} as any,
    kcal: 0,
    carb: 0,
    protein: 0,
    fat: 0,
    score: null as any,
    saving: false,
  },

  async onLoad(q: Record<string, string | undefined>) {
    if (q.meal_type) this.setData({ mealType: q.meal_type })
    if (q.draft) {
      const d = getApp().globalData.mealDraft || {}
      getApp().globalData.mealDraft = null
      this.setData({
        items: (d.items || []).map(withKey),
        photoUploadId: d.photo_upload_id || null,
        photoUrl: d.photo_url || '',
        source: d.source || 'manual',
        mealType: d.meal_type || this.data.mealType,
      })
      if (d.summary) this.applyDraft(d)
      else this.preview()
      if (q.search) this.addItem()
    } else if (q.id) {
      wx.setNavigationBarTitle({ title: '这顿饭' })
      try {
        const m = await get(`/api/meals/${q.id}`)
        this.setData({ id: m.id, mealType: m.meal_type, date: m.date, items: m.items.map(withKey), photoUploadId: m.photo_upload_id, photoUrl: m.photo_url || '', source: m.source })
        this.preview()
      } catch (e) {
        showError(e)
      }
    }
  },

  applyDraft(d: any) {
    if (!d || !d.summary) return
    this.setData({ summary: d.summary, kcal: d.kcal, carb: d.carb, protein: d.protein, fat: d.fat, score: d.score })
  },

  payloadItems() {
    return this.data.items.map((i) => ({
      food_id: i.food_id,
      name: i.name,
      grams: i.grams,
      category: i.category,
      per100g: i.per100g || null,
    }))
  },

  async preview() {
    if (!this.data.items.length) {
      this.setData({ summary: {}, kcal: 0, score: null })
      return
    }
    try {
      const d = await post('/api/meals/preview', { items: this.payloadItems() })
      // 保留照片上的位置和候选名
      const items = d.items.map((it: any, i: number) => ({ ...this.data.items[i], ...it, key: this.data.items[i].key }))
      this.setData({ items })
      this.applyDraft(d)
    } catch (e) {
      showError(e)
    }
  },

  pickType(e: WechatMiniprogram.TouchEvent) {
    this.setData({ mealType: e.currentTarget.dataset.key })
  },
  pickDate(e: WechatMiniprogram.PickerChange) {
    this.setData({ date: e.detail.value as string })
  },

  step(e: WechatMiniprogram.TouchEvent) {
    const i = e.currentTarget.dataset.index as number
    const d = Number(e.currentTarget.dataset.d)
    const it = this.data.items[i]
    const perUnit = it.grams / (it.unit_count || 1)
    const count = Math.max(0.5, Math.round(((it.unit_count || 1) + d) * 2) / 2)
    this.setData({ [`items[${i}].unit_count`]: count, [`items[${i}].grams`]: Math.round(perUnit * count) })
    this.preview()
  },

  rename(e: WechatMiniprogram.TouchEvent) {
    const i = e.currentTarget.dataset.index as number
    const it = this.data.items[i]
    const options = [...(it.candidates || []), '搜索食物库…'].slice(0, 6)
    wx.showActionSheet({
      itemList: options,
      success: (r) => {
        if (r.tapIndex === options.length - 1) return this.search(i)
        this.setData({ [`items[${i}].name`]: options[r.tapIndex], [`items[${i}].food_id`]: null })
        this.preview()
      },
    })
  },

  remove(e: WechatMiniprogram.TouchEvent) {
    const items = this.data.items.slice()
    items.splice(e.currentTarget.dataset.index as number, 1)
    this.setData({ items })
    this.preview()
  },

  addItem() {
    this.search(-1)
  },

  /** 打开食物库搜索；index = -1 表示新增，否则替换那一项 */
  search(index: number) {
    wx.navigateTo({
      url: '/pkg/food-search/index?pick=1',
      events: {
        pick: (food: any) => {
          const item = withKey({ food_id: food.id, name: food.name, category: food.category, grams: food.unit_grams, unit_name: food.unit_name, unit_count: 1, kcal: 0, display: '', estimated: false })
          const items = this.data.items.slice()
          if (index >= 0) {
            item.x = items[index].x
            item.y = items[index].y
            items[index] = item
          } else items.push(item)
          this.setData({ items })
          this.preview()
        },
      },
    })
  },

  async save() {
    if (this.data.saving || !this.data.items.length) return
    this.setData({ saving: true })
    const body = {
      date: this.data.date,
      meal_type: this.data.mealType,
      items: this.payloadItems(),
      photo_upload_id: this.data.photoUploadId,
      source: this.data.source,
    }
    try {
      const r = this.data.id ? await put(`/api/meals/${this.data.id}`, body) : await post('/api/meals', body)
      wx.showToast({ title: r.cheer || '保存好了', icon: 'none' })
      setTimeout(() => wx.navigateBack({ fail: () => wx.switchTab({ url: '/pages/today/index' }) }), 800)
    } catch (e) {
      this.setData({ saving: false })
      showError(e)
    }
  },

  deleteMeal() {
    wx.showModal({
      title: '删除这顿饭？',
      success: async (r) => {
        if (!r.confirm) return
        try {
          await del(`/api/meals/${this.data.id}`)
          wx.navigateBack()
        } catch (e) {
          showError(e)
        }
      },
    })
  },

  goMember() {
    wx.navigateTo({ url: '/pkg/member/index' })
  },
})
