export function pad(n: number) {
  return n < 10 ? '0' + n : '' + n
}

export function ymd(d: Date = new Date()) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

export function md(s: string) {
  const d = new Date(s.length <= 10 ? s.replace(/-/g, '/') : s)
  return `${d.getMonth() + 1}月${d.getDate()}日`
}

export function hm(s: string) {
  const d = new Date(s)
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export function greeting() {
  const h = new Date().getHours()
  if (h < 6) return '夜深了'
  if (h < 11) return '早上好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
}

export const MEAL_LABELS: Record<string, string> = { breakfast: '早餐', lunch: '午餐', dinner: '晚餐', snack: '加餐' }

export function guessMealType() {
  const h = new Date().getHours()
  if (h >= 5 && h < 10) return 'breakfast'
  if (h >= 10 && h < 15) return 'lunch'
  if (h >= 17 && h < 21) return 'dinner'
  return 'snack'
}

export function chooseImage(sourceType: ('album' | 'camera')[] = ['camera', 'album']): Promise<string> {
  return new Promise((resolve, reject) => {
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType,
      sizeType: ['compressed'],
      success: (r) => resolve(r.tempFiles[0].tempFilePath),
      fail: reject,
    })
  })
}

/** 请求一次性订阅消息，返回用户同意的条数。 */
export function askSubscribe(tmplId: string): Promise<number> {
  if (!tmplId) return Promise.resolve(0)
  return new Promise((resolve) => {
    wx.requestSubscribeMessage({
      tmplIds: [tmplId],
      success: (r) => resolve((r as Record<string, string>)[tmplId] === 'accept' ? 1 : 0),
      fail: () => resolve(0),
    })
  })
}

/** 敏感信息授权：health=体成分，medical=病历用药。 */
export function ensureConsent(kind: 'health' | 'medical', consented: boolean): Promise<boolean> {
  if (consented) return Promise.resolve(true)
  const text =
    kind === 'health'
      ? '体重、体脂等身体数据属于敏感个人信息。我们只用它来给你画曲线和做解读，图片私有存储，你可以随时删除或注销账号。'
      : '病历、用药和身体不适记录属于敏感医疗健康信息。我们只帮你记录和整理，不做诊断；图片私有存储，可一键删除。'
  return new Promise((resolve) => {
    wx.showModal({
      title: kind === 'health' ? '健康数据授权' : '敏感信息授权',
      content: text,
      confirmText: '同意',
      cancelText: '再想想',
      success: async (r) => {
        if (!r.confirm) return resolve(false)
        const { post } = require('./api') as typeof import('./api')
        await post('/api/me/consent', { kind })
        resolve(true)
      },
    })
  })
}
