import { useEffect, useState, useCallback, useRef } from 'react';
import {
  Card, Typography, Tag, Space, Button, Switch, Input, Radio,
  Modal, message, Table, Select,
} from 'antd';
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table';
import {
  EyeOutlined, SearchOutlined, SendOutlined,
  ArrowDownOutlined, ArrowUpOutlined, RobotOutlined,
  DownloadOutlined, FolderOpenOutlined, BulbOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { contentApi, agentSessionsApi } from '../../services/api';
import { ensureArray, extractResults } from '../../utils/dataGuards';

const { Title, Text, Paragraph } = Typography;

// ============================================================
// localStorage 持久化
// ============================================================
const LS_PAGE_SIZE = 'novel_export_page_size';
const LS_LAST_DIR = 'novel_export_last_dir';

function getStoredPageSize(): number {
  const v = localStorage.getItem(LS_PAGE_SIZE);
  return v ? parseInt(v, 10) : 20;
}
function setStoredPageSize(size: number) {
  localStorage.setItem(LS_PAGE_SIZE, String(size));
}
function getStoredLastDir(): string {
  return localStorage.getItem(LS_LAST_DIR) || '';
}
function setStoredLastDir(dir: string) {
  localStorage.setItem(LS_LAST_DIR, dir);
}

// ============================================================
// 文件选择器 Hook
// ============================================================
function useDirectoryPicker() {
  const pickDirectory = useCallback(async (): Promise<string | null> => {
    const picker = (window as any).showDirectoryPicker;
    if (!picker) return null;
    try {
      const handle = await picker({ mode: 'readwrite' });
      // 获取目录路径（通过 FileSystemDirectoryHandle 的 name 属性）
      // 注意：出于安全原因，浏览器不会返回完整路径，只返回目录名
      // 因此我们需要回退到手动输入
      return handle.name;
    } catch {
      return null;
    }
  }, []);
  return { pickDirectory, supported: !!(window as any).showDirectoryPicker };
}

// ============================================================
// 主组件
// ============================================================
interface Chapter {
  chapter_id: string;
  title: string;
  file: string;
  size: number;
  summary?: {
    chapter_id?: number;
    title?: string;
    summary?: string;
    key_events?: string[];
    characters_appeared?: string[];
  };
}

export default function ChaptersPage() {
  const navigate = useNavigate();

  // 章节数据
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [loading, setLoading] = useState(false);
  const [ascending, setAscending] = useState(true);

  // 分页状态
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(getStoredPageSize());

  // 选择状态 - 使用 Set 保证 O(1) 查询
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // 搜索状态
  const [searchMode, setSearchMode] = useState<'character' | 'fulltext'>('fulltext');
  const [searchQuery, setSearchQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<any[] | null>(null);
  const [hasSearched, setHasSearched] = useState(false);
  const [resultAscending, setResultAscending] = useState(true);

  // Agent 对话状态
  const [agentInput, setAgentInput] = useState('');
  const [agentMessages, setAgentMessages] = useState<{ role: string; content: string }[]>([]);
  const [agentSending, setAgentSending] = useState(false);
  const [agentExpanded, setAgentExpanded] = useState(false);
  const [agentSessionId, setAgentSessionId] = useState<string | null>(
    localStorage.getItem('novel_agent_session_id'),
  );
  const agentAbortRef = useRef<AbortController | null>(null);

  // 导出弹窗状态
  const [exportModalVisible, setExportModalVisible] = useState(false);
  const [exportTargetDir, setExportTargetDir] = useState(getStoredLastDir());
  const [exportOverwrite, setExportOverwrite] = useState(false);
  const [exporting, setExporting] = useState(false);

  // 文件选择器
  const { pickDirectory, supported: dirPickerSupported } = useDirectoryPicker();

  // 加载章节列表
  useEffect(() => {
    setLoading(true);
    console.log('[ChaptersPage] fetchChapters: 开始请求章节列表');
    contentApi.getChapters()
      .then(res => {
        console.log('[ChaptersPage] fetchChapters: 原始响应类型', typeof res.data, '是否为数组', Array.isArray(res.data));
        console.log('[ChaptersPage] fetchChapters: 原始响应数据', res.data);
        const validated = ensureArray(res.data) as Chapter[];
        console.log('[ChaptersPage] fetchChapters: 校验后数据长度', validated.length);

        // 调试：检查第一个章节的数据结构
        if (validated.length > 0) {
          const first = validated[0];
          console.log('[ChaptersPage] 第一个章节数据:', {
            chapter_id: first.chapter_id,
            title: first.title,
            summaryExists: !!first.summary,
            summaryType: typeof first.summary,
            summaryContent: first.summary?.summary,
            summaryTitle: first.summary?.title,
          });
        }

        setChapters(validated);
      })
      .catch(err => {
        console.error('[ChaptersPage] fetchChapters: 请求失败', err);
        setChapters([]);
      })
      .finally(() => setLoading(false));

    // 组件卸载时取消进行中的 Agent 请求
    return () => {
      if (agentAbortRef.current) {
        agentAbortRef.current.abort();
        agentAbortRef.current = null;
      }
    };
  }, []);

  // 排序后的章节
  const sortedChapters = [...chapters].sort((a, b) => {
    const aNum = parseInt(a.chapter_id, 10) || 0;
    const bNum = parseInt(b.chapter_id, 10) || 0;
    return ascending ? aNum - bNum : bNum - aNum;
  });

  // 当前页的章节
  const startIndex = (currentPage - 1) * pageSize;
  const paginatedChapters = sortedChapters.slice(startIndex, startIndex + pageSize);

  // 已选数量
  const selectedCount = selectedIds.size;

  // 选择处理
  const handleSelectChange = useCallback((selectedRowKeys: React.Key[]) => {
    const newSet = new Set(selectedRowKeys as string[]);
    console.log('[ChaptersPage] handleSelectChange: 选择变更', {
      selectedCount: newSet.size,
      selectedIds: Array.from(newSet),
    });
    setSelectedIds(newSet);
  }, []);

  const handleSelectAllChange = useCallback((selected: boolean) => {
    console.log('[ChaptersPage] handleSelectAllChange: 全选变更', {
      selected,
      pageChapterIds: paginatedChapters.map(c => c.chapter_id),
    });
    setSelectedIds(prev => {
      const next = new Set(prev);
      paginatedChapters.forEach(c => {
        if (selected) next.add(c.chapter_id);
        else next.delete(c.chapter_id);
      });
      console.log('[ChaptersPage] handleSelectAllChange: 选择状态更新', {
        beforeCount: prev.size,
        afterCount: next.size,
      });
      return next;
    });
  }, [paginatedChapters]);

  // 分页处理
  const handlePageChange = useCallback((page: number, size?: number) => {
    console.log('[ChaptersPage] handlePageChange: 分页变更', {
      fromPage: currentPage,
      toPage: page,
      newPageSize: size,
      selectedCount: selectedIds.size,
      selectedIds: Array.from(selectedIds),
    });
    setCurrentPage(page);
    if (size && size !== pageSize) {
      setPageSize(size);
      setStoredPageSize(size);
      setCurrentPage(1);
      console.log('[ChaptersPage] handlePageChange: 页大小变更，重置到第1页');
    }
  }, [pageSize, currentPage, selectedIds]);

  // 搜索
  const handleSearch = async () => {
    const q = searchQuery.trim();
    if (!q) return;
    console.log('[ChaptersPage] handleSearch: 开始搜索, 关键词:', q);
    setSearching(true);
    setSearchResults(null);
    setHasSearched(true);
    try {
      const res = await contentApi.search(q);
      console.log('[ChaptersPage] handleSearch: 原始响应类型', typeof res.data);
      console.log('[ChaptersPage] handleSearch: 原始响应数据', res.data);
      const rawResults = res.data?.results;
      console.log('[ChaptersPage] handleSearch: results 字段类型', typeof rawResults, '是否为数组', Array.isArray(rawResults));
      const validated = extractResults(rawResults);
      console.log('[ChaptersPage] handleSearch: 校验后结果数量', validated.length);
      setSearchResults(validated);
    } catch (err) {
      console.error('[ChaptersPage] handleSearch: 搜索失败', err);
      message.error('搜索失败');
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  };

  // Agent - 使用统一会话 API（Phase 2）
  const handleAgentSend = async () => {
    const sendStartTime = Date.now();
    const text = agentInput.trim();
    if (!text) return;

    // [LOG] 发送开始
    console.log('[Agent] handleTurn:START', {
      timestamp: new Date().toISOString(),
      inputLength: text.length,
      inputPreview: text.slice(0, 50),
      hasExistingSession: !!agentSessionId,
      existingAbortController: !!agentAbortRef.current,
    });

    // 取消之前的请求（如果有）
    if (agentAbortRef.current) {
      console.log('[Agent] handleTurn:ABORT_PREVIOUS', {
        reason: 'new_request_started',
        previousAbortedAt: new Date().toISOString(),
      });
      agentAbortRef.current.abort();
    }
    const abortController = new AbortController();
    agentAbortRef.current = abortController;

    // 监听 abort 事件，记录取消时机
    abortController.signal.addEventListener('abort', () => {
      console.log('[Agent] handleTurn:ABORT_SIGNAL_RECEIVED', {
        abortedAt: new Date().toISOString(),
        elapsedMs: Date.now() - sendStartTime,
      });
    });

    setAgentSending(true);
    setAgentMessages(prev => [...prev, { role: 'user', content: text }]);
    setAgentInput('');

    try {
      // 确保会话存在
      let sessionId: string = agentSessionId || '';
      if (!sessionId) {
        console.log('[Agent] handleTurn:CREATE_SESSION', { scene: 'creative_assistant' });
        const { data } = await agentSessionsApi.createSession({ scene: 'creative_assistant' });
        sessionId = data.session_id;
        console.log('[Agent] handleTurn:SESSION_CREATED', {
          sessionId,
          elapsedMs: Date.now() - sendStartTime,
        });
        setAgentSessionId(sessionId);
        localStorage.setItem('novel_agent_session_id', sessionId);
      }

      // 添加助手占位消息
      setAgentMessages(prev => [...prev, { role: 'assistant', content: '' }]);

      // 发起 SSE 流式请求（带取消信号）
      const fetchStartTime = Date.now();
      console.log('[Agent] handleTurn:FETCH_START', {
        url: `/api/agent-sessions/${sessionId}/turns`,
        signal: abortController.signal.aborted ? 'aborted' : 'active',
      });
      const response = await agentSessionsApi.handleTurn(sessionId, text, {}, abortController.signal);
      console.log('[Agent] handleTurn:FETCH_RESPONSE', {
        status: response.status,
        ok: response.ok,
        contentType: response.headers.get('content-type'),
        elapsedMs: Date.now() - fetchStartTime,
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');
      console.log('[Agent] handleTurn:READER_READY', { elapsedMs: Date.now() - sendStartTime });

      const decoder = new TextDecoder();
      let buffer = '';
      let fullContent = '';
      let deltaCount = 0;

      while (!abortController.signal.aborted) {
          console.log('[Agent] handleTurn:READER_CANCELLED_BY_ABORT', {
            deltaCount,
            partialContentLength: fullContent.length,
            elapsedMs: Date.now() - sendStartTime,
          });
          reader.cancel();
          break;
        }
        const { done, value } = await reader.read();
        if (done) {
          console.log('[Agent] handleTurn:STREAM_DONE', {
            totalDeltas: deltaCount,
            totalContentLength: fullContent.length,
            elapsedMs: Date.now() - sendStartTime,
          });
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const event = JSON.parse(line.slice(6));
              if (event.event === 'message.delta') {
                deltaCount += 1;
                fullContent += event.payload?.text || '';
                setAgentMessages(prev => {
                  const updated = [...prev];
                  const lastIdx = updated.length - 1;
                  if (lastIdx >= 0 && updated[lastIdx].role === 'assistant') {
                    updated[lastIdx] = { ...updated[lastIdx], content: fullContent };
                  }
                  return updated;
                });
              } else if (event.event === 'turn.completed') {
                console.log('[Agent] handleTurn:TURN_COMPLETED', {
                  usage: event.payload?.usage,
                  totalDeltas: deltaCount,
                  elapsedMs: Date.now() - sendStartTime,
                });
              } else if (event.event === 'turn.failed') {
                console.log('[Agent] handleTurn:TURN_FAILED', {
                  error: event.payload?.error,
                  errorType: event.payload?.error_type,
                  elapsedMs: Date.now() - sendStartTime,
                });
                setAgentMessages(prev => {
                  const updated = [...prev];
                  const lastIdx = updated.length - 1;
                  if (lastIdx >= 0 && updated[lastIdx].role === 'assistant') {
                    updated[lastIdx] = {
                      ...updated[lastIdx],
                      content: `错误: ${event.payload?.error || '未知错误'}`,
                    };
                  }
                  return updated;
                });
              }
            } catch (parseErr) {
              // 跳过解析失败的行
              console.warn('[Agent] handleTurn:SSE_PARSE_FAILED', { line, error: parseErr });
            }
          }
        }
      }

      // 如果最终内容为空，设置默认消息
      if (!fullContent && !abortController.signal.aborted) {
        setAgentMessages(prev => {
          const updated = [...prev];
          const lastIdx = updated.length - 1;
          if (lastIdx >= 0 && updated[lastIdx].role === 'assistant' && !updated[lastIdx].content) {
            updated[lastIdx] = { ...updated[lastIdx], content: '指令已提交，Agent 将在后台处理您的请求。' };
          }
          return updated;
        });
      }
    } catch (err: any) {
      if (err.name === 'AbortError') {
        console.log('[Agent] handleTurn:ABORT_ERROR_CAUGHT', {
          abortedAt: new Date().toISOString(),
          elapsedMs: Date.now() - sendStartTime,
          message: '请求被用户主动取消（关闭浮窗、组件卸载或发送新消息）',
        });
        return;
      }
      console.error('[Agent] handleTurn:SEND_FAILED', {
        errorName: err.name,
        errorMessage: err.message,
        errorStack: err.stack,
        elapsedMs: Date.now() - sendStartTime,
      });
      setAgentMessages(prev => {
        const updated = [...prev];
        const lastIdx = updated.length - 1;
        if (lastIdx >= 0 && updated[lastIdx].role === 'assistant') {
          updated[lastIdx] = {
            ...updated[lastIdx],
            content: updated[lastIdx].content || '发送失败，请稍后重试。',
          };
        }
        return updated;
      });
      message.error('发送失败');
    } finally {
      const isAborted = abortController.signal.aborted;
      console.log('[Agent] handleTurn:FINALLY', {
        aborted: isAborted,
        agentSendingBeforeReset: agentSending,
        elapsedMs: Date.now() - sendStartTime,
      });
      setAgentSending(false);
      agentAbortRef.current = null;
      console.log('[Agent] handleTurn:END', {
        totalElapsedMs: Date.now() - sendStartTime,
        timestamp: new Date().toISOString(),
      });
    }
  };

  // 导出
  const handleOpenExportModal = () => {
    console.log('[ChaptersPage] handleOpenExportModal: 打开导出弹窗', {
      selectedCount: selectedIds.size,
      selectedIds: Array.from(selectedIds),
      lastDir: getStoredLastDir(),
    });
    setExportTargetDir(getStoredLastDir());
    setExportOverwrite(false);
    setExportModalVisible(true);
  };

  const handleCloseExportModal = () => {
    setExportModalVisible(false);
  };

  const handlePickDirectory = async () => {
    console.log('[ChaptersPage] handlePickDirectory: 尝试打开文件选择器', {
      dirPickerSupported,
    });
    if (dirPickerSupported) {
      const dir = await pickDirectory();
      if (dir) {
        console.log('[ChaptersPage] handlePickDirectory: 选择目录成功', { dir });
        setExportTargetDir(dir);
        return;
      }
      console.warn('[ChaptersPage] handlePickDirectory: 选择目录失败或取消');
    } else {
      console.warn('[ChaptersPage] handlePickDirectory: 浏览器不支持文件选择器，回退到手动输入');
    }
    // 回退：手动输入（Input 组件已支持）
  };

  const handleExport = async () => {
    if (selectedCount === 0) {
      console.warn('[ChaptersPage] handleExport: 未选择章节，阻止导出');
      message.error('请先选择要导出的章节');
      return;
    }
    if (!exportTargetDir.trim()) {
      console.warn('[ChaptersPage] handleExport: 未指定目标目录，阻止导出');
      message.error('请选择或输入目标目录');
      return;
    }

    const exportParams = {
      chapter_ids: Array.from(selectedIds),
      target_dir: exportTargetDir.trim(),
      overwrite: exportOverwrite,
    };

    console.log('[ChaptersPage] handleExport: 开始导出', {
      selectedCount,
      chapterIds: exportParams.chapter_ids,
      targetDir: exportParams.target_dir,
      overwrite: exportParams.overwrite,
    });

    setExporting(true);
    try {
      const response = await contentApi.exportChapters(exportParams);
      const data = response.data;

      console.log('[ChaptersPage] handleExport: 导出成功', {
        status: response.status,
        success: data.success,
        exportedCount: data.exported_count,
        skippedCount: data.skipped_count,
        messages: data.messages,
      });

      if (data.success) {
        console.log('[ChaptersPage] handleExport: 导出成功，保存目录到 localStorage', {
          savedDir: exportParams.target_dir,
        });
        message.success(`导出成功！共导出 ${data.exported_count} 个章节`);
        if (data.skipped_count > 0) {
          message.info(`跳过 ${data.skipped_count} 个章节（文件已存在）`);
        }
        setStoredLastDir(exportParams.target_dir);
        setExportModalVisible(false);
      } else {
        console.warn('[ChaptersPage] handleExport: 导出未成功', {
          messages: data.messages,
        });
        message.error('导出失败：' + (data.messages?.join('; ') || '未知错误'));
      }
    } catch (error: any) {
      const status = error.response?.status;
      const detail = error.response?.data?.detail || error.message || '未知错误';

      console.error('[ChaptersPage] handleExport: 导出失败', {
        status,
        detail,
        error: error.toString(),
        requestParams: exportParams,
      });

      if (status === 409) {
        message.error('导出失败：目标文件已存在，请勾选"覆盖已存在的文件"或选择其他目录');
      } else if (status === 400) {
        message.error('导出失败：' + detail);
      } else if (status === 404) {
        message.error('导出失败：章节不存在');
      } else if (status === 500) {
        message.error('导出失败：服务器内部错误，请稍后重试');
      } else {
        message.error('导出失败：' + detail);
      }
    } finally {
      console.log('[ChaptersPage] handleExport: 导出流程结束');
      setExporting(false);
    }
  };

  // 获取摘要内容（修复显示"暂无摘要"的问题）
  const getSummaryContent = (record: Chapter): React.ReactNode => {
    if (!record.summary) {
      return '暂无摘要';
    }
    
    // 检查是否有实际的摘要内容
    const summaryText = record.summary.summary;
    if (summaryText && typeof summaryText === 'string' && summaryText.trim()) {
      return summaryText;
    }
    
    // 尝试使用标题作为备用
    const summaryTitle = record.summary.title;
    if (summaryTitle && typeof summaryTitle === 'string' && summaryTitle.trim()) {
      return summaryTitle;
    }
    
    return '暂无摘要';
  };

  // Table 列定义
  const columns: ColumnsType<Chapter> = [
    {
      title: (
        <span
          onClick={() => setAscending(!ascending)}
          style={{ cursor: 'pointer', userSelect: 'none' }}
          title="点击切换排序"
        >
          章节 {ascending ? <ArrowDownOutlined /> : <ArrowUpOutlined />}
        </span>
      ),
      dataIndex: 'chapter_id',
      key: 'chapter_id',
      width: 80,
      render: (_: any, record: Chapter) => (
        <Tag>第 {record.chapter_id} 章</Tag>
      ),
    },
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      render: (_: any, record: Chapter) => {
        const displayTitle = record.title && record.title.trim() 
          ? record.title 
          : `第 ${record.chapter_id} 章`;
        return <Text strong>{displayTitle}</Text>;
      },
    },
    {
      title: '摘要',
      dataIndex: 'summary',
      key: 'summary',
      width: '50%',
      render: (_: any, record: Chapter) => (
        <Space style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Paragraph ellipsis={{ rows: 2 }} style={{ marginBottom: 0 }}>
            {getSummaryContent(record)}
          </Paragraph>
          {record.summary && (
            <Space size={12}>
              {record.summary.key_events && record.summary.key_events.length > 0 && (
                <Text type="secondary" style={{ fontSize: 12 }}>
                  关键事件: {record.summary.key_events.length} 个
                </Text>
              )}
              {record.summary.characters_appeared && record.summary.characters_appeared.length > 0 && (
                <Text type="secondary" style={{ fontSize: 12 }}>
                  出场人物: {record.summary.characters_appeared.length} 人
                </Text>
              )}
            </Space>
          )}
        </Space>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_: any, record: Chapter) => (
        <Button
          type="link"
          icon={<EyeOutlined />}
          onClick={() => navigate(`/content/chapters/${record.chapter_id}`)}
        >
          查看
        </Button>
      ),
    },
  ];

  // Table 分页配置
  const pagination: TablePaginationConfig = {
    current: currentPage,
    pageSize: pageSize,
    total: sortedChapters.length,
    showSizeChanger: true,
    pageSizeOptions: ['20', '50', '100', '200', '500'],
    showTotal: (total: number) => `共 ${total} 章`,
    onChange: (page: number, size?: number) => handlePageChange(page, size),
  };

  // Table 行选择配置
  const rowSelection = {
    selectedRowKeys: Array.from(selectedIds),
    onChange: handleSelectChange,
    onSelectAll: (selected: boolean) => handleSelectAllChange(selected),
    selections: [
      Table.SELECTION_ALL,
      Table.SELECTION_INVERT,
      Table.SELECTION_NONE,
    ],
  };

  return (
    <div>
      {/* 搜索区域 */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Title level={5} style={{ marginTop: 0 }}>搜索</Title>
        <Space style={{ width: '100%' }}>
          <Radio.Group
            value={searchMode}
            onChange={e => setSearchMode(e.target.value)}
            optionType="button"
            buttonStyle="solid"
          >
            <Radio.Button value="character">角色名搜索</Radio.Button>
            <Radio.Button value="fulltext">全文搜索</Radio.Button>
          </Radio.Group>
          <Space.Compact style={{ width: '100%' }}>
            <Input
              placeholder={searchMode === 'character' ? '输入角色名称...' : '输入搜索关键词...'}
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              onPressEnter={handleSearch}
            />
            <Button type="primary" icon={<SearchOutlined />} loading={searching} onClick={handleSearch}>
              搜索
            </Button>
          </Space.Compact>
        </Space>

        {/* 搜索结果 */}
        {hasSearched && searchResults !== null && (
          <div style={{ marginTop: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <Text type="secondary">
                共 {searchResults.length} 条结果
              </Text>
              <Space>
                <Text type="secondary" style={{ fontSize: 12 }}>排序:</Text>
                <Switch
                  size="small"
                  checkedChildren={<ArrowDownOutlined />}
                  unCheckedChildren={<ArrowUpOutlined />}
                  checked={resultAscending}
                  onChange={setResultAscending}
                />
              </Space>
            </div>
            <Table
              size="small"
              dataSource={
                (Array.isArray(searchResults) ? [...searchResults] : []).sort((a: any, b: any) => {
                  const aNum = parseInt(a.id?.replace(/\D/g, '') || '0', 10);
                  const bNum = parseInt(b.id?.replace(/\D/g, '') || '0', 10);
                  return resultAscending ? aNum - bNum : bNum - aNum;
                })
              }
              columns={[
                {
                  title: '类型',
                  dataIndex: 'type',
                  key: 'type',
                  render: (type: string) => (
                    <Tag color={type === 'character' ? 'blue' : 'purple'}>
                      {type === 'character' ? '角色' : type === 'chapter' ? '章节' : '暗线'}
                    </Tag>
                  ),
                },
                {
                  title: '标题',
                  dataIndex: 'title',
                  key: 'title',
                  render: (_: any, record: any) => (
                    <Text strong>{record.title}</Text>
                  ),
                },
                {
                  title: '描述',
                  dataIndex: 'snippet',
                  key: 'snippet',
                  render: (_: any, record: any) => {
                    const snippet = record.snippet && record.snippet.trim()
                      ? record.snippet
                      : (record.type === 'chapter' ? `第 ${record.id} 章` : '');
                    return <Text type="secondary" style={{ fontSize: 13 }}>{snippet}</Text>;
                  },
                },
                {
                  title: '操作',
                  key: 'action',
                  render: (_: any, record: any) => (
                    <Button
                      type="link"
                      size="small"
                      icon={<EyeOutlined />}
                      onClick={() => {
                        if (record.type === 'chapter') {
                          navigate(`/content/chapters/${record.id}`);
                        } else if (record.type === 'character') {
                          navigate('/content/characters');
                        }
                      }}
                    >
                      查看
                    </Button>
                  ),
                },
              ]}
              pagination={false}
              locale={{ emptyText: '无搜索结果' }}
            />
          </div>
        )}
      </Card>

      {/* 章节列表 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, flexWrap: 'wrap', gap: 12 }}>
        <Title level={4} style={{ margin: 0 }}>章节管理</Title>
        <Space wrap size={0} style={{ gap: '0 24px' }}>
          {/* 统计信息 */}
          <Space size={8} style={{ color: '#8c8c8c', fontSize: 13 }}>
            <span>共 {chapters.length} 章</span>
            {selectedCount > 0 && (
              <span style={{ color: '#722ed1', fontWeight: 500 }}>
                已选 {selectedCount} 章
              </span>
            )}
          </Space>

          {/* 导出按钮 */}
          <Button
            type="primary"
            size="small"
            icon={<DownloadOutlined />}
            onClick={handleOpenExportModal}
            disabled={selectedCount === 0}
            style={{ minWidth: 90 }}
          >
            导出文章
          </Button>
        </Space>
      </div>

      <Table
        rowKey="chapter_id"
        loading={loading}
        dataSource={paginatedChapters}
        columns={columns}
        rowSelection={rowSelection}
        pagination={pagination}
        scroll={{ x: 600 }}
        locale={{ emptyText: '暂无章节，请先生成内容' }}
      />

      {/* 导出弹窗 */}
      <Modal
        title="导出章节"
        open={exportModalVisible}
        onCancel={handleCloseExportModal}
        footer={[
          <Button key="back" onClick={handleCloseExportModal}>
            取消
          </Button>,
          <Button key="submit" type="primary" loading={exporting} onClick={handleExport}>
            开始导出
          </Button>,
        ]}
        width={600}
      >
        <Space style={{ width: '100%' }}>
          <div>
            <Title level={5} style={{ marginBottom: 8 }}>已选章节</Title>
            <Text>共选择 <Text strong>{selectedCount}</Text> 个章节</Text>
            {selectedCount > 0 && (
              <div style={{ maxHeight: 120, overflow: 'auto', marginTop: 8, padding: 8, background: '#f5f5f5', borderRadius: 4 }}>
                {sortedChapters
                  .filter(c => selectedIds.has(c.chapter_id))
                  .map(c => {
                    const displayTitle = c.title && c.title.trim() 
                      ? c.title 
                      : `第 ${c.chapter_id} 章`;
                    return (
                      <Tag key={c.chapter_id} style={{ marginBottom: 4 }}>
                        {displayTitle}
                      </Tag>
                    );
                  })}
              </div>
            )}
          </div>

          <div>
            <Title level={5} style={{ marginBottom: 8 }}>目标目录</Title>
            <Space.Compact style={{ width: '100%' }}>
              <Input
                placeholder="输入目标目录路径，如 /Users/username/Documents/novels"
                value={exportTargetDir}
                onChange={(e) => setExportTargetDir(e.target.value)}
                prefix={<FolderOpenOutlined />}
              />
              {dirPickerSupported && (
                <Button onClick={handlePickDirectory}>
                  浏览...
                </Button>
              )}
            </Space.Compact>
            <Text type="secondary" style={{ fontSize: 12 }}>
              支持绝对路径和 ~ 表示用户目录
            </Text>
          </div>

          <div>
            <Space>
              <Select
                value={exportOverwrite ? 'overwrite' : 'skip'}
                onChange={(v) => setExportOverwrite(v === 'overwrite')}
                options={[
                  { value: 'skip', label: '跳过已存在文件' },
                  { value: 'overwrite', label: '覆盖已存在文件' },
                ]}
              />
            </Space>
          </div>

          <div>
            <Text type="secondary" style={{ fontSize: 12 }}>
              <strong>提示：</strong>导出的章节文件将以 chapter_XX_final.md 格式保存，方便同步到网站或其他平台。
            </Text>
          </div>
        </Space>
      </Modal>

      {/* Agent 浮窗对话 */}
      {agentExpanded && (
        <div
          style={{
            position: 'fixed',
            bottom: 100,
            right: 32,
            width: 380,
            maxHeight: 520,
            borderRadius: 16,
            boxShadow: '0 8px 32px rgba(114, 46, 209, 0.15), 0 2px 8px rgba(0, 0, 0, 0.08)',
            background: 'rgba(255, 255, 255, 0.95)',
            backdropFilter: 'blur(12px)',
            border: '1px solid rgba(114, 46, 209, 0.2)',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            zIndex: 1000,
          }}
        >
          {/* 标题栏 - 可拖拽 */}
          <div
            style={{
              padding: '12px 16px',
              background: 'linear-gradient(135deg, #722ed1 0%, #9254de 100%)',
              color: '#fff',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              cursor: 'move',
            }}
          >
            <Space>
              <RobotOutlined style={{ fontSize: 18 }} />
              <span style={{ fontWeight: 600, fontSize: 15 }}>创作助手</span>
            </Space>
            <Button
              type="text"
              size="small"
              onClick={() => {
                // 关闭浮窗时取消进行中的请求
                if (agentAbortRef.current) {
                  agentAbortRef.current.abort();
                  agentAbortRef.current = null;
                }
                setAgentExpanded(false);
              }}
              style={{ color: '#fff', opacity: 0.9 }}
            >
              ✕
            </Button>
          </div>

          {/* 消息区域 */}
          <div
            style={{
              flex: 1,
              overflow: 'auto',
              padding: 16,
              background: 'linear-gradient(180deg, #faf5ff 0%, #fff 100%)',
              minHeight: 200,
              maxHeight: 320,
            }}
          >
            {agentMessages.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '24px 0' }}>
                <RobotOutlined style={{ fontSize: 32, color: '#b37feb', marginBottom: 12 }} />
                <Text type="secondary" style={{ display: 'block' }}>
                  向创作助手发送指令
                </Text>
                <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 4 }}>
                  例如：&quot;帮我创作第3章&quot;
                </Text>
              </div>
            ) : (
              agentMessages.map((msg, i) => (
                <div
                  key={i}
                  style={{
                    marginBottom: 12,
                    display: 'flex',
                    justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                  }}
                >
                  <div
                    style={{
                      maxWidth: '85%',
                      padding: '10px 14px',
                      borderRadius: msg.role === 'user' 
                        ? '16px 16px 4px 16px' 
                        : '16px 16px 16px 4px',
                      background: msg.role === 'user' 
                        ? 'linear-gradient(135deg, #722ed1 0%, #9254de 100%)'
                        : '#f5f5f5',
                      color: msg.role === 'user' ? '#fff' : 'rgba(0, 0, 0, 0.85)',
                      fontSize: 14,
                      lineHeight: 1.5,
                      boxShadow: msg.role === 'user' 
                        ? '0 2px 8px rgba(114, 46, 209, 0.25)' 
                        : '0 1px 2px rgba(0, 0, 0, 0.05)',
                    }}
                  >
                    {msg.content}
                  </div>
                </div>
              ))
            )}
          </div>

          {/* 输入区域 */}
          <div
            style={{
              padding: 12,
              borderTop: '1px solid #f0f0f0',
              background: '#fff',
            }}
          >
            <Space.Compact style={{ width: '100%' }}>
              <Input
                placeholder="输入创作指令..."
                value={agentInput}
                onChange={e => setAgentInput(e.target.value)}
                onPressEnter={handleAgentSend}
                style={{
                  borderRadius: '20px 0 0 20px',
                  border: '1px solid #e8e8e8',
                  padding: '8px 16px',
                }}
              />
              <Button
                type="primary"
                icon={<SendOutlined />}
                loading={agentSending}
                onClick={handleAgentSend}
                style={{
                  borderRadius: '0 20px 20px 0',
                  background: 'linear-gradient(135deg, #722ed1 0%, #9254de 100%)',
                  border: 'none',
                  height: 40,
                  padding: '0 20px',
                }}
              />
            </Space.Compact>
          </div>
        </div>
      )}

      {/* 浮窗触发按钮 */}
      <Button
        type="primary"
        icon={<BulbOutlined />}
        size="large"
        style={{
          position: 'fixed',
          bottom: 32,
          right: 32,
          borderRadius: '50%',
          width: 60,
          height: 60,
          boxShadow: '0 4px 16px rgba(114, 46, 209, 0.4)',
          background: agentExpanded ? '#b37feb' : 'linear-gradient(135deg, #722ed1 0%, #9254de 100%)',
          border: 'none',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 999,
          transition: 'all 0.3s ease',
        }}
        onClick={() => setAgentExpanded(!agentExpanded)}
      >
        {agentExpanded ? <span style={{ fontSize: 20 }}>✕</span> : <BulbOutlined style={{ fontSize: 24 }} />}
      </Button>
    </div>
  );
}
