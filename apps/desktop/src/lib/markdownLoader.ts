/** Markdown 渲染器 chunk 的加载器（react-markdown + remark-gfm 不进主包） */
export const loadMarkdownRenderer = () => import('../components/MarkdownRenderer')

/** 启动后空闲时预取，第一条消息出现前通常已就绪 */
export function preloadMarkdown() {
  void loadMarkdownRenderer()
}
