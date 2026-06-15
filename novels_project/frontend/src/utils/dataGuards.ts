/**
 * 数据类型校验工具函数
 *
 * 用于防御 API 返回非预期数据结构导致的运行时错误。
 */

/**
 * 确保值为数组，非数组值返回空数组。
 * 用于防御 API 返回非数组的章节列表、暗线列表等场景。
 */
export function ensureArray<T = unknown>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

/**
 * 从 API 响应中安全提取 results 数组。
 * 适用于全局搜索 API 返回的 { results: [...] } 结构。
 */
export function extractResults(value: unknown): unknown[] {
  if (value == null) return [];
  if (Array.isArray(value)) return value;
  return [];
}