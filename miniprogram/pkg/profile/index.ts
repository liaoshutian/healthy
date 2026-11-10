import { get, patch, showError, uploadImage } from '../../utils/api'

Page({
  data: { form: { nickname: '', avatar_url: '', gender: '', birthday: '', height_cm: '' } as Record<string, any> },

  async onLoad() {
    try {
      const me = await get('/api/me')
      this.setData({ form: { nickname: me.nickname || '', avatar_url: me.avatar_url || '', gender: me.gender || '', birthday: me.birthday || '', height_cm: me.height_cm || '' } })
    } catch (e) {
      showError(e)
    }
  },

  async onAvatar(e: WechatMiniprogram.CustomEvent) {
    try {
      const up = await uploadImage(e.detail.avatarUrl, 'avatar')
      this.setData({ 'form.avatar_url': up.url })
    } catch (err) {
      showError(err)
    }
  },
  onNick(e: WechatMiniprogram.Input) {
    this.setData({ 'form.nickname': e.detail.value })
  },
  pickGender(e: WechatMiniprogram.TouchEvent) {
    this.setData({ 'form.gender': e.currentTarget.dataset.v })
  },
  onBirthday(e: WechatMiniprogram.PickerChange) {
    this.setData({ 'form.birthday': e.detail.value as string })
  },
  onHeight(e: WechatMiniprogram.Input) {
    this.setData({ 'form.height_cm': e.detail.value })
  },

  async save() {
    const f = this.data.form
    const body: Record<string, unknown> = { nickname: f.nickname || null }
    if (f.avatar_url) body.avatar_url = f.avatar_url
    if (f.gender) body.gender = f.gender
    if (f.birthday) body.birthday = f.birthday
    const h = parseFloat(f.height_cm)
    if (!isNaN(h)) body.height_cm = h
    try {
      getApp().globalData.me = await patch('/api/me', body)
      wx.showToast({ title: '保存好了', icon: 'none' })
      setTimeout(() => wx.navigateBack(), 600)
    } catch (e) {
      showError(e)
    }
  },
})
