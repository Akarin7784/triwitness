import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import type { Plugin } from 'vite'
import { fileURLToPath } from 'node:url'
import { coreBridge } from './vite.coreBridge.ts'

// 仓库根：fixture 直接从 evals/fixtures/events 导入（?raw），不复制
const repoRoot = fileURLToPath(new URL('../..', import.meta.url))

// WebView2 / 现代浏览器都支持 woff2：去掉 fontsource 的 woff 回退，安装包少一半体积
function woff2Only(): Plugin {
  return {
    name: 'woff2-only',
    enforce: 'pre',
    transform(code, id) {
      if (!id.includes('@fontsource') || !id.endsWith('.css')) return
      return code.replace(/,\s*url\([^)]+\.woff\)\s*format\(['"]woff['"]\)/g, '')
    },
  }
}

export default defineConfig({
  plugins: [woff2Only(), react(), tailwindcss(), coreBridge(repoRoot)],
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
    fs: { allow: ['.', repoRoot] },
  },
  envPrefix: ['VITE_', 'TAURI_'],
  build: {
    target: process.env.TAURI_ENV_PLATFORM === 'windows' ? 'chrome105' : 'esnext',
    minify: !process.env.TAURI_ENV_DEBUG ? 'esbuild' : false,
    sourcemap: !!process.env.TAURI_ENV_DEBUG,
  },
})
