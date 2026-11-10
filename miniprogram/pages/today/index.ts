import { get, post, showError } from '../../utils/api'
import { selectTab } from '../../utils/tab'
import { greeting } from '../../utils/util'

const WEEK = ['日', '一', '二', '三', '四', '五', '六']

Page({
  data: {
    d: {} as any,
    greeting: greeting(),
    dateText: '',
    showMacro: false,
    recommend: null as any,
  },

  onShow() {
    selectTab(this, 0)
    const now = new Date()
    this.setData({ greeting: greeting(), dateText: `${now.getMonth() + 1}月${now.getDate()}日 星期${WEEK[now.getDay()]}` })
    this.load()
  },

  onPullDownRefresh() {
    this.load().finally(() => wx.stopPullDownRefresh())
  },

  async load() {
    try {
      const d = await get('/api/today')
      this.setData({ d })
      if (!d.challenge) {
        const rec = await get('/api/plans/recommend').catch(() => null)
        this.setData({ recommend: rec })
      } else {
        this.setData({ recommend: null })
      }
    } catch (e) {
      showError(e)
    }
  },

  toggleMacro() {
    this.setData({ showMacro: !this.data.showMacro })
  },

  onPetal(e: WechatMiniprogram.TouchEvent) {
    const key = e.currentTarget.dataset.key as string
    if (key === 'water') return this.addWater()
    if (key === 'body') return wx.navigateTo({ url: '/pkg/body-edit/index?mode=weight' })
    if (key === 'care') return wx.switchTab({ url: '/pages/routine/index' })
    wx.navigateTo({ url: `/pkg/meal-photo/index?meal_type=${key}` })
  },

  async addWater() {
    try {
      const r = await post('/api/water', { delta: 1 })
      wx.showToast({ title: `喝了 ${r.cups} 杯水 💧`, icon: 'none' })
      this.load()
    } catch (e) {
      showError(e)
    }
  },

  snapMeal(e: WechatMiniprogram.TouchEvent) {
    wx.navigateTo({ url: `/pkg/meal-photo/index?meal_type=${e.currentTarget.dataset.type}` })
  },

  openMeal(e: WechatMiniprogram.TouchEvent) {
    wx.navigateTo({ url: `/pkg/meal-edit/index?id=${e.currentTarget.dataset.id}` })
  },

  openSymptom(e: WechatMiniprogram.TouchEvent) {
    wx.navigateTo({ url: `/pkg/symptom-detail/index?id=${e.currentTarget.dataset.id}` })
  },

  async doneRoutine(e: WechatMiniprogram.TouchEvent) {
    try {
      const r = await post(`/api/routines/${e.currentTarget.dataset.id}/done`, {})
      wx.showToast({ title: r.cheer, icon: 'none' })
      this.load()
    } catch (err) {
      showError(err)
    }
  },

  goRoutines() {
    wx.switchTab({ url: '/pages/routine/index' })
  },
  goBody() {
    wx.navigateTo({ url: '/pkg/body-edit/index' })
  },
  goPlans() {
    wx.navigateTo({ url: '/pkg/plans/index' })
  },
})
