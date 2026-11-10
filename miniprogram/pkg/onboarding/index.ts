import { get, patch, post, showError } from '../../utils/api'

const heights: number[] = []
for (let h = 140; h <= 210; h++) heights.push(h)

Page({
  data: {
    step: 0,
    intro: [
      { icon: '📄', title: '拍报告', desc: '拍一张 InBody 报告，20 多项指标自动录入' },
      { icon: '🍱', title: '拍饭', desc: '拍一下就知道吃了几碗饭、几只鸡翅' },
      { icon: '⏰', title: '记规律', desc: '理发、换牙刷、体检，到时间了提醒你' },
    ],
    gender: '',
    birthday: '',
    heights,
    heightIndex: 25,
    play: 'casual',
    templates: [] as any[],
    picked: {} as Record<number, boolean>,
  },

  async onLoad() {
    try {
      this.setData({ templates: await get('/api/routines/templates') })
    } catch (e) {
      /* 离线时跳过 */
    }
  },

  next() {
    if (this.data.step === 2 && this.data.play === 'challenge') {
      // 先把最后一步走完，再去挑卡
      this.setData({ step: 3 })
      return
    }
    this.setData({ step: this.data.step + 1 })
  },

  pickGender(e: WechatMiniprogram.TouchEvent) {
    this.setData({ gender: e.currentTarget.dataset.v })
  },
  pickBirthday(e: WechatMiniprogram.PickerChange) {
    this.setData({ birthday: e.detail.value as string })
  },
  pickHeight(e: WechatMiniprogram.PickerChange) {
    this.setData({ heightIndex: Number(e.detail.value) })
  },
  pickPlay(e: WechatMiniprogram.TouchEvent) {
    this.setData({ play: e.currentTarget.dataset.v })
  },
  pickTemplate(e: WechatMiniprogram.TouchEvent) {
    const i = e.currentTarget.dataset.index as number
    this.setData({ [`picked.${i}`]: !this.data.picked[i] })
  },

  goInbody() {
    wx.navigateTo({ url: '/pkg/body-edit/index?mode=inbody' })
  },

  async saveBasic() {
    const body: Record<string, unknown> = { height_cm: heights[this.data.heightIndex] }
    if (this.data.gender) body.gender = this.data.gender
    if (this.data.birthday) body.birthday = this.data.birthday
    try {
      await patch('/api/me', body)
      this.next()
    } catch (e) {
      showError(e)
    }
  },

  async saveRoutines() {
    try {
      const picked = this.data.templates.filter((_: any, i: number) => this.data.picked[i])
      for (const t of picked) await post('/api/routines', t)
    } catch (e) {
      showError(e)
    }
    this.finish()
  },

  async finish() {
    try {
      await patch('/api/me', { onboarded: true })
    } catch (e) {
      /* 下次再标记 */
    }
    wx.setStorageSync('qn_onboarded', true)
    if (this.data.play === 'challenge') wx.redirectTo({ url: '/pkg/plans/index' })
    else wx.switchTab({ url: '/pages/today/index' })
  },
})
