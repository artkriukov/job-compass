export function compatibilityPlainText(value: string): string {
  return value
    .replace(/\[([^\]]+)]\(https?:\/\/[^)]+\)/g, '$1')
    .replace(/[*_`]/g, '')
    .trim()
}
