import { render, screen, waitFor } from '@testing-library/react';
import { vi, test, expect } from 'vitest';
import MemoryManagement from './MemoryManagement';
import { memoryConfigApi } from '../../services/api';

vi.mock('../../services/api');

test('slider clamps out‑of‑range chapterWindow to valid preset index', async () => {
  // Mock API returns a chapter_window not in the preset list
  (memoryConfigApi.get as vi.Mock).mockResolvedValue({
    data: {
      agent_id: 'main',
      config: { chapter_window: 1500 }, // out of preset range
      global_config: {
        chapter_window: 100,
        max_summary_blocks: 5,
        dialogue_compression_threshold: 0.75,
      },
    },
  });

  render(<MemoryManagement />);

  // 等待组件完成加载
  await waitFor(() =>
    expect(screen.queryAllByRole('slider').length).toBeGreaterThanOrEqual(2),
  );

  // 第一个 Slider 是“摘要滑动窗口”
  const sliders = screen.queryAllByRole('slider');
  const slider = sliders[0];
  // The slider's value is 0‑indexed (max 9). 1500 -> Math.round(1500/100)=15 -> clamped to 9.
  expect(slider).toHaveAttribute('aria-valuenow', '9');
});
