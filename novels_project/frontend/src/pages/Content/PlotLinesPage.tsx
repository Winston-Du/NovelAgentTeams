import { useEffect, useState } from 'react';
import {
  Card, Table, Button, Space, Typography, Tag, Modal,
  Form, Input, Select, message, Popconfirm,
} from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { contentApi } from '../../services/api';

const { Title } = Typography;
const { TextArea } = Input;

export default function PlotLinesPage() {
  const [plotLines, setPlotLines] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<any>(null);
  const [form] = Form.useForm();

  const fetchPlotLines = async () => {
    setLoading(true);
    try {
      const res = await contentApi.getPlotLines();
      setPlotLines(Array.isArray(res.data) ? res.data : []);
    } catch {
      setPlotLines([]);
      message.error('获取暗线列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchPlotLines(); }, []);

  const handleCreate = async (values: any) => {
    try {
      await contentApi.createPlotLine(values);
      message.success('创建成功');
      setCreateOpen(false);
      form.resetFields();
      fetchPlotLines();
    } catch (e: any) {
      message.error(e.response?.data?.detail || '创建失败');
    }
  };

  const handleUpdate = async (values: any) => {
    if (!editing) return;
    try {
      await contentApi.updatePlotLine(editing.id, values);
      message.success('更新成功');
      setEditOpen(false);
      setEditing(null);
      fetchPlotLines();
    } catch (e: any) {
      message.error(e.response?.data?.detail || '更新失败');
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await contentApi.deletePlotLine(id);
      message.success('删除成功');
      fetchPlotLines();
    } catch {
      message.error('删除失败');
    }
  };

  const statusColor: Record<string, string> = {
    active: 'blue', resolved: 'green', abandoned: 'default',
  };
  const statusLabel: Record<string, string> = {
    active: '进行中', resolved: '已回收', abandoned: '已废弃',
  };

  const columns = [
    { title: '名称', dataIndex: 'name', key: 'name', width: 150 },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 100,
      render: (s: string) => <Tag color={statusColor[s] || 'default'}>{statusLabel[s] || s}</Tag>,
    },
    {
      title: '关联人物', dataIndex: 'related_characters', key: 'related_characters', width: 200,
      render: (chars: string[]) => chars?.map(c => <Tag key={c}>{c}</Tag>),
    },
    {
      title: '操作', key: 'actions', width: 160,
      render: (_: any, record: any) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => {
            setEditing(record);
            form.setFieldsValue(record);
            setEditOpen(true);
          }}>
            编辑
          </Button>
          <Popconfirm title="确定删除？" onConfirm={() => handleDelete(record.id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const formContent = (
    <Form form={form} layout="vertical">
      <Form.Item name="name" label="暗线名称" rules={[{ required: true }]}>
        <Input />
      </Form.Item>
      <Form.Item name="description" label="描述" rules={[{ required: true }]}>
        <TextArea rows={4} />
      </Form.Item>
      <Form.Item name="status" label="状态">
        <Select options={[
          { label: '进行中', value: 'active' },
          { label: '已回收', value: 'resolved' },
          { label: '已废弃', value: 'abandoned' },
        ]} />
      </Form.Item>
      <Form.Item name="notes" label="备注">
        <TextArea rows={2} />
      </Form.Item>
    </Form>
  );

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>暗线管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => { setCreateOpen(true); form.resetFields(); }}>
          新建暗线
        </Button>
      </div>

      <Table
        dataSource={plotLines}
        columns={columns}
        rowKey="id"
        loading={loading}
        locale={{ emptyText: '暂无暗线数据，请先在创作过程中埋入暗线' }}
      />

      <Modal title="新建暗线" open={createOpen} onCancel={() => setCreateOpen(false)} onOk={() => form.submit()}>
        <div onKeyDown={e => e.key === 'Enter' && form.submit()}>
          {formContent}
        </div>
      </Modal>

      <Modal title="编辑暗线" open={editOpen} onCancel={() => setEditOpen(false)} onOk={() => form.submit()}>
        <div onKeyDown={e => e.key === 'Enter' && form.submit()}>
          {formContent}
        </div>
      </Modal>
    </div>
  );
}