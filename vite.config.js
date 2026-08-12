import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  root: path.resolve(__dirname, 'frontend'),
  plugins: [react()],
  build: {
    outDir: path.resolve(__dirname, 'frontend/dist'),
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return
          if (id.includes('katex')) return 'katex'
          if (
            id.includes('highlight.js') ||
            id.includes('lowlight') ||
            id.includes('rehype-highlight')
          )
            return 'highlight'
          if (
            id.includes('react-markdown') ||
            id.includes('remark') ||
            id.includes('rehype') ||
            id.includes('micromark') ||
            id.includes('mdast') ||
            id.includes('/unist') ||
            id.includes('hast') ||
            id.includes('property-information') ||
            id.includes('/vfile') ||
            id.includes('/bail') ||
            id.includes('/trough') ||
            id.includes('/devlop') ||
            id.includes('/decode-named-character-reference')
          )
            return 'markdown'
          if (id.includes('force-graph') || id.includes('/d3-')) return 'force-graph'
          if (
            /node_modules\/react\//.test(id) ||
            id.includes('react-dom') ||
            id.includes('react-router') ||
            id.includes('/scheduler/')
          )
            return 'react-vendor'
          if (id.includes('@tanstack')) return 'query'
        },
      },
    },
  },
})
