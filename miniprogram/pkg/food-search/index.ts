import { get, showError } from '../../utils/api'

let timer: number | undefined

Page({
  data: {
    q: '',
    cat: '',
    list: [] as any[],
    cats: [
      { key: '', label: '全部' },
      { key: 'staple', label: '主食' },
      { key: 'meat', label: '肉' },
      { key: 'fish', label: '鱼虾' },
      { key: 'egg', label: '蛋' },
      { key: 'soy', label: '豆制品' },
      { key: 'veg', label: '蔬菜' },
      { key: 'fruit', label: '水果' },
      { key: 'dairy', label: '奶' },
      { key: 'drink', label: '饮料' },
      { key: 'snack', label: '零食' },
      { key: 'oil', label: '油' },
      { key: 'nuts', label: '坚果' },
    ],
    picking: false,
  },

  onLoad(q: Record<string, string | undefined>) {
    this.setData({ picking: !!q.pick })
    this.load()
  },

  onInput(e: WechatMiniprogram.Input) {
    this.setData({ q: e.detail.value })
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => this.load(), 250) as unknown as number
  },

  pickCat(e: WechatMiniprogram.TouchEvent) {
    this.setData({ cat: e.currentTarget.dataset.key })
    this.load()
  },

  async load() {
    try {
      const params: Record<string, string> = { q: this.data.q }
      if (this.data.cat) params.category = this.data.cat
      this.setData({ list: await get('/api/foods/search', params) })
    } catch (e) {
      showError(e)
    }
  },

  pick(e: WechatMiniprogram.TouchEvent) {
    const food = this.data.list[e.currentTarget.dataset.index as number]
    if (this.data.picking) {
      const channel = this.getOpenerEventChannel ? this.getOpenerEventChannel() : null
      if (channel && channel.emit) channel.emit('pick', food)
      wx.navigateBack()
      return
    }
    getApp().globalData.mealDraft = { items: [{ food_id: food.id, name: food.name, category: food.category, grams: food.unit_grams, unit_name: food.unit_name, unit_count: 1, kcal: 0, display: '', estimated: false }] }
    wx.redirectTo({ url: '/pkg/meal-edit/index?draft=1' })
  },
})
