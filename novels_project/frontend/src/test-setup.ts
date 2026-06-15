/**
 * Vitest 全局 setup
 * 解决 antd 在 jsdom 环境下的 polyfill 缺失问题
 */
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

// 每个测试后自动清理 DOM
afterEach(() => {
  cleanup();
});

// ResizeObserver polyfill（antd Tabs/Slider 等需要）
(globalThis as any).ResizeObserver = class {
  observe() { /* noop */ }
  unobserve() { /* noop */ }
  disconnect() { /* noop */ }
};

// matchMedia polyfill（antd Grid 组件需要）
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => { /* noop */ },
    removeListener: () => { /* noop */ },
    addEventListener: () => { /* noop */ },
    removeEventListener: () => { /* noop */ },
    dispatchEvent: () => false,
  }),
});

// IntersectionObserver polyfill（部分组件需要）
(globalThis as any).IntersectionObserver = class {
  root = null;
  rootMargin = '';
  thresholds = [];
  observe() { /* noop */ }
  unobserve() { /* noop */ }
  disconnect() { /* noop */ }
  takeRecords() { return []; }
};
