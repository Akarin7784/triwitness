import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// Fonts bundled locally (offline-safe on Windows); only the weights we use (measured: Serif 500/600, Sans 400/500, Mono 400).
// CJK 字体是按字频切好的 unicode-range 切片，只下载屏幕上出现过的字所在的切片。
// 标题衬线体：GB2312 子集（scripts/subset-serif.py 生成），集外字回退到正文无衬线体
import './assets/fonts/noto-serif-sc-subset.css'
import '@fontsource/noto-sans-sc/400.css'
import '@fontsource/noto-sans-sc/500.css'
import '@fontsource/jetbrains-mono/latin-400.css'
import '@fontsource/jetbrains-mono/latin-ext-400.css'
import './index.css'
import App from './App'
import { installDesktopGuards } from './lib/desktopGuards'
import { installVisibilityPause } from './lib/visibility'
import { preloadMarkdown } from './lib/markdownLoader'

installDesktopGuards()
installVisibilityPause()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

// 首帧之后空闲时预取 Markdown 渲染器 chunk
const idle = window.requestIdleCallback ?? ((fn: () => void) => window.setTimeout(fn, 200))
idle(() => preloadMarkdown())
