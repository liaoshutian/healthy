import { get, post, showError } from '../../utils/api'

Page({
  data: { plans: [] as any[], current: null as any, recommend: null as any },

  onShow() {
    this.load()
  },

  async load() {
    try {
      const [plans, challenges, recommend] = await Promise.all([get('/api/plans'), get('/api/challenges'), get('/api/plans/recommend').catch(() => null)])
      this.setData({
        plans: plans.map((p: any) => ({ ...p, stars: '★'.repeat(p.difficulty) + '☆'.repeat(3 - p.difficulty) })),
        current: challenges.find((c: any) => c.status === 'active' || c.status === 'paused') || null,
        recommend,
      })
    } catch (e) {
      showError(e)
    }
  },

  start(e: WechatMiniprogram.TouchEvent) {
    const code = e.currentTarget.dataset.code as string
    const trial = !!e.currentTarget.dataset.trial
    const plan = this.data.plans.find((p: any) => p.code === code)
    const go = async () => {
      try {
        await post('/api/challenges', { plan_code: code, trial })
        wx.showToast({ title: `${plan.icon} 开始玩${plan.name}啦`, icon: 'none' })
        setTimeout(() => wx.switchTab({ url: '/pages/today/index' }), 800)
      } catch (err) {
        showError(err)
      }
    }
    const tips = [plan.caution, this.data.current ? `现在的「${this.data.current.plan.name}」会先停下，不算失败。` : ''].filter(Boolean).join('\n')
    if (tips) wx.showModal({ title: '开始之前', content: tips, confirmText: '开始', success: (r) => r.confirm && go() })
    else go()
  },

  async act(e: WechatMiniprogram.TouchEvent) {
    try {
      await post(`/api/challenges/${this.data.current.id}/action`, { action: e.currentTarget.dataset.action })
      this.load()
    } catch (err) {
      showError(err)
    }
  },
})
