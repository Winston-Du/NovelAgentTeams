import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { message } from 'antd';
import MemoryManagement from './MemoryManagement';

// Mock API
vi.mock('../../services/api', () => ({
  memoryConfigApi: {
    get: vi.fn(),
    update: vi.fn(),
    reset: vi.fn(),
  },
}));

import { memoryConfigApi } from '../../services/api';

const mockConfig = {
  agent_id: 'plot_writer',
  has_override: true,
  config: {
    chapter_window: 300,
    max_summary_blocks: 3,
    summary_max_chars: 2000,
    dialogue_compression_threshold: 0.8,
    preserve_recent_messages: 4,
    dialogue_summary_max_chars: 4000,
    dialogue_context_summary_max_chars: 1500,
    dialogue_compression_max_retries: 2,
    subagent_compression_enabled: true,
    subagent_max_messages: 30,
    auto_compaction_threshold: 100000,
  },
  global_config: {
    chapter_window: 100,
    max_summary_blocks: 3,
    summary_max_chars: 2000,
    dialogue_compression_threshold: 0.8,
    preserve_recent_messages: 4,
    dialogue_summary_max_chars: 4000,
    dialogue_context_summary_max_chars: 1500,
    dialogue_compression_max_retries: 2,
    subagent_compression_enabled: true,
    subagent_max_messages: 30,
    auto_compaction_threshold: 100000,
  },
};

beforeEach(() => {
  vi.clearAllMocks();
  (memoryConfigApi.get as any).mockResolvedValue({ data: mockConfig });
  (memoryConfigApi.update as any).mockResolvedValue({ data: { status: 'updated' } });
  (memoryConfigApi.reset as any).mockResolvedValue({ data: { status: 'reset' } });
  // 静默 message 错误输出
  vi.spyOn(message, 'error').mockImplementation(() => undefined as any);
  vi.spyOn(message, 'success').mockImplementation(() => undefined as any);
  vi.spyOn(message, 'info').mockImplementation(() => undefined as any);
});

describe('MemoryManagement', () => {
  it('渲染并加载默认 plot_writer agent 配置', async () => {
    render(<MemoryManagement />);
    await waitFor(() => {
      expect(document.body.textContent).toContain('记忆管理');
    });
    expect(document.body.textContent).toContain('已自定义');
  });

  it('显示 4 个 Agent 标签页', async () => {
    render(<MemoryManagement />);
    await waitFor(() => {
      expect(document.body.textContent).toContain('剧情撰写');
    });
    expect(document.body.textContent).toContain('资深校对');
    expect(document.body.textContent).toContain('人物设计');
  });

  it('显示 4 个统计卡片', async () => {
    render(<MemoryManagement />);
    await waitFor(() => {
      expect(document.body.textContent).toContain('当前滑窗');
    });
    expect(document.body.textContent).toContain('300');     // chapter_window
    expect(document.body.textContent).toContain('保留摘要块');
    expect(document.body.textContent).toContain('压缩阈值');
    expect(document.body.textContent).toContain('80%');      // 0.8 * 100
    expect(document.body.textContent).toContain('自动压缩触发');
  });

  it('点击 [重置为默认] 触发 reset API', async () => {
    render(<MemoryManagement />);
    await waitFor(() => {
      expect(screen.getByText('重置为默认')).toBeTruthy();
    });
    fireEvent.click(screen.getByText('重置为默认'));
    await waitFor(() => {
      expect(memoryConfigApi.reset).toHaveBeenCalledWith('plot_writer');
    });
  });

  it('点击 [保存] 触发 update API（仅提交修改字段）', async () => {
    render(<MemoryManagement />);
    await waitFor(() => {
      expect(screen.getByText('保存')).toBeTruthy();
    });
    // 找到「保留最近消息数」InputNumber 并修改
    const inputs = screen.getAllByRole('spinbutton');
    // 找 preserve_recent_messages - 找到 value=4 的那个
    const preserveInput = inputs.find((el) => (el as HTMLInputElement).value === '4') as HTMLInputElement;
    expect(preserveInput).toBeTruthy();
    fireEvent.change(preserveInput, { target: { value: '8' } });

    fireEvent.click(screen.getByText('保存'));
    await waitFor(() => {
      expect(memoryConfigApi.update).toHaveBeenCalled();
    });
    const callArgs = (memoryConfigApi.update as any).mock.calls[0];
    expect(callArgs[0]).toBe('plot_writer');
    expect(callArgs[1]).toEqual({ preserve_recent_messages: 8 });
  });

  it('未修改时点击 [保存] 不调用 update API', async () => {
    render(<MemoryManagement />);
    await waitFor(() => {
      expect(screen.getByText('保存')).toBeTruthy();
    });
    fireEvent.click(screen.getByText('保存'));
    // 调用后未发现 update
    await new Promise((r) => setTimeout(r, 50));
    expect(memoryConfigApi.update).not.toHaveBeenCalled();
  });

  it('配置加载失败时显示错误提示', async () => {
    (memoryConfigApi.get as any).mockRejectedValueOnce(new Error('网络错误'));
    render(<MemoryManagement />);
    await waitFor(() => {
      expect(message.error).toHaveBeenCalled();
    });
    expect(document.body.textContent).toContain('暂无配置数据');
  });

  it('受控模式: 传入 agentId 时禁用 Tabs', async () => {
    (memoryConfigApi.get as any).mockResolvedValue({
      data: { ...mockConfig, agent_id: 'main' },
    });
    render(<MemoryManagement agentId="main" />);
    await waitFor(() => {
      expect(document.body.textContent).toContain('记忆管理');
    });
    // 受控模式下不应出现 4 个 Tab
    expect(document.body.textContent).not.toContain('剧情撰写');
  });
});
