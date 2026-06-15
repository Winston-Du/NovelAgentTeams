# 前端 Lint 规范（lint‑guidelines.md）

> 本文档汇总了 `novels_project/frontend` 项目在 ESLint 与 TypeScript 检查中遇到的常见错误、修复示例以及依赖同步流程，供团队成员参考。  
> 每次出现新的问题或新规则时，请更新本文件并同步至 CI 流程。

## 1. 常见 ESLint 错误与修复

### 1.1. 缺少 `react/jsx-key`

**触发**：在数组中直接渲染组件而未指定 `key`。  
**修复**：为每个元素提供唯一 `key`（通常使用业务 ID）。

```tsx
// ❌ 错误
actions={[
  <Button>保存</Button>,
]}

// ✅ 正确
actions={[
  <Button key={agent.id}>保存</Button>,
]}
```

---

### 1.2. `no‑constant‑condition` 死循环

**触发**：使用 `while (true)` 或类似的永不终止的循环。  
**修复**：加入明确的退出条件或 `break`。

```tsx
// ❌ 错误
while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  // …
}

// ✅ 正确
while (!abortController.signal.aborted) {
  const { done, value } = await reader.read();
  if (done) break;
  // …
}
```

---

### 1.3. `react/no-unescaped-entities` 双引号未转义

**触发**：在 JSX 文本中直接使用 `"`、'``、`>` 等字符。  
**修复**：使用对应的 HTML 实体或 `{'…'}` 包裹。

```tsx
// ❌ 错误
<Text>例如："帮我创作第3章"</Text>

// ✅ 正确
<Text>例如：&quot;帮我创作第3章&quot;</Text>
// 或
<Text>{"例如：\"帮我创作第3章\""}</Text>
```

---

### 1.4. `no‑explicit‑any` 大量使用 `any`

**触发**：在 TypeScript 中使用 `any` 会削弱类型安全。  
**修复**：使用 `unknown` + 类型守卫，或精确的类型定义。

```ts
// ❌ 错误
} catch (e: any) {
  message.error(e?.message);
}

// ✅ 正确
} catch (e: unknown) {
  const err = e as { message?: string };
  message.error(err?.message ?? '未知错误');
}
```

---

### 1.5. `react-hooks/exhaustive-deps` 依赖缺失

**触发**：`useEffect`、`useCallback` 等 Hook 缺少必要的依赖。  
**修复**：将所有在闭包内使用的外部变量加入依赖数组；如果不需要响应，可使用 `useRef` 或提取到组件外部。

```ts
// ❌ 错误
useEffect(() => {
  loadSettings();
}, []); // missing dep `loadSettings`

// ✅ 正确
useEffect(() => {
  loadSettings();
}, [loadSettings]);
```

---

## 2. 测试框架相关错误

### 2.1. `ReferenceError: jest is not defined`

**根因**：项目使用 **Vitest**，但测试文件中使用了 Jest API。  
**修复**：

```ts
// 替换前（Jest 语法）
jest.mock('../../services/api');
(api.get as jest.Mock).mockResolvedValue(...);

// 替换后（Vitest 语法）
import { vi, test, expect } from 'vitest';
vi.mock('../../services/api');
(api.get as vi.Mock).mockResolvedValue(...);
```

### 2.2. `ReferenceError: test is not defined`

**根因**：未显式导入 Vitest 的全局函数。  
**修复**：

```ts
import { test, expect } from 'vitest';
```

---

### 2.3. Vitest DOM matchers 未生效（`Invalid Chai property: toHaveAttribute`）

**根因**：`@testing-library/jest-dom` 提供 `toHaveAttribute`、`toBeInTheDocument` 等扩展断言，需要在 Vitest 中显式启用：

1. 在 `vitest.config.ts` 开启 `globals: true`（让 `expect` 注入全局），  
2. 在 `src/test-setup.ts` 顶部 `import '@testing-library/jest-dom'`。

**正确配置示例**：

```ts
// vitest.config.ts
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    include: ['src/**/*.test.{ts,tsx}'],
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
    globals: true,           // ← 必须开启
  },
});
```

```ts
// src/test-setup.ts
import '@testing-library/jest-dom';   // ← 必须放在最前
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

afterEach(() => cleanup());
// ...polyfills...
```

**错误现象**：`Error: Invalid Chai property: toHaveAttribute`  
**修复**：按上述方式配置后，DOM matchers 即可使用。

---

## 3. 依赖同步检查

### 3.1. 删除插件需同步配置

- 在 `package.json` 中删除插件后，务必同步修改 `.eslintrc.json` 中对应的 `plugins` 与 `rules`。
- 例子：移除 `eslint-plugin-antd` 时：

```diff
- "plugins": ["antd", "react", "react-hooks", "@typescript-eslint"]
+ "plugins": ["react", "react-hooks", "@typescript-eslint"]

- "antd/no-deprecated": "error",
- "antd/no-empty-block": "warn",
- "antd/no-unused-prop": "warn",
```

### 3.2. 检查插件可用性

```bash
# 确认插件是否真的存在
npm view eslint-plugin-antd versions --json | tail -5

# 验证本地依赖树
npm ls eslint-plugin-antd
```

如果返回 “No matching version found”，请在删除插件前先确认升级或更换为可用的版本。

---

## 4. 配置热重载与防越界

### 4.1. Slider 索引越界防护

```ts
// ❌ 错误（无钳制）
: Math.round(chapterWindow / 100)

// ✅ 正确
: Math.max(0, Math.min(9, Math.round(chapterWindow / 100)))
```

> 目的：保证返回值始终落在 `WINDOW_PRESETS` 索引 0‑9 之内。

### 4.2. 文件末尾换行

- 文本文件（`.ts`, `.tsx`, `.json`, `.md` 等）应以换行符结尾。
- 建议在编辑器中开启 “Insert final newline” 选项。

---

## 5. CI 与本地执行

### 5.1. 本地全量检查

```bash
cd novels_project/frontend
./node_modules/.bin/eslint . --ext .ts,.tsx --max-warnings 0
npm test --silent
```

### 5.2. CI 推荐

- 拉取 PR 时自动执行 `npm run lint` + `npm test`。
- 若 `max-warnings 0` 过于严格，可改为 `max-warnings 50` 作为阈值。

---

## 5.3. `package.json` 推荐的脚本

为保持规范在团队中可复用，建议在 `package.json` 中显式声明严格 lint 脚本（可与 `lint` 区分）：

```json
{
  "scripts": {
    "lint": "eslint . --ext .ts,.tsx",
    "lint:strict": "eslint . --ext .ts,.tsx --max-warnings 0",
    "test": "vitest run",
    "test:watch": "vitest"
  }
}
```

- `npm run lint` —— 普通 lint 检查，允许 warning。  
- `npm run lint:strict` —— 严格检查，常用于 CI。  
- `npm test` / `npm run test:watch` —— 单元/组件测试。

---

## 6. 常见错误清单（供 PR 检查）

| 类别 | 错误码 | 备注 |
|------|--------|------|
| React | `react/jsx-key` | 列表元素必须提供 `key` |
| React | `react/no-unescaped-entities` | JSX 文本中双/单引号需转义 |
| JS  | `no-constant-condition` | 避免 `while (true)` 等永真循环 |
| TypeScript | `@typescript-eslint/no-explicit-any` | 禁止 `any`（警告） |
| TypeScript | `@typescript-eslint/no-unused-vars` | 清理未使用的导入/变量 |
| React Hooks | `react-hooks/exhaustive-deps` | 确保 `useEffect`/`useCallback` 依赖完整 |
| 测试 | `ReferenceError: jest is not defined` | 使用 Vitest 时改用 `vi` |
| 测试 | `ReferenceError: test is not defined` | 显式导入 `test`/`expect` |

---

## 7. 如何为本指南做贡献

1. 遇到新的 Lint/编译错误时，先在文档对应章节添加 “错误描述 + 示例 + 修复”。  
2. 提交 PR 时附带复现的 `npm test` / `npm run lint` 截图或日志。  
3. 合并后更新 `CHANGELOG.md`，标注本指南的版本。

---

*文档维护者：开发组*  
*最后更新：2026‑06‑15*
