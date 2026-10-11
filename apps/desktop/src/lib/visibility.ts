/** 窗口隐藏 / 最小化时给 <html> 打 data-hidden：CSS 动画暂停（见 index.css「性能」） */
export function installVisibilityPause() {
  const sync = () => document.documentElement.toggleAttribute('data-hidden', document.hidden)
  sync()
  document.addEventListener('visibilitychange', sync)
}
