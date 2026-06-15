import { describe, it, expect } from 'vitest';
import { ensureArray, extractResults } from '../utils/dataGuards';

// ============================================================
// ensureArray 测试
// ============================================================
describe('ensureArray', () => {
  describe('正常数组输入', () => {
    it('应返回原数组（非空）', () => {
      const input = [{ id: 1 }, { id: 2 }];
      expect(ensureArray(input)).toEqual(input);
    });

    it('应返回原数组（空数组）', () => {
      expect(ensureArray([])).toEqual([]);
    });

    it('应返回原数组（单元素）', () => {
      const input = [{ chapter_id: '1', title: '测试' }];
      expect(ensureArray(input)).toEqual(input);
    });
  });

  describe('非数组输入 - 应返回空数组', () => {
    it('undefined', () => {
      expect(ensureArray(undefined)).toEqual([]);
    });

    it('null', () => {
      expect(ensureArray(null)).toEqual([]);
    });

    it('普通对象', () => {
      expect(ensureArray({ chapters: [] })).toEqual([]);
    });

    it('字符串', () => {
      expect(ensureArray('not-an-array')).toEqual([]);
    });

    it('数字', () => {
      expect(ensureArray(42)).toEqual([]);
    });

    it('布尔值 true', () => {
      expect(ensureArray(true)).toEqual([]);
    });

    it('布尔值 false', () => {
      expect(ensureArray(false)).toEqual([]);
    });

    it('空对象 {}', () => {
      expect(ensureArray({})).toEqual([]);
    });
  });

  describe('API 异常响应场景', () => {
    it('API 返回错误对象 { detail: "..." }', () => {
      expect(ensureArray({ detail: '章节不存在' })).toEqual([]);
    });

    it('API 返回空响应体', () => {
      expect(ensureArray('')).toEqual([]);
    });

    it('API 返回 { data: [...] } 包装对象', () => {
      // 这种结构不会被识别为数组，返回空数组，由调用方处理
      expect(ensureArray({ data: [{ id: 1 }] })).toEqual([]);
    });
  });
});

// ============================================================
// extractResults 测试
// ============================================================
describe('extractResults', () => {
  describe('正常数组输入', () => {
    it('应返回原数组', () => {
      const input = [
        { type: 'character', title: '陆商曜' },
        { type: 'chapter', title: '第1章' },
      ];
      expect(extractResults(input)).toEqual(input);
    });

    it('应返回空数组', () => {
      expect(extractResults([])).toEqual([]);
    });
  });

  describe('null / undefined 输入', () => {
    it('null → []', () => {
      expect(extractResults(null)).toEqual([]);
    });

    it('undefined → []', () => {
      expect(extractResults(undefined)).toEqual([]);
    });
  });

  describe('非数组对象', () => {
    it('普通对象 → []', () => {
      expect(extractResults({ results: [] })).toEqual([]);
    });

    it('字符串 → []', () => {
      expect(extractResults('search-results')).toEqual([]);
    });

    it('数字 → []', () => {
      expect(extractResults(0)).toEqual([]);
    });
  });

  describe('API 响应边界场景', () => {
    it('res.data 为 undefined（网络错误等）', () => {
      expect(extractResults(undefined)).toEqual([]);
    });

    it('res.data.results 为 undefined（后端未返回 results 字段）', () => {
      // 模拟 res.data?.results 为 undefined
      expect(extractResults(undefined)).toEqual([]);
    });

    it('res.data.results 为 null', () => {
      expect(extractResults(null)).toEqual([]);
    });

    it('res.data 为 { query: "...", count: 0 }（缺少 results）', () => {
      // 模拟 res.data?.results 为 undefined
      expect(extractResults(undefined)).toEqual([]);
    });
  });
});