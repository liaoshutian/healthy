Component({
  data: {
    selected: 0,
    list: [
      { path: '/pages/today/index', text: '今日', icon: '🍋' },
      { path: '/pages/data/index', text: '数据', icon: '📅' },
      { path: '/pages/record/index', text: '记一下', icon: '', center: true },
      { path: '/pages/routine/index', text: '规律', icon: '⏰' },
      { path: '/pages/mine/index', text: '我的', icon: '🙂' },
    ],
  },
  methods: {
    go(e: WechatMiniprogram.TouchEvent) {
      const i = e.currentTarget.dataset.index as number
      wx.switchTab({ url: this.data.list[i].path })
    },
  },
})
