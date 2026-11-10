/**
 * 一片青柠：每记一类事就点亮一瓣，点满就是“今天很完整”。中间是吉祥物「小柠」的脸。
 */
interface Petal {
  key: string
  label: string
  lit: boolean
}

Component({
  properties: {
    petals: { type: Array, value: [] as Petal[] },
    size: { type: Number, value: 420 },
  },
  observers: {
    petals() {
      this.draw()
    },
  },
  lifetimes: {
    ready() {
      this.draw()
    },
  },
  methods: {
    onTap() {
      this.triggerEvent('tap')
    },
    draw() {
      const query = this.createSelectorQuery()
      query
        .select('#c')
        .fields({ node: true, size: true })
        .exec((res) => {
          if (!res || !res[0] || !res[0].node) return
          const canvas = res[0].node as WechatMiniprogram.Canvas
          const ctx = canvas.getContext('2d') as any
          const dpr = wx.getWindowInfo().pixelRatio
          const w = res[0].width as number
          canvas.width = w * dpr
          canvas.height = w * dpr
          ctx.scale(dpr, dpr)
          this.paint(ctx, w)
        })
    },
    paint(ctx: any, w: number) {
      const petals = (this.data.petals as Petal[]) || []
      const n = petals.length || 6
      const c = w / 2
      const rRind = c - 2
      const rPith = rRind * 0.9
      const rPulp = rRind * 0.84
      const rCore = rRind * 0.2
      ctx.clearRect(0, 0, w, w)
      // 果皮
      ctx.beginPath()
      ctx.arc(c, c, rRind, 0, Math.PI * 2)
      ctx.fillStyle = '#6BAA2F'
      ctx.fill()
      // 白色内皮
      ctx.beginPath()
      ctx.arc(c, c, rPith, 0, Math.PI * 2)
      ctx.fillStyle = '#F6FBE8'
      ctx.fill()
      // 果瓣
      const gap = 0.07
      for (let i = 0; i < n; i++) {
        const lit = petals[i] ? petals[i].lit : false
        const a0 = -Math.PI / 2 + (i * 2 * Math.PI) / n + gap
        const a1 = -Math.PI / 2 + ((i + 1) * 2 * Math.PI) / n - gap
        ctx.beginPath()
        ctx.moveTo(c + Math.cos((a0 + a1) / 2) * rCore * 1.1, c + Math.sin((a0 + a1) / 2) * rCore * 1.1)
        ctx.arc(c, c, rPulp, a0, a1)
        ctx.closePath()
        if (lit) {
          const g = ctx.createRadialGradient(c, c, rCore, c, c, rPulp)
          g.addColorStop(0, '#E9F7B5')
          g.addColorStop(1, '#A8D85A')
          ctx.fillStyle = g
        } else {
          ctx.fillStyle = '#EEF2E2'
        }
        ctx.fill()
        // 果肉的小颗粒
        if (lit) {
          ctx.fillStyle = 'rgba(255,255,255,0.55)'
          const mid = (a0 + a1) / 2
          for (let k = 0; k < 3; k++) {
            const rr = rCore + (rPulp - rCore) * (0.35 + k * 0.2)
            ctx.beginPath()
            ctx.ellipse
              ? ctx.ellipse(c + Math.cos(mid) * rr, c + Math.sin(mid) * rr, 3, 6, mid, 0, Math.PI * 2)
              : ctx.arc(c + Math.cos(mid) * rr, c + Math.sin(mid) * rr, 3, 0, Math.PI * 2)
            ctx.fill()
          }
        }
      }
      // 小柠的脸
      const lit = petals.filter((p) => p.lit).length
      ctx.beginPath()
      ctx.arc(c, c, rCore, 0, Math.PI * 2)
      ctx.fillStyle = '#FFFDF6'
      ctx.fill()
      ctx.fillStyle = '#2F3A24'
      const eye = rCore * 0.13
      ctx.beginPath()
      ctx.arc(c - rCore * 0.38, c - rCore * 0.12, eye, 0, Math.PI * 2)
      ctx.arc(c + rCore * 0.38, c - rCore * 0.12, eye, 0, Math.PI * 2)
      ctx.fill()
      ctx.beginPath()
      ctx.strokeStyle = '#2F3A24'
      ctx.lineWidth = Math.max(1.5, rCore * 0.08)
      ctx.lineCap = 'round'
      const smile = lit >= n ? 0.5 : lit >= n / 2 ? 0.35 : 0.2
      ctx.arc(c, c + rCore * 0.1, rCore * 0.35, Math.PI * (0.5 - smile), Math.PI * (0.5 + smile))
      ctx.stroke()
      // 腮红
      ctx.fillStyle = 'rgba(247,160,120,0.45)'
      ctx.beginPath()
      ctx.arc(c - rCore * 0.62, c + rCore * 0.2, rCore * 0.12, 0, Math.PI * 2)
      ctx.arc(c + rCore * 0.62, c + rCore * 0.2, rCore * 0.12, 0, Math.PI * 2)
      ctx.fill()
    },
  },
})
