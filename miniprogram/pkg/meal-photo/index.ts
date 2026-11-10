import { post, showError, uploadImage } from '../../utils/api'
import { chooseImage } from '../../utils/util'

Page({
  data: { photo: '', loading: false, mealType: '' },

  onLoad(q: Record<string, string | undefined>) {
    this.setData({ mealType: q.meal_type || '' })
  },

  shoot() {
    this.pick(['camera'])
  },
  album() {
    this.pick(['album'])
  },
  manual() {
    wx.redirectTo({ url: `/pkg/meal-edit/index?meal_type=${this.data.mealType}` })
  },

  async pick(source: ('album' | 'camera')[]) {
    let path: string
    try {
      path = await chooseImage(source)
    } catch (e) {
      return
    }
    this.setData({ photo: path, loading: true })
    try {
      const up = await uploadImage(path, 'food')
      const draft = await post('/api/meals/recognize', { upload_id: up.id })
      if (draft.fallback) {
        // 识别失败或配额用完 → 退化成食物库搜索，照片保留
        wx.showToast({ title: draft.message, icon: 'none', duration: 2500 })
        getApp().globalData.mealDraft = { items: [], photo_upload_id: up.id, photo_url: up.url, source: 'photo', meal_type: this.data.mealType }
        wx.redirectTo({ url: '/pkg/meal-edit/index?draft=1&search=1' })
        return
      }
      getApp().globalData.mealDraft = { ...draft, source: 'photo', meal_type: this.data.mealType || draft.suggested_meal_type }
      wx.redirectTo({ url: '/pkg/meal-edit/index?draft=1' })
    } catch (e) {
      this.setData({ loading: false, photo: '' })
      showError(e)
    }
  },
})
