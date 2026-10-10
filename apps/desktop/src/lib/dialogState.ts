/** 打开的对话框数：全局快捷键（Esc 停止等）在有对话框时让路 */
let openCount = 0
export const dialogOpen = () => openCount > 0
export function trackDialog(): () => void {
  openCount++
  return () => {
    openCount--
  }
}
