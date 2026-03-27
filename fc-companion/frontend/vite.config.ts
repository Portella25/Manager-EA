import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.ico', 'apple-touch-icon.png', 'mask-icon.svg'],
      manifest: {
        name: 'FC Companion',
        short_name: 'FC Companion',
        description: 'Central de Inteligência do Treinador',
        theme_color: '#0a140d',
        background_color: '#0a140d',
        display: 'standalone',
        icons: [
          {
            src: 'pwa-192x192.png',
            sizes: '192x192',
            type: 'image/png'
          },
          {
            src: 'pwa-512x512.png',
            sizes: '512x512',
            type: 'image/png'
          }
        ]
      }
    })
  ],
  server: {
    host: '0.0.0.0', // Expose to local network
    proxy: {
      '^/(api|state|feed|events|companion|career|profile|torcida|press-conference|board|crisis|season-arc|legacy|hall-of-fame|achievements|meta-achievements|market|timeline|dashboard|news|conference|finance)/.*': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      }
    }
  }
})
