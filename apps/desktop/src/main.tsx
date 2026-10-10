import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// Fonts bundled locally (offline-safe on Windows); only the weights we use.
import '@fontsource/noto-serif-sc/500.css'
import '@fontsource/noto-serif-sc/600.css'
import '@fontsource/noto-sans-sc/400.css'
import '@fontsource/noto-sans-sc/500.css'
import '@fontsource/jetbrains-mono/400.css'
import '@fontsource/jetbrains-mono/500.css'
import './index.css'
import App from './App'
import { installDesktopGuards } from './lib/desktopGuards'

installDesktopGuards()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
