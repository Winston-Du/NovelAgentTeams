import { useState } from 'react';
import { Input, Typography, Tag, Space, Empty, Spin } from 'antd';
import { SearchOutlined, UserOutlined, FileTextOutlined, NodeIndexOutlined } from '@ant-design/icons';
import { contentApi } from '../../services/api';

const { Title, Text } = Typography;

const typeIcons: Record<string, React.ReactNode> = {
  character: <UserOutlined />,
  chapter: <FileTextOutlined />,
  plotline: <NodeIndexOutlined />,
};

const typeColors: Record<string, string> = {
  character: 'purple', chapter: 'blue', plotline: 'orange',
};

export default function SearchPage() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const handleSearch = async (value: string) => {
    if (!value.trim()) return;
    setQuery(value);
    setLoading(true);
    setSearched(true);
    try {
      const res = await contentApi.search(value);
      setResults(res.data.results || []);
      setTotal(res.data.count || 0);
    } catch {
      setResults([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <Title level={4}>全局搜索</Title>
      <Input.Search
        placeholder="搜索人物、章节、暗线..."
        allowClear
        enterButton={<><SearchOutlined /> 搜索</>}
        size="large"
        onSearch={handleSearch}
        style={{ marginBottom: 24, maxWidth: 600 }}
      />

      {loading && <Spin style={{ display: 'block', margin: '40px auto' }} />}

      {!loading && searched && (
        <div>
          <Text type="secondary" style={{ marginBottom: 16, display: 'block' }}>
            搜索 "{query}"，找到 {total} 条结果
          </Text>

          {results.length === 0 ? (
            <Empty description="未找到匹配结果" />
          ) : (
            <div className="search-results-list">
              {results.map((item: any) => (
                <div key={item.id} className="search-result-item">
                  <Space style={{ marginBottom: 4 }}>
                    <span style={{ fontSize: 18 }}>
                      {typeIcons[item.type] || <FileTextOutlined />}
                    </span>
                    <Tag color={typeColors[item.type] || 'default'}>
                      {((): string => {
                        const labels: Record<string, string> = { character: '人物', chapter: '章节', plotline: '暗线' };
                        return labels[item.type] || item.type;
                      })()}
                    </Tag>
                    <Text strong>{item.title}</Text>
                  </Space>
                  <div style={{ color: 'rgba(0,0,0,0.65)', marginLeft: 30 }}>
                    {item.snippet}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}