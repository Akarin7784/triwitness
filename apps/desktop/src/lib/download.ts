/** 保存文件：桌面端写到“下载”文件夹并提示路径；浏览器预览走普通下载 */
import { getTransport } from '../bridge/transport'
import { textToB64 } from './attachments'
import { toast } from './toast'

export async function saveText(name: string, text: string, mime = 'text/plain'): Promise<string | null> {
  const t = await getTransport()
  try {
    const path = t ? await t.saveDownload(name, textToB64(text)) : null
    if (path) {
      toast(`已保存到 ${path}`)
      return path
    }
  } catch (e) {
    toast(`保存失败：${e instanceof Error ? e.message : String(e)}`)
    return null
  }
  const url = URL.createObjectURL(new Blob([text], { type: `${mime};charset=utf-8` }))
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 4000)
  toast(`已下载 ${name}`)
  return name
}

export async function copyText(text: string, ok = '已复制') {
  try {
    await navigator.clipboard.writeText(text)
    toast(ok)
  } catch {
    toast('复制失败')
  }
}
