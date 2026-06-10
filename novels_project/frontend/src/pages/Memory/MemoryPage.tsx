import { useEffect, useState } from 'react';
import {
  Card, Tabs, Table, Typography, Tag, Space, Button,
  Input, Select, message, Statistic, Row, Col, Drawer,
  Descriptions, Popconfirm, Spin, Empty, Modal, Form,
} from 'antd';
import {
  DatabaseOutlined, ReloadOutlined, SearchOutlined,
  DeleteOutlined, EyeOutlined, SyncOutlined, PlusOutlined,
  CloudUploadOutlined,
} from '@ant-design/icons';
import { memoryApi } from '../../services/api';

const { Title, Text } = Typography;
const { TextArea } = Input;

export default function MemoryPage() {
  const [activeTab, setActiveTab] = useState('entities');
  const [entities, setEntities] = useState<any[]>([]);
  const [relations, setRelations] = useState<any[]>([]);
  const [foreshadows, setForeshadows] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [initializing, setInitializing] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [typeFilter, setTypeFilter] = useState<string | undefined>();
  const [selectedEntity, setSelectedEntity] = useState<any>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [entRes, relRes, foreRes, statsRes] = await Promise.all([
        memoryApi.getEntities({ limit: 200 }),
        memoryApi.getRelations({}),
        memoryApi.getForeshadowing(),
        memoryApi.getStats(),
      ]);
      setEntities(entRes.data.entities || []);
      setRelations(relRes.data.relations || []);
      setForeshadows(foreRes.data.unresolved || []);
      setStats(statsRes.data);
    } catch {
      // Ignore errors if graph doesn't exist yet
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  const handleSync = async () => {
    setSyncing(true);
    try {
      await memoryApi.sync();
      message.success('同步完成');
      fetchData();
    } catch (err: any) {
      const detail = err?.response?.data?.detail || '同步失败';
      message.error(detail);
    } finally {
      setSyncing(false);
    }
  };

  const handleInit = async () => {
    setInitializing(true);
    try {
      const res = await memoryApi.init();
      message.success(`图谱初始化完成，已导入 ${res.data.imported ?? 0} 个实体`);
      fetchData();
    } catch (err: any) {
      const detail = err?.response?.data?.detail || '初始化失败';
      message.error(detail);
    } finally {
      setInitializing(false);
    }
  };

  const handleDeleteEntity = async (id: string) => {
    try {
      await memoryApi.deleteEntity(id);
      message.success('删除成功');
      fetchData();
    } catch {
      message.error('删除失败');
    }
  };

  const handleDeleteRelation = async (source: string, target: string) => {
    try {
      await memoryApi.deleteRelation(source, target);
      message.success('删除成功');
      fetchData();
    } catch {
      message.error('删除失败');
    }
  };

  const typeColors: Record<string, string> = {
    character: 'purple', event: 'blue', item: 'cyan',
    location: 'green', organization: 'orange', concept: 'magenta',
  };

  const entityColumns = [
    { title: '名称', dataIndex: 'name', key: 'name', width: 150 },
    {
      title: '类型', dataIndex: 'type', key: 'type', width: 100,
      render: (t: string) => <Tag color={typeColors[t] || 'default'}>{t}</Tag>,
    },
    { title: '简介', dataIndex: 'brief', key: 'brief', ellipsis: true },
    {
      title: '操作', key: 'actions', width: 160,
      render: (_: any, record: any) => (
        <Space>
          <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => {
            setSelectedEntity(record);
            setDrawerOpen(true);
          }}>
            详情
          </Button>
          <Popconfirm title="确定删除？" onConfirm={() => handleDeleteEntity(record.name)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const relColumns = [
    { title: '源实体', dataIndex: 'source', key: 'source', width: 120 },
    { title: '关系', dataIndex: 'type', key: 'type', width: 120,
      render: (t: string) => <Tag>{t}</Tag>,
    },
    { title: '目标实体', dataIndex: 'target', key: 'target', width: 120 },
    {
      title: '操作', key: 'actions', width: 80,
      render: (_: any, record: any) => (
        <Popconfirm title="确定删除？" onConfirm={() => handleDeleteRelation(record.source, record.target)}>
          <Button type="link" size="small" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      ),
    },
  ];

  const tabs = [
    {
      key: 'entities',
      label: `实体 (${entities.length})`,
      children: (
        <div>
          <Space style={{ marginBottom: 16 }}>
            <Input.Search
              placeholder="搜索实体..."
              allowClear
              onSearch={setSearchText}
              style={{ width: 250 }}
            />
            <Select
              placeholder="类型筛选"
              allowClear
              onChange={setTypeFilter}
              style={{ width: 120 }}
              options={[
                { label: '人物', value: 'character' },
                { label: '事件', value: 'event' },
                { label: '地点', value: 'location' },
                { label: '概念', value: 'concept' },
              ]}
            />
          </Space>
          <Table
            dataSource={entities.filter(e => {
              if (searchText && !e.name?.includes(searchText) && !e.brief?.includes(searchText)) return false;
              if (typeFilter && e.type !== typeFilter) return false;
              return true;
            })}
            columns={entityColumns}
            rowKey="name"
            loading={loading}
            size="small"
            locale={{ emptyText: <Empty description="暂无实体数据，请先导入人物卡或执行初始化" /> }}
          />
        </div>
      ),
    },
    {
      key: 'relations',
      label: `关系 (${relations.length})`,
      children: (
        <Table
          dataSource={relations}
          columns={relColumns}
          rowKey={(r: any) => `${r.source}-${r.target}-${r.type}`}
          loading={loading}
          size="small"
          locale={{ emptyText: <Empty description="暂无关系数据，实体间的关系将在文本提取后自动生成" /> }}
        />
      ),
    },
    {
      key: 'foreshadow',
      label: `伏笔 (${foreshadows.length})`,
      children: (
        <div>
          {foreshadows.length === 0 ? (
            <Empty description="暂未发现未回收的伏笔" />
          ) : (
            foreshadows.map((f: any, i: number) => (
              <Card key={i} size="small" style={{ marginBottom: 8 }}>
                <Text strong>{f.concept || f.name}</Text>
                <br />
                <Text type="secondary">{f.brief || f.description}</Text>
                {f.unresolved_targets && f.unresolved_targets.length > 0 && (
                  <div style={{ marginTop: 8 }}>
                    <Text type="secondary">未回收目标: </Text>
                    {f.unresolved_targets.map((t: any, j: number) => (
                      <Tag key={j}>{t.name || t}</Tag>
                    ))}
                  </div>
                )}
              </Card>
            ))
          )}
        </div>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Space>
          <DatabaseOutlined style={{ fontSize: 24, color: '#722ed1' }} />
          <Title level={4} style={{ margin: 0 }}>记忆管理</Title>
        </Space>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={fetchData}>刷新</Button>
          <Button
            icon={<CloudUploadOutlined />}
            onClick={handleInit}
            loading={initializing}
          >
            初始化图谱
          </Button>
          <Button
            type="primary"
            icon={<SyncOutlined spin={syncing} />}
            onClick={handleSync}
            loading={syncing}
          >
            手动同步
          </Button>
        </Space>
      </div>

      {stats && (
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={6}><Card size="small"><Statistic title="节点总数" value={stats.node_count || 0} /></Card></Col>
          <Col span={6}><Card size="small"><Statistic title="关系总数" value={stats.edge_count || 0} /></Card></Col>
          <Col span={6}><Card size="small"><Statistic title="人物" value={stats.node_types?.character || 0} /></Card></Col>
          <Col span={6}><Card size="small"><Statistic title="概念/伏笔" value={stats.node_types?.concept || 0} /></Card></Col>
        </Row>
      )}

      <Card>
        <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabs} />
      </Card>

      {/* 实体详情抽屉 */}
      <Drawer
        title="实体详情"
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        size="default"
      >
        {selectedEntity && (
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="名称">{selectedEntity.name}</Descriptions.Item>
            <Descriptions.Item label="类型">
              <Tag color={typeColors[selectedEntity.type] || 'default'}>{selectedEntity.type}</Tag>
            </Descriptions.Item>
            {Object.entries(selectedEntity)
              .filter(([k]) => !['name', 'type'].includes(k))
              .map(([key, value]) => (
                <Descriptions.Item key={key} label={key}>
                  {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                </Descriptions.Item>
              ))}
          </Descriptions>
        )}
      </Drawer>
    </div>
  );
}