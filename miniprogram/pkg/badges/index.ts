import { get, showError } from '../../utils/api'

Page({
  data: { badges: [] as any[] },
  async onLoad() {
    try {
      this.setData({ badges: await get('/api/me/badges') })
    } catch (e) {
      showError(e)
    }
  },
})
