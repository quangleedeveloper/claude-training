const MB = 1024 * 1024

// Mirrors the backend defaults (backend/app/core/config.py) to give feedback before
// uploading. The backend validates again and is the source of truth.
export const MEDIA_TYPES = {
  image: { extensions: [".jpg", ".jpeg", ".png", ".webp"], maxBytes: 10 * MB },
  audio: { extensions: [".mp3", ".wav", ".m4a"], maxBytes: 50 * MB },
  video: { extensions: [".mp4", ".mov", ".webm"], maxBytes: 200 * MB },
} as const

export const MAX_FILES_PER_UPLOAD = 10

export const ACCEPTED_EXTENSIONS = Object.values(MEDIA_TYPES)
  .flatMap((type) => type.extensions)
  .join(",")

export function formatBytes(bytes: number): string {
  if (bytes >= MB) {
    return `${Number((bytes / MB).toFixed(1))} MB`
  }
  return `${Math.max(1, Math.round(bytes / 1024))} KB`
}

// Splits a batch into files that can be uploaded and files rejected with a reason
export function partitionMediaFiles(chosen: File[]): {
  valid: File[]
  rejected: { filename: string; reason: string }[]
} {
  const valid: File[] = []
  const rejected: { filename: string; reason: string }[] = []
  for (const file of chosen) {
    const reason =
      valid.length >= MAX_FILES_PER_UPLOAD
        ? `At most ${MAX_FILES_PER_UPLOAD} files per upload`
        : validateMediaFile(file)
    if (reason) {
      rejected.push({ filename: file.name, reason })
    } else {
      valid.push(file)
    }
  }
  return { valid, rejected }
}

export function validateMediaFile(file: File): string | null {
  const dot = file.name.lastIndexOf(".")
  const extension = dot >= 0 ? file.name.slice(dot).toLowerCase() : ""
  for (const type of Object.values(MEDIA_TYPES)) {
    if ((type.extensions as readonly string[]).includes(extension)) {
      return file.size > type.maxBytes
        ? `Larger than the ${formatBytes(type.maxBytes)} limit`
        : null
    }
  }
  return `Unsupported file type. Supported: ${ACCEPTED_EXTENSIONS}`
}
