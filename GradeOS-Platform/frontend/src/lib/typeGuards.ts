/**
 * 类型守卫函数 - 用于运行时类型检查和转换
 * 
 * 这些函数提供了安全的方式来处理来自 API 的 unknown 类型数据
 */

export type UnknownRecord = Record<string, unknown>;

/**
 * 将任何值转换为 Record<string, unknown>
 * 如果不是对象，返回空对象
 */
export const asRecord = (value: unknown): UnknownRecord =>
    value && typeof value === 'object' ? (value as UnknownRecord) : {};

/**
 * 将任何值转换为数组
 * 如果不是数组，返回空数组
 */
export const asArray = <T,>(value: unknown): T[] =>
    Array.isArray(value) ? (value as T[]) : [];

/**
 * 将任何值转换为数字
 * 如果转换失败，返回 fallback 值
 */
export const asNumber = (value: unknown, fallback = 0) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
};

/**
 * 将任何值转换为字符串数组
 * 过滤掉非字符串元素
 */
export const asStringArray = (value: unknown): string[] =>
    asArray<unknown>(value).filter((item): item is string => typeof item === 'string');

/**
 * 将任何值转换为数字数组
 * 过滤掉非数字元素
 */
export const asNumberArray = (value: unknown): number[] =>
    asArray<unknown>(value).filter((item): item is number => typeof item === 'number');
