import { render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import MemoryManagement from './MemoryManagement';
import { memoryConfigApi } from '../../services/api';

vi.mock('../../services/api');

test('slider clamps out‑of‑range chapterWindow to valid preset index', async () => {
  // Mock API returns a chapter_window not in the preset list
  (memoryConfigApi.get as jest.Mock).mockResolvedValue({
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

  // Wait for the component to finish loading the config
  await waitFor(() => expect(screen.getByLabelText(/章节滑动窗口/i)).toBeInTheDocument());

  const slider = screen.getByRole('slider');
  // The slider uses values 1‑10 (preset count). 1500 -> Math.round(1500/100)=15 -> clamped to 9 -> displayed as 10
  expect(slider).toHaveAttribute('aria-valuenow', '10');
});
