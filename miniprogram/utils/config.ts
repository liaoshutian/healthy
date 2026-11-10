// 后端地址。开发者工具里勾选“不校验合法域名”即可连本地后端。
const { miniProgram } = wx.getAccountInfoSync()

export const API_BASE =
  miniProgram.envVersion === 'develop' ? 'http://localhost:8000' : 'https://api.rexliao.cn'

// 订阅消息模板 ID，和后端 WX_TMPL_ROUTINE 保持一致（在小程序后台申请后填写）；规律小事和吃药提醒共用
export const TMPL_ROUTINE = 'neMAvVxEK1crzbttU9OOFdmTbRNXJXwZCUOGBU0vaos'
