// 生产构建保持关闭；仅在明确设置 VITE_USE_MOCK_FALLBACK=1 时启用。
export const USE_MOCK_FALLBACK = import.meta.env.VITE_USE_MOCK_FALLBACK === '1'

// Docker 生产环境使用 /backend 反向代理，本地构建仍连接 8787。
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8787'
