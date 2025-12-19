import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  
  // 開発サーバーの最適化
  server: {
    host: true, // ネットワークからのアクセスを許可
    port: 5173,
    strictPort: false,
    // HMR（Hot Module Replacement）の最適化
    hmr: {
      overlay: true,
    },
    // ファイル監視の最適化
    watch: {
      // node_modulesやbackendディレクトリを監視対象から除外
      ignored: ['**/node_modules/**', '**/backend/**', '**/.git/**'],
    },
  },
  
  // ビルドの最適化
  build: {
    // ソースマップを無効化して高速化
    sourcemap: false,
    // チャンクサイズの警告を500kbに設定
    chunkSizeWarningLimit: 500,
    rollupOptions: {
      output: {
        // 手動でチャンク分割
        manualChunks: {
          'react-vendor': ['react', 'react-dom'],
        },
      },
    },
  },
  
  // 依存関係の最適化
  optimizeDeps: {
    include: ['react', 'react-dom', 'lucide-react'],
    exclude: [],
  },
  
  // プレビューサーバーの設定
  preview: {
    port: 4173,
    strictPort: false,
  },
});
