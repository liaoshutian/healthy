import { get, showError } from '../../utils/api'
import { selectTab } from '../../utils/tab'
import { md, pad, ymd } from '../../utils/util'

interface Cell {
  key: string
  day: string
  date: string
  today: boolean
  meals: number
  body: boolean
  routine: string
  sick: boolean
}

Page({
  data: {
    tab: 'calendar',
    year: 0,
    month: 0,
    cells: [] as Cell[],
    metrics: [
      { key: 'weight_kg', label: '体重' },
      { key: 'body_fat_pct', label: '体脂率' },
      { key: 'skeletal_muscle_kg', label: '骨骼肌' },
      { key: 'visceral_fat_level', label: '内脏脂肪' },
      { key: 'kcal', label: '每日热量' },
    ],
    ranges: [
      { key: 'week', label: '周' },
      { key: 'month', label: '月' },
      { key: '3m', label: '3 月' },
      { key: 'year', label: '年' },
      { key: 'all', label: '全部' },
    ],
    metric: 'weight_kg',
    range: 'month',
    trend: {} as any,
    day: null as any,
    dayTitle: '',
    dayEmpty: false,
  },

  onLoad() {
    const now = new Date()
    this.setData({ year: now.getFullYear(), month: now.getMonth() + 1 })
  },

  onShow() {
    selectTab(this, 1)
    this.data.tab === 'calendar' ? this.loadCalendar() : this.loadTrend()
  },

  noop() {},

  switchTab(e: WechatMiniprogram.TouchEvent) {
    const tab = e.currentTarget.dataset.tab as string
    this.setData({ tab })
    tab === 'calendar' ? this.loadCalendar() : this.loadTrend()
  },

  async loadCalendar() {
    const { year, month } = this.data
    try {
      const res = await get('/api/calendar', { year, month })
      const first = new Date(year, month - 1, 1)
      const blanks = (first.getDay() + 6) % 7 // 周一开头
      const daysInMonth = new Date(year, month, 0).getDate()
      const today = ymd()
      const cells: Cell[] = []
      for (let i = 0; i < blanks; i++) cells.push({ key: 'b' + i, day: '', date: '', today: false, meals: 0, body: false, routine: '', sick: false })
      for (let d = 1; d <= daysInMonth; d++) {
        const date = `${year}-${pad(month)}-${pad(d)}`
        const info = res.days[date] || {}
        cells.push({
          key: date,
          day: String(d),
          date,
          today: date === today,
          meals: info.meals || 0,
          body: !!info.body,
          routine: info.routines && info.routines.length ? info.routines[0].icon : '',
          sick: !!info.sick,
        })
      }
      this.setData({ cells })
    } catch (e) {
      showError(e)
    }
  },

  prevMonth() {
    let { year, month } = this.data
    month -= 1
    if (month < 1) {
      month = 12
      year -= 1
    }
    this.setData({ year, month })
    this.loadCalendar()
  },

  nextMonth() {
    let { year, month } = this.data
    month += 1
    if (month > 12) {
      month = 1
      year += 1
    }
    this.setData({ year, month })
    this.loadCalendar()
  },

  async openDay(e: WechatMiniprogram.TouchEvent) {
    const date = e.currentTarget.dataset.date as string
    if (!date) return
    try {
      const day = await get('/api/calendar/day', { day: date })
      const empty = !day.meals.length && !day.water && !day.body.length && !day.routines.length && !day.symptom_updates.length
      this.setData({ day, dayTitle: md(date), dayEmpty: empty })
    } catch (err) {
      showError(err)
    }
  },

  closeDay() {
    this.setData({ day: null })
  },

  openMeal(e: WechatMiniprogram.TouchEvent) {
    wx.navigateTo({ url: `/pkg/meal-edit/index?id=${e.currentTarget.dataset.id}` })
  },

  async loadTrend() {
    try {
      const trend = await get('/api/trends', { metric: this.data.metric, range: this.data.range })
      this.setData({ trend })
    } catch (e) {
      showError(e)
    }
  },

  pickMetric(e: WechatMiniprogram.TouchEvent) {
    this.setData({ metric: e.currentTarget.dataset.key })
    this.loadTrend()
  },

  pickRange(e: WechatMiniprogram.TouchEvent) {
    this.setData({ range: e.currentTarget.dataset.key })
    this.loadTrend()
  },

  goMember() {
    wx.navigateTo({ url: '/pkg/member/index' })
  },
})
