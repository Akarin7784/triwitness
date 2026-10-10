/**
 * 交给核心的“用户设置”（UI-21 第 3 轮）：个人资料 + 风格 + 项目说明拼成一段纯文本（--guidance-file）。
 * 核心把它放在任务描述前；空的部分不写。纯函数，便于测试。
 */
import { PRESET_STYLES, type Prefs } from './prefs'
import type { Project } from './projects'

export function stylePrompt(p: Pick<Prefs, 'style' | 'customStyles'>): { name: string; prompt: string } | null {
  const preset = PRESET_STYLES.find((s) => s.id === p.style)
  if (preset) return preset.prompt ? { name: preset.name, prompt: preset.prompt } : null
  const c = p.customStyles.find((s) => s.id === p.style)
  return c && c.prompt.trim() ? { name: c.name, prompt: c.prompt.trim() } : null
}

export function buildGuidance(p: Pick<Prefs, 'name' | 'about' | 'style' | 'customStyles'>, project?: Project): string {
  const parts: string[] = []
  const who: string[] = []
  if (p.name.trim()) who.push(`称呼：${p.name.trim()}`)
  if (p.about.trim()) who.push(`偏好：${p.about.trim()}`)
  if (who.length) parts.push(`### 关于用户\n${who.join('\n')}`)
  const st = stylePrompt(p)
  if (st) parts.push(`### 回答风格（${st.name}）\n${st.prompt}`)
  if (project) {
    const head = `### 项目：${project.name}`
    const body = [project.description.trim(), project.instructions.trim()].filter(Boolean).join('\n\n')
    if (body || project.knowledge.length) {
      const files = project.knowledge.length ? `\n知识文件：${project.knowledge.map((k) => k.name).join('、')}（见附件）` : ''
      parts.push(`${head}\n${body}${files}`.trim())
    }
  }
  return parts.join('\n\n')
}
