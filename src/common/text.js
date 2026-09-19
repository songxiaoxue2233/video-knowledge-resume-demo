const MOJIBAKE_PATTERN = /(ï¿½|锟斤拷|鏂|瑙|绗|灏|鎶|鐭|銆|锛|鈥|�)/

export function isBadText(value) {
  const text = String(value || '').trim()
  if (!text) return false
  const questionRuns = (text.match(/\?{2,}/g) || []).join('').length
  const questionRatio = questionRuns / Math.max(text.length, 1)
  return MOJIBAKE_PATTERN.test(text) || questionRuns >= 3 || questionRatio > 0.06
}

export function cleanText(value, fallback = '') {
  const text = String(value || '').trim()
  if (!text || isBadText(text)) return fallback
  return text
}

export function cleanNote(note = {}) {
  const title = cleanText(note.title, '解析异常，请重新解析')
  const summary = cleanText(note.summary, '这条笔记内容出现编码异常，建议重新提交链接解析。')
  const theory = cleanText(note.theory, '后台还没有返回可用的结构化笔记。')
  const tag = Array.isArray(note.tags) && note.tags.length ? cleanText(note.tags[0], '未分类') : cleanText(note.category, '未分类')
  return { ...note, title, summary, theory, tag }
}

export function isDisplayableNote(note = {}) {
  const title = String(note.title || '').trim()
  const summary = String(note.summary || '').trim()
  const theory = String(note.theory || '').trim()
  const sourceUrl = String(note.source_url || '').trim()
  const text = `${title} ${summary} ${theory}`
  if (isBadText(text)) return false
  const onlyUrl = /^https?:\/\//.test(title) || /^https?:\/\//.test(summary) || /^https?:\/\//.test(theory)
  const repeatedMeta = theory && (theory === title || theory === summary)
  const tooThin = theory.length < 80 && summary.length < 60
  return !(onlyUrl || repeatedMeta || (sourceUrl && tooThin))
}

export function formatCompactTime(value) {
  if (!value) return ''
  const date = value instanceof Date ? value : new Date(String(value).replace(' ', 'T'))
  if (Number.isNaN(date.getTime())) return String(value).replace(/:\d{2}$/, '')
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hour = String(date.getHours()).padStart(2, '0')
  const minute = String(date.getMinutes()).padStart(2, '0')
  return `${month}-${day} ${hour}:${minute}`
}
