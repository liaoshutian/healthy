import { get, post, showError } from '../../utils/api'
import { selectTab } from '../../utils/tab'
import { guessMealType, MEAL_LABELS, md } from '../../utils/util'

Page({
  data: {
    actions: [
      { key: 'food', icon: '📸', title: '拍食物', desc: '拍一下就知道吃了几碗饭', manual: true },
      { key: 'inbody', icon: '📄', title: '拍体测报告', desc: 'InBody 报告自动录入', manual: true },
      { key: 'weight', icon: '⚖️', title: '记体重', desc: '称一称，看曲线', manual: false },
      { key: 'water', icon: '💧', title: '喝一杯水', desc: '点一下加一杯', manual: false },
      { key: 'routine', icon: '⏰', title: '记一件规律事', desc: '理发、换牙刷、体检…', manual: false },
      { key: 'symptom', icon: '🩹', title: '记不适与用药', desc: '哪里不舒服、吃了什么药', manual: false },
    ],
    text: '',
    recent: [] as any[],
  },

  onShow() {
    selectTab(this, 2)
    this.loadRecent()
  },

  async loadRecent() {
    try {
      const rows = await get('/api/meals/recent')
      this.setData({ recent: rows.map((r: any) => ({ ...r, when: `${md(r.date)} ${MEAL_LABELS[r.meal_type]}` })) })
    } catch (e) {
      /* 首次没有记录时忽略 */
    }
  },

  async go(e: WechatMiniprogram.TouchEvent) {
    const key = e.currentTarget.dataset.key as string
    switch (key) {
      case 'food':
        return wx.navigateTo({ url: '/pkg/meal-photo/index' })
      case 'inbody':
        return wx.navigateTo({ url: '/pkg/body-edit/index?mode=inbody' })
      case 'weight':
        return wx.navigateTo({ url: '/pkg/body-edit/index?mode=weight' })
      case 'routine':
        return wx.switchTab({ url: '/pages/routine/index' })
      case 'symptom':
        return wx.navigateTo({ url: '/pkg/symptom-edit/index' })
      case 'water':
        try {
          const r = await post('/api/water', { delta: 1 })
          wx.showToast({ title: `今天第 ${r.cups} 杯水 💧`, icon: 'none' })
        } catch (err) {
          showError(err)
        }
    }
  },

  goManual(e: WechatMiniprogram.TouchEvent) {
    const key = e.currentTarget.dataset.key as string
    if (key === 'food') wx.navigateTo({ url: '/pkg/meal-edit/index' })
    else wx.navigateTo({ url: '/pkg/body-edit/index?mode=manual' })
  },

  onText(e: WechatMiniprogram.Input) {
    this.setData({ text: e.detail.value })
  },

  async parseText() {
    const text = this.data.text.trim()
    if (!text) return
    wx.showLoading({ title: '小柠在看…' })
    try {
      const draft = await post('/api/meals/parse-text', { text })
      wx.hideLoading()
      if (draft.fallback) {
        wx.showToast({ title: draft.message, icon: 'none' })
        return wx.navigateTo({ url: '/pkg/food-search/index' })
      }
      getApp().globalData.mealDraft = { ...draft, source: 'text' }
      this.setData({ text: '' })
      wx.navigateTo({ url: '/pkg/meal-edit/index?draft=1' })
    } catch (err) {
      wx.hideLoading()
      showError(err)
    }
  },

  async copy(e: WechatMiniprogram.TouchEvent) {
    try {
      await post(`/api/meals/${e.currentTarget.dataset.id}/copy`, { meal_type: guessMealType() })
      wx.showToast({ title: '记好啦，和上次一样', icon: 'none' })
    } catch (err) {
      showError(err)
    }
  },
})
