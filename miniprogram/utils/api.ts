import { API_BASE } from './config'

const TOKEN_KEY = 'qn_token'

export interface ApiError {
  status: number
  message: string
}

let loginPromise: Promise<string> | null = null

function wxLogin(): Promise<string> {
  return new Promise((resolve, reject) => {
    wx.login({ success: (r) => resolve(r.code), fail: reject })
  })
}

/** 静默登录：wx.login 拿 code 换自己的 token。并发请求只登录一次。 */
export function login(force = false): Promise<string> {
  const cached = wx.getStorageSync(TOKEN_KEY) as string
  if (cached && !force) return Promise.resolve(cached)
  if (loginPromise) return loginPromise
  loginPromise = wxLogin()
    .then((code) => rawRequest<{ token: string; onboarded: boolean }>('POST', '/api/auth/login', { code }, ''))
    .then((res) => {
      wx.setStorageSync(TOKEN_KEY, res.token)
      wx.setStorageSync('qn_onboarded', res.onboarded)
      return res.token
    })
    .finally(() => {
      loginPromise = null
    })
  return loginPromise
}

function rawRequest<T>(method: string, path: string, data: unknown, token: string): Promise<T> {
  return new Promise((resolve, reject) => {
    wx.request({
      url: API_BASE + path,
      method: method as 'GET',
      data: data as WechatMiniprogram.IAnyObject,
      // AI 识别会依次尝试两家模型（各最多 40 秒），客户端要等得比服务端久
      timeout: 95000,
      header: token ? { Authorization: `Bearer ${token}` } : {},
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data as T)
        } else {
          const body = res.data as { detail?: unknown }
          const detail = typeof body?.detail === 'string' ? body.detail : '出了点小问题，稍后再试'
          reject({ status: res.statusCode, message: detail } as ApiError)
        }
      },
      fail: () => reject({ status: 0, message: '网络不太好，稍后再试' } as ApiError),
    })
  })
}

export async function request<T = any>(method: string, path: string, data?: unknown): Promise<T> {
  const token = await login()
  try {
    return await rawRequest<T>(method, path, data, token)
  } catch (e) {
    const err = e as ApiError
    if (err.status === 401) {
      wx.removeStorageSync(TOKEN_KEY)
      const t = await login(true)
      return rawRequest<T>(method, path, data, t)
    }
    throw err
  }
}

export const get = <T = any>(path: string, data?: unknown) => request<T>('GET', path, data)
export const post = <T = any>(path: string, data?: unknown) => request<T>('POST', path, data)
export const put = <T = any>(path: string, data?: unknown) => request<T>('PUT', path, data)
export const patch = <T = any>(path: string, data?: unknown) => request<T>('PATCH', path, data)
export const del = <T = any>(path: string) => request<T>('DELETE', path)

/** 上传一张图片，返回 {id, url}。 */
export async function uploadImage(filePath: string, kind: string): Promise<{ id: number; url: string }> {
  const token = await login()
  return new Promise((resolve, reject) => {
    wx.uploadFile({
      url: API_BASE + '/api/uploads',
      filePath,
      name: 'file',
      formData: { kind },
      header: { Authorization: `Bearer ${token}` },
      success: (res) => {
        if (res.statusCode === 200) resolve(JSON.parse(res.data))
        else reject({ status: res.statusCode, message: '图片上传失败' })
      },
      fail: () => reject({ status: 0, message: '图片上传失败，检查一下网络' }),
    })
  })
}

/** 统一的错误提示。402=会员权益，428=需要授权。 */
export function showError(e: unknown) {
  const err = e as ApiError
  if (err?.status === 402) {
    wx.showModal({
      title: '这是 Pro 的小福利',
      content: err.message,
      confirmText: '看看会员',
      success: (r) => r.confirm && wx.navigateTo({ url: '/pkg/member/index' }),
    })
    return
  }
  wx.showToast({ title: err?.message || '出了点小问题', icon: 'none' })
}
