/**
 * 人体部位选择：正面/背面人体图点大部位 → 放大成局部 → 再点更细的位置（最多三级）。
 * 部位数据来自后端 /api/meta 的 body_parts。value: [{code, label, note}]
 */
interface PartNode {
  code: string
  label: string
  side: 'front' | 'back' | 'both'
  children?: PartNode[]
}
interface Selected {
  code: string
  label: string
  note?: string
}

// 人体图上的热区（单位 rpx，画布 320×600）
const REGIONS = [
  { id: 'head', code: 'head', side: 'both', shape: 'circle', x: 115, y: 0, w: 90, h: 96 },
  { id: 'neck', code: 'neck', side: 'both', shape: 'round', x: 140, y: 96, w: 40, h: 30 },
  { id: 'shl', code: 'shoulder', side: 'both', shape: 'circle', x: 62, y: 124, w: 56, h: 52 },
  { id: 'shr', code: 'shoulder', side: 'both', shape: 'circle', x: 202, y: 124, w: 56, h: 52 },
  { id: 'chest', code: 'chest', side: 'front', shape: 'round', x: 112, y: 128, w: 96, h: 90 },
  { id: 'abd', code: 'abdomen', side: 'front', shape: 'round', x: 112, y: 222, w: 96, h: 96 },
  { id: 'back', code: 'back', side: 'back', shape: 'round', x: 112, y: 128, w: 96, h: 110 },
  { id: 'waist', code: 'waist', side: 'back', shape: 'round', x: 112, y: 242, w: 96, h: 50 },
  { id: 'hip', code: 'hip', side: 'back', shape: 'round', x: 112, y: 296, w: 96, h: 50 },
  { id: 'arml', code: 'arm', side: 'both', shape: 'pill', x: 50, y: 180, w: 50, h: 190 },
  { id: 'armr', code: 'arm', side: 'both', shape: 'pill', x: 220, y: 180, w: 50, h: 190 },
  { id: 'thl', code: 'leg', side: 'both', shape: 'pill', x: 114, y: 350, w: 44, h: 100 },
  { id: 'thr', code: 'leg', side: 'both', shape: 'pill', x: 162, y: 350, w: 44, h: 100 },
  { id: 'knl', code: 'knee', side: 'both', shape: 'circle', x: 112, y: 452, w: 48, h: 44 },
  { id: 'knr', code: 'knee', side: 'both', shape: 'circle', x: 160, y: 452, w: 48, h: 44 },
  { id: 'cfl', code: 'leg', side: 'both', shape: 'pill', x: 116, y: 498, w: 40, h: 100 },
  { id: 'cfr', code: 'leg', side: 'both', shape: 'pill', x: 164, y: 498, w: 40, h: 100 },
  { id: 'pelvis', code: 'abdomen', side: 'front', shape: 'round', x: 112, y: 322, w: 96, h: 26 },
]

Component({
  properties: {
    parts: { type: Array, value: [] as PartNode[] },
    value: { type: Array, value: [] as Selected[] },
  },
  data: {
    side: 'front',
    regions: REGIONS,
    zoom: null as PartNode | null,
    zoomStack: [] as PartNode[],
    zoomChildren: [] as PartNode[],
    zoomTrail: '',
    selectedTop: {} as Record<string, boolean>,
    selectedCodes: {} as Record<string, boolean>,
  },
  observers: {
    value(v: Selected[]) {
      const top: Record<string, boolean> = {}
      const codes: Record<string, boolean> = {}
      v.forEach((s) => {
        top[s.code.split('.')[0]] = true
        codes[s.code] = true
      })
      this.setData({ selectedTop: top, selectedCodes: codes })
    },
  },
  methods: {
    noop() {},
    switchSide(e: WechatMiniprogram.TouchEvent) {
      this.setData({ side: e.currentTarget.dataset.side })
    },
    find(code: string): PartNode | undefined {
      return (this.data.parts as PartNode[]).find((p) => p.code === code)
    },
    openTop(e: WechatMiniprogram.TouchEvent) {
      const node = this.find(e.currentTarget.dataset.code)
      if (!node) return
      if (!node.children) {
        this.toggle({ code: node.code, label: node.label })
        return
      }
      this.showZoom([node])
    },
    showZoom(stack: PartNode[]) {
      const node = stack[stack.length - 1]
      const side = this.data.side
      const children = (node.children || []).filter((c) => c.side === 'both' || c.side === side || stack.length > 1)
      this.setData({ zoom: node, zoomStack: stack, zoomChildren: children, zoomTrail: stack.map((s) => s.label).join(' · ') })
      // 告诉页面：用户在看这个部位，可以查“上次也是这里”
      this.triggerEvent('focus', { code: node.code })
    },
    pickChild(e: WechatMiniprogram.TouchEvent) {
      const child = this.data.zoomChildren[e.currentTarget.dataset.index as number]
      if (child.children) {
        this.showZoom([...this.data.zoomStack, child])
        return
      }
      const trail = [...this.data.zoomStack, child].map((s) => s.label).join(' · ')
      this.toggle({ code: child.code, label: trail })
    },
    pickWhole() {
      const stack = this.data.zoomStack
      this.toggle({ code: stack[stack.length - 1].code, label: stack.map((s) => s.label).join(' · ') })
      this.closeZoom()
    },
    zoomBack() {
      this.showZoom(this.data.zoomStack.slice(0, -1))
    },
    closeZoom() {
      this.setData({ zoom: null, zoomStack: [], zoomChildren: [] })
    },
    toggle(sel: Selected) {
      const v = (this.data.value as Selected[]).slice()
      const i = v.findIndex((x) => x.code === sel.code)
      if (i >= 0) v.splice(i, 1)
      else v.push(sel)
      this.triggerEvent('change', { value: v })
    },
    remove(e: WechatMiniprogram.TouchEvent) {
      const v = (this.data.value as Selected[]).slice()
      v.splice(e.currentTarget.dataset.index as number, 1)
      this.triggerEvent('change', { value: v })
    },
  },
})
