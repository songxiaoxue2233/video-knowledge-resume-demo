const STORAGE_KEY = 'vk_local_notes'

export function getLocalNotes() {
  return uni.getStorageSync(STORAGE_KEY) || []
}

export function saveLocalNotes(notes) {
  uni.setStorageSync(STORAGE_KEY, notes)
}

export function findLocalNote(id) {
  return getLocalNotes().find((note) => note.id === id)
}
