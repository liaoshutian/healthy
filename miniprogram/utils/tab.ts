/** 在 tab 页 onShow 里调用，高亮自定义 tabBar。 */
export function selectTab(page: WechatMiniprogram.Page.Instance<any, any>, index: number) {
  const bar = (page as any).getTabBar?.()
  if (bar) bar.setData({ selected: index })
}
