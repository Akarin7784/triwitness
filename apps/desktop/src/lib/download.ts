/** 保存文件：桌面端写到“下载”文件夹并提示路径；浏览器预览走普通下载 */
import { getTransport } from '../bridge/transport'
import { textToB64 } from './attachments'
import { toast } from './toast'
import { t as tr } from './i18n'

export async function saveText(name: string, text: string, mime = 'text/plain'): Promise<string | null> {
  const t = await getTransport()
  try {
    const path = t ? await t.saveDownload(name, textToB64(text)) : null
    if (path) {
      toast(tr('已保存到 {0}', path))
      return path
    }
  } catch (e) {
    toast(tr('保存失败：{0}', e instanceof Error ? e.message : String(e)))
    return null
  }
  const url = URL.createObjectURL(new Blob([text], { type: `${mime};charset=utf-8` }))
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 4000)
  toast(tr('已下载 {0}', name))
  return name
}

export async function copyText(text: string, ok = tr('已复制')) {
  try {
    await navigator.clipboard.writeText(text)
    toast(ok)
  } catch {
    toast(tr('复制失败'))
  }
}
