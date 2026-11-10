import { get, login } from './utils/api'

interface Meta {
  body_parts: any[]
  symptom_tags: string[]
  routine_templates: any[]
  plans: any[]
  petals: any[]
  metrics: any[]
  benefits: any
}

App<{ globalData: { meta: Meta | null; me: any; mealDraft: any }; loadMeta(): Promise<Meta>; loadMe(): Promise<any> }>({
  globalData: { meta: null, me: null, mealDraft: null },

  onLaunch() {
    login()
      .then(() => {
        if (!wx.getStorageSync('qn_onboarded')) wx.navigateTo({ url: '/pkg/onboarding/index' })
      })
      .catch(() => {})
    this.loadMeta().catch(() => {})
  },

  async loadMeta() {
    if (!this.globalData.meta) this.globalData.meta = await get<Meta>('/api/meta')
    return this.globalData.meta
  },

  async loadMe() {
    this.globalData.me = await get('/api/me')
    return this.globalData.me
  },
})
