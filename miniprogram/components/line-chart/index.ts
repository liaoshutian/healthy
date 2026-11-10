/** 极简折线图：原始点 + 7 日移动平均。数据少时画点，不引入第三方图表库。 */
interface Point {
  date: string
  value: number
}

Component({
  properties: {
    points: { type: Array, value: [] as Point[] },
    average: { type: Array, value: [] as number[] },
    unit: { type: String, value: '' },
    height: { type: Number, value: 360 },
  },
  observers: {
    'points, average'() {
      this.draw()
    },
  },
  lifetimes: {
    ready() {
      this.draw()
    },
  },
  methods: {
    draw() {
      this.createSelectorQuery()
        .select('#c')
        .fields({ node: true, size: true })
        .exec((res) => {
          if (!res || !res[0] || !res[0].node) return
          const canvas = res[0].node as WechatMiniprogram.Canvas
          const ctx = canvas.getContext('2d') as any
          const dpr = wx.getWindowInfo().pixelRatio
          const w = res[0].width as number
          const h = res[0].height as number
          canvas.width = w * dpr
          canvas.height = h * dpr
          ctx.scale(dpr, dpr)
          this.paint(ctx, w, h)
        })
    },
    paint(ctx: any, w: number, h: number) {
      const pts = this.data.points as Point[]
      const avg = this.data.average as number[]
      ctx.clearRect(0, 0, w, h)
      if (!pts.length) {
        ctx.fillStyle = '#8A9479'
        ctx.font = '13px sans-serif'
        ctx.textAlign = 'center'
        ctx.fillText('还没有数据，记一次就有曲线啦', w / 2, h / 2)
        return
      }
      const pad = { l: 36, r: 12, t: 16, b: 24 }
      const values = pts.map((p) => p.value).concat(avg)
      let min = Math.min(...values)
      let max = Math.max(...values)
      if (max - min < 1) {
        max += 0.5
        min -= 0.5
      }
      const span = max - min
      min -= span * 0.1
      max += span * 0.1
      const t0 = new Date(pts[0].date).getTime()
      const t1 = new Date(pts[pts.length - 1].date).getTime()
      const x = (d: string) => (t1 === t0 ? (pad.l + w - pad.r) / 2 : pad.l + ((new Date(d).getTime() - t0) / (t1 - t0)) * (w - pad.l - pad.r))
      const y = (v: number) => pad.t + (1 - (v - min) / (max - min)) * (h - pad.t - pad.b)
      // 网格
      ctx.strokeStyle = '#EDF0E2'
      ctx.fillStyle = '#8A9479'
      ctx.font = '10px sans-serif'
      ctx.lineWidth = 1
      for (let i = 0; i <= 3; i++) {
        const v = min + ((max - min) * i) / 3
        const yy = y(v)
        ctx.beginPath()
        ctx.moveTo(pad.l, yy)
        ctx.lineTo(w - pad.r, yy)
        ctx.stroke()
        ctx.textAlign = 'right'
        ctx.fillText(v.toFixed(1), pad.l - 4, yy + 3)
      }
      ctx.textAlign = 'left'
      ctx.fillText(pts[0].date.slice(5, 10), pad.l, h - 6)
      ctx.textAlign = 'right'
      ctx.fillText(pts[pts.length - 1].date.slice(5, 10), w - pad.r, h - 6)
      // 原始数据
      ctx.strokeStyle = 'rgba(125,190,60,0.45)'
      ctx.lineWidth = 1.5
      ctx.beginPath()
      pts.forEach((p, i) => (i ? ctx.lineTo(x(p.date), y(p.value)) : ctx.moveTo(x(p.date), y(p.value))))
      ctx.stroke()
      ctx.fillStyle = '#7DBE3C'
      pts.forEach((p) => {
        ctx.beginPath()
        ctx.arc(x(p.date), y(p.value), 2.5, 0, Math.PI * 2)
        ctx.fill()
      })
      // 7 日平均
      if (avg.length === pts.length && pts.length > 2) {
        ctx.strokeStyle = '#5E9E2A'
        ctx.lineWidth = 2.5
        ctx.beginPath()
        pts.forEach((p, i) => (i ? ctx.lineTo(x(p.date), y(avg[i])) : ctx.moveTo(x(p.date), y(avg[i]))))
        ctx.stroke()
      }
    },
  },
})
