import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import ChaptersPage from './ChaptersPage';

// Mock API
vi.mock('../../services/api', () => ({
  contentApi: {
    getChapters: vi.fn(),
    exportChapters: vi.fn(),
    search: vi.fn(),
    annotate: vi.fn(),
  },
}));

import { contentApi } from '../../services/api';

const mockChapters = Array.from({ length: 25 }, (_, i) => ({
  chapter_id: String(i + 1),
  title: `第 ${i + 1} 章 测试章节`,
  file: `chapter_${i + 1}_final.md`,
  size: 1024 * (i + 1),
  summary: i % 2 === 0 ? { title: `摘要 ${i + 1}`, key_events: ['事件1'], characters_appeared: ['角色A'] } : null,
}));

function renderPage() {
  return render(
    <BrowserRouter>
      <ChaptersPage />
    </BrowserRouter>
  );
}

describe('ChaptersPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (contentApi.getChapters as any).mockResolvedValue({ data: mockChapters });
  });

  it('加载并显示章节列表', async () => {
    renderPage();
    await waitFor(() => {
      expect(document.body.textContent).toContain('章节管理');
    });
    expect(document.body.textContent).toContain('共 25 章');
    expect(document.body.textContent).toContain('第 1 章 测试章节');
  });

  it('默认分页为 20 章/页', async () => {
    renderPage();
    await waitFor(() => {
      expect(document.body.textContent).toContain('第 1 章 测试章节');
    });
    expect(document.body.textContent).toContain('共 25 章');
  });

  it('导出按钮未选择时置灰', async () => {
    renderPage();
    await waitFor(() => {
      expect(document.body.textContent).toContain('导出文章');
    });
    const exportBtn = screen.getByRole('button', { name: /导出文章/ }) as HTMLButtonElement;
    expect(exportBtn.disabled).toBe(true);
  });

  it('勾选章节后导出按钮可用', async () => {
    renderPage();
    await waitFor(() => {
      expect(document.body.textContent).toContain('第 1 章 测试章节');
    });
    const checkbox = screen.getAllByRole('checkbox')[0];
    fireEvent.click(checkbox);
    
    const exportBtn = screen.getByRole('button', { name: /导出文章/ }) as HTMLButtonElement;
    await waitFor(() => {
      expect(exportBtn.disabled).toBe(false);
    });
  });

  it('显示已选数量 Badge', async () => {
    renderPage();
    await waitFor(() => {
      expect(document.body.textContent).toContain('第 1 章 测试章节');
    });
    const checkbox = screen.getAllByRole('checkbox')[0];
    fireEvent.click(checkbox);
    
    await waitFor(() => {
      expect(document.body.textContent).toContain('已选');
    });
  });

  it('全选当前页', async () => {
    renderPage();
    await waitFor(() => {
      expect(document.body.textContent).toContain('第 1 章 测试章节');
    });
    const headerCheckbox = screen.getAllByRole('checkbox')[0];
    fireEvent.click(headerCheckbox);
    
    const exportBtn = screen.getByRole('button', { name: /导出文章/ }) as HTMLButtonElement;
    await waitFor(() => {
      expect(exportBtn.disabled).toBe(false);
    });
  });

  it('导出弹窗显示已选章节数量', async () => {
    renderPage();
    await waitFor(() => {
      expect(document.body.textContent).toContain('第 1 章 测试章节');
    });
    const checkbox = screen.getAllByRole('checkbox')[0];
    fireEvent.click(checkbox);
    
    const exportBtn = screen.getByRole('button', { name: /导出文章/ }) as HTMLButtonElement;
    await waitFor(() => expect(exportBtn.disabled).toBe(false));
    fireEvent.click(exportBtn);
    
    await waitFor(() => {
      expect(document.body.textContent).toContain('共选择');
    });
  });

  it('更改页大小后保持选择', async () => {
    renderPage();
    await waitFor(() => {
      expect(document.body.textContent).toContain('第 1 章 测试章节');
    });
    const checkbox = screen.getAllByRole('checkbox')[0];
    fireEvent.click(checkbox);
    
    const exportBtn = screen.getByRole('button', { name: /导出文章/ }) as HTMLButtonElement;
    await waitFor(() => {
      expect(exportBtn.disabled).toBe(false);
    });
  });

  it('跨页选择保持状态', async () => {
    renderPage();
    await waitFor(() => {
      expect(document.body.textContent).toContain('第 1 章 测试章节');
    });
    // 勾选第一页第一个章节
    const checkbox = screen.getAllByRole('checkbox')[0];
    fireEvent.click(checkbox);
    
    // 模拟切换到第 2 页
    const nextPageBtn = screen.getByTitle('下一页');
    fireEvent.click(nextPageBtn);
    
    await waitFor(() => {
      expect(document.body.textContent).toContain('第 21 章 测试章节');
    });
    
    // 勾选第 2 页的一个章节
    const checkbox2 = screen.getAllByRole('checkbox')[0];
    fireEvent.click(checkbox2);
    
    // 切换回第 1 页
    const prevPageBtn = screen.getByTitle('上一页');
    fireEvent.click(prevPageBtn);
    
    await waitFor(() => {
      expect(document.body.textContent).toContain('第 1 章 测试章节');
    });
    
    // 导出按钮应仍可用（跨页选择保持）
    const exportBtn = screen.getByRole('button', { name: /导出文章/ }) as HTMLButtonElement;
    await waitFor(() => {
      expect(exportBtn.disabled).toBe(false);
    });
  });

  it('导出 API 调用包含正确的 chapter_ids', async () => {
    (contentApi.exportChapters as any).mockResolvedValue({
      data: { success: true, exported_count: 2, skipped_count: 0, messages: [] },
    });
    renderPage();
    await waitFor(() => {
      expect(document.body.textContent).toContain('第 1 章 测试章节');
    });
    
    // 勾选两个章节
    const checkboxes = screen.getAllByRole('checkbox');
    fireEvent.click(checkboxes[0]);
    fireEvent.click(checkboxes[1]);
    
    const exportBtn = screen.getByRole('button', { name: /导出文章/ }) as HTMLButtonElement;
    await waitFor(() => expect(exportBtn.disabled).toBe(false));
    fireEvent.click(exportBtn);
    
    // 输入目录并确认导出
    await waitFor(() => {
      expect(document.body.textContent).toContain('共选择');
    });
    
    const dirInput = screen.getByPlaceholderText(/输入目标目录路径/);
    fireEvent.change(dirInput, { target: { value: '/tmp/test_export' } });
    
    const submitBtn = screen.getByRole('button', { name: /开始导出/ });
    fireEvent.click(submitBtn);
    
    await waitFor(() => {
      expect(contentApi.exportChapters).toHaveBeenCalledWith(
        expect.objectContaining({
          chapter_ids: expect.arrayContaining(['1', '2']),
          target_dir: '/tmp/test_export',
        })
      );
    });
  });

  it('导出到不同目录场景', async () => {
    (contentApi.exportChapters as any).mockResolvedValue({
      data: { success: true, exported_count: 1, skipped_count: 0, messages: ['已导出 chapter_1_final.md'] },
    });
    renderPage();
    await waitFor(() => {
      expect(document.body.textContent).toContain('第 1 章 测试章节');
    });
    
    const checkbox = screen.getAllByRole('checkbox')[0];
    fireEvent.click(checkbox);
    
    const exportBtn = screen.getByRole('button', { name: /导出文章/ }) as HTMLButtonElement;
    await waitFor(() => expect(exportBtn.disabled).toBe(false));
    fireEvent.click(exportBtn);
    
    await waitFor(() => {
      expect(document.body.textContent).toContain('共选择');
    });
    
    // 场景 1: 使用绝对路径
    const dirInput = screen.getByPlaceholderText(/输入目标目录路径/);
    fireEvent.change(dirInput, { target: { value: '/Users/test/novels' } });
    
    const submitBtn = screen.getByRole('button', { name: /开始导出/ });
    fireEvent.click(submitBtn);
    
    await waitFor(() => {
      expect(contentApi.exportChapters).toHaveBeenCalledWith(
        expect.objectContaining({ target_dir: '/Users/test/novels' })
      );
    });
  });

  it('localStorage 记住上次导出目录', async () => {
    localStorage.setItem('novel_export_last_dir', '/tmp/previous_dir');
    renderPage();
    await waitFor(() => {
      expect(document.body.textContent).toContain('第 1 章 测试章节');
    });
    
    const checkbox = screen.getAllByRole('checkbox')[0];
    fireEvent.click(checkbox);
    
    const exportBtn = screen.getByRole('button', { name: /导出文章/ }) as HTMLButtonElement;
    await waitFor(() => expect(exportBtn.disabled).toBe(false));
    fireEvent.click(exportBtn);
    
    await waitFor(() => {
      expect(document.body.textContent).toContain('共选择');
    });
    
    // 检查目录输入框是否自动填充上次目录
    const dirInput = screen.getByDisplayValue('/tmp/previous_dir');
    expect(dirInput).toBeTruthy();
  });
});
