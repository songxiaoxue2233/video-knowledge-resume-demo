import { api } from './api.js'

export function toast(title) {
  uni.showToast({ title, icon: 'none', duration: 1600 })
}

export function goNoteDetail(id = 'note-001') {
  uni.navigateTo({ url: `/pages/note/detail?id=${id}` })
}

function copyDownloadUrl(url, title) {
  uni.setClipboardData({
    data: url,
    showToast: false,
    success: () => uni.showModal({
      title: '文件已生成',
      content: `${title}\n下载链接已复制。`,
      showCancel: false
    })
  })
}

export function openDownload(result, fallbackTitle = '文件已生成') {
  const url = result && result.downloadUrl
  const title = result && result.filename ? `${fallbackTitle}：${result.filename}` : fallbackTitle
  if (!url) return toast(title)

  // #ifdef H5
  window.open(url, '_blank')
  copyDownloadUrl(url, title)
  // #endif

  // #ifndef H5
  if (!/\.docx($|\?)/i.test(url)) {
    copyDownloadUrl(url, title)
    return
  }
  uni.showLoading({ title: '正在下载文件' })
  uni.downloadFile({
    url,
    success: (res) => {
      if (res.statusCode === 200) {
        uni.openDocument({
          filePath: res.tempFilePath,
          fileType: 'docx',
          showMenu: true,
          fail: () => copyDownloadUrl(url, title)
        })
      } else {
        copyDownloadUrl(url, title)
      }
    },
    fail: () => copyDownloadUrl(url, title),
    complete: () => uni.hideLoading()
  })
  // #endif
}

export function syncFeishu(ids) {
  return api.syncFeishu(ids).then((res) => {
    openDownload(res, '飞书同步文件已生成')
    return res
  }).catch((err) => { toast('同步飞书失败'); throw err })
}

export function exportWord(ids) {
  return api.exportWord(ids).then((res) => {
    openDownload(res, 'Word文件已生成')
    return res
  }).catch((err) => { toast('导出Word失败'); throw err })
}

export function exportMarkdown(ids) {
  return api.exportMarkdown(ids).then((res) => {
    openDownload(res, 'Markdown文件已生成')
    return res
  }).catch((err) => { toast('导出Markdown失败'); throw err })
}
