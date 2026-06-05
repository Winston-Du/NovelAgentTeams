import { useEffect, useState } from 'react';
import {
  Card, List, Typography, Tag, Space, Button, Switch, Input, Radio,
  message,
} from 'antd';
import {
  EyeOutlined, FileTextOutlined, SearchOutlined, SendOutlined,
  SortAscendingOutlined, SortDescendingOutlined, RobotOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { contentApi } from '../../services/api';
import { ensureArray, extractResults } from '../../utils/dataGuards';

const { Title, Text, Paragraph } = Typography;

export default function ChaptersPage() {
  const [chapters, setChapters] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [ascending, setAscending] = useState(true);
  const navigate = useNavigate();

  // Search state
  const [searchMode, setSearchMode] = useState<'character' | 'fulltext'>('fulltext');
  const [searchQuery, setSearchQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<any[] | null>(null);
  const [hasSearched, setHasSearched] = useState(false);
  const [resultAscending, setResultAscending] = useState(true);

  // Agent dialog state
  const [agentInput, setAgentInput] = useState('');
  const [agentMessages, setAgentMessages] = useState<{ role: string; content: string }[]>([]);
  const [agentSending, setAgentSending] = useState(false);
  const [agentExpanded, setAgentExpanded] = useState(false);

  useEffect(() => {
    setLoading(true);
    console.log('[ChaptersPage] fetchChapters: 开始请求章节列表');
    contentApi.getChapters()
      .then(res => {
        console.log('[ChaptersPage] fetchChapters: 原始响应类型', typeof res.data, '是否为数组', Array.isArray(res.data));
        console.log('[ChaptersPage] fetchChapters: 原始响应数据', res.data);
        const validated = ensureArray(res.data);
        console.log('[ChaptersPage] fetchChapters: 校验后数据长度', validated.length);
        setChapters(validated);
      })
      .catch(err => {
        console.error('[ChaptersPage] fetchChapters: 请求失败', err);
        setChapters([]);
      })
      .finally(() => setLoading(false));
  }, []);

  const sortedChapters = [...chapters].sort((a, b) => {
    const diff = (a.chapter_id || a.chapter_id || 0) - (b.chapter_id || b.chapter_id || 0);
    return ascending ? diff : -diff;
  });

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

  const handleAgentSend = async () => {
    const text = agentInput.trim();
    if (!text) return;
    setAgentSending(true);
    setAgentMessages(prev => [...prev, { role: 'user', content: text }]);
    setAgentInput('');
    try {
      await contentApi.annotate({ content_type: 'new_chapter', content_id: '', note: text });
      setAgentMessages(prev => [...prev, { role: 'assistant', content: '指令已提交，Agent 将在后台处理您的请求。' }]);
      message.success('指令已发送');
    } catch {
      setAgentMessages(prev => [...prev, { role: 'assistant', content: '发送失败，请稍后重试。' }]);
      message.error('发送失败');
    } finally {
      setAgentSending(false);
    }
  };

  return (
    <div>
      {/* 搜索区域 */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Title level={5} style={{ marginTop: 0 }}>搜索</Title>
        <Space direction="vertical" style={{ width: '100%' }}>
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
                  checkedChildren={<SortAscendingOutlined />}
                  unCheckedChildren={<SortDescendingOutlined />}
                  checked={resultAscending}
                  onChange={setResultAscending}
                />
              </Space>
            </div>
            <List
              size="small"
              dataSource={
                (Array.isArray(searchResults) ? [...searchResults] : []).sort((a: any, b: any) => {
                  const aNum = parseInt(a.id?.replace(/\D/g, '') || '0', 10);
                  const bNum = parseInt(b.id?.replace(/\D/g, '') || '0', 10);
                  return resultAscending ? aNum - bNum : bNum - aNum;
                })
              }
              locale={{ emptyText: '无搜索结果' }}
              renderItem={(item: any) => (
                <List.Item
                  actions={[
                    <Button
                      key="view"
                      type="link"
                      size="small"
                      icon={<EyeOutlined />}
                      onClick={() => {
                        if (item.type === 'chapter') {
                          navigate(`/content/chapters/${item.id}`);
                        } else if (item.type === 'character') {
                          navigate('/content/characters');
                        }
                      }}
                    >
                      查看
                    </Button>,
                  ]}
                >
                  <List.Item.Meta
                    title={
                      <Space>
                        <Tag color={item.type === 'character' ? 'blue' : 'purple'}>
                          {item.type === 'character' ? '角色' : item.type === 'chapter' ? '章节' : '暗线'}
                        </Tag>
                        <Text strong>{item.title}</Text>
                      </Space>
                    }
                    description={
                      <Text type="secondary" style={{ fontSize: 13 }}>
                        {item.snippet || (item.type === 'chapter' ? `第 ${item.id} 章` : '')}
                      </Text>
                    }
                  />
                </List.Item>
              )}
            />
          </div>
        )}
      </Card>

      {/* 章节列表 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>章节管理</Title>
        <Space>
          <Text type="secondary" style={{ fontSize: 13 }}>排序:</Text>
          <Switch
            checkedChildren={<SortAscendingOutlined />}
            unCheckedChildren={<SortDescendingOutlined />}
            checked={ascending}
            onChange={setAscending}
          />
          <Text type="secondary">共 {chapters.length} 章</Text>
        </Space>
      </div>

      <List
        loading={loading}
        dataSource={sortedChapters}
        renderItem={(chapter: any) => (
          <List.Item
            actions={[
              <Button
                type="link"
                icon={<EyeOutlined />}
                onClick={() => navigate(`/content/chapters/${chapter.chapter_id}`)}
              >
                查看内容
              </Button>,
            ]}
          >
            <List.Item.Meta
              avatar={<FileTextOutlined style={{ fontSize: 24, color: '#722ed1' }} />}
              title={
                <Space>
                  <Text strong>{chapter.title || `第 ${chapter.chapter_id} 章`}</Text>
                  <Tag>第 {chapter.chapter_id} 章</Tag>
                  {chapter.size && (
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {(chapter.size / 1024).toFixed(1)} KB
                    </Text>
                  )}
                </Space>
              }
              description={
                <Space direction="vertical" size={2}>
                  {chapter.summary ? (
                    <>
                      <Paragraph ellipsis={{ rows: 2 }} style={{ marginBottom: 0 }}>
                        {chapter.summary.summary || chapter.summary.title || '暂无摘要'}
                      </Paragraph>
                      <Space size={12}>
                        {chapter.summary.key_events && (
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            关键事件: {chapter.summary.key_events.length} 个
                          </Text>
                        )}
                        {chapter.summary.characters_appeared && (
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            出场人物: {chapter.summary.characters_appeared.length} 人
                          </Text>
                        )}
                      </Space>
                    </>
                  ) : (
                    <Text type="secondary">暂无摘要</Text>
                  )}
                </Space>
              }
            />
          </List.Item>
        )}
        locale={{ emptyText: '暂无章节，请先生成内容' }}
      />

      {/* Agent 对话区域 */}
      <div style={{ marginTop: 24 }}>
        {agentExpanded ? (
          <Card
            size="small"
            title={
              <Space>
                <RobotOutlined />
                <span>创作助手</span>
              </Space>
            }
            extra={
              <Button
                type="text"
                size="small"
                onClick={() => setAgentExpanded(false)}
              >
                收起
              </Button>
            }
            style={{ borderColor: '#722ed1' }}
          >
            <div style={{ maxHeight: 300, overflow: 'auto', marginBottom: 12 }}>
              {agentMessages.length === 0 ? (
                <Text type="secondary">向创作助手发送指令，例如"帮我创作第3章"。</Text>
              ) : (
                agentMessages.map((msg, i) => (
                  <div
                    key={i}
                    style={{
                      marginBottom: 8,
                      textAlign: msg.role === 'user' ? 'right' : 'left',
                    }}
                  >
                    <Tag color={msg.role === 'user' ? 'blue' : 'purple'} style={{ marginRight: 0 }}>
                      {msg.role === 'user' ? '你' : '助手'}
                    </Tag>
                    <div style={{
                      display: 'inline-block',
                      maxWidth: '80%',
                      padding: '6px 12px',
                      borderRadius: 8,
                      background: msg.role === 'user' ? '#e6f7ff' : '#f9f0ff',
                      textAlign: 'left',
                      marginTop: 4,
                    }}>
                      {msg.content}
                    </div>
                  </div>
                ))
              )}
            </div>
            <Space.Compact style={{ width: '100%' }}>
              <Input
                placeholder="输入创作指令..."
                value={agentInput}
                onChange={e => setAgentInput(e.target.value)}
                onPressEnter={handleAgentSend}
              />
              <Button
                type="primary"
                icon={<SendOutlined />}
                loading={agentSending}
                onClick={handleAgentSend}
              >
                发送
              </Button>
            </Space.Compact>
          </Card>
        ) : (
          <Button
            type="primary"
            icon={<RobotOutlined />}
            size="large"
            style={{
              position: 'fixed',
              bottom: 32,
              right: 32,
              borderRadius: 28,
              height: 56,
              boxShadow: '0 4px 12px rgba(114, 46, 209, 0.3)',
            }}
            onClick={() => setAgentExpanded(true)}
          >
            创作助手
          </Button>
        )}
      </div>
    </div>
  );
}