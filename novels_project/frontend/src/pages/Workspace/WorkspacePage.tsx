import { useEffect, useState } from 'react';
import {
  Card, Table, Button, Space, Modal, Input, Form,
  Typography, Tag, Popconfirm, message, Empty,
} from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, SwapOutlined } from '@ant-design/icons';
import { useWorkspaceStore, Workspace } from '../../stores/workspaceStore';

const { Title } = Typography;

export default function WorkspacePage() {
  const {
    workspaces, currentWorkspace, loading,
    fetchWorkspaces, createWorkspace,
    deleteWorkspace, renameWorkspace, switchWorkspace,
  } = useWorkspaceStore();

  const [createOpen, setCreateOpen] = useState(false);
  const [renameOpen, setRenameOpen] = useState(false);
  const [renameTarget, setRenameTarget] = useState<Workspace | null>(null);
  const [form] = Form.useForm();
  const [renameForm] = Form.useForm();

  useEffect(() => {
    fetchWorkspaces();
  }, []);

  const handleCreate = async (values: { name: string; base_path?: string }) => {
    try {
      await createWorkspace(values.name, values.base_path);
      message.success('工作空间创建成功');
      setCreateOpen(false);
      form.resetFields();
    } catch (e: any) {
      message.error(e.response?.data?.detail || '创建失败');
    }
  };

  const handleRename = async (values: { new_name: string }) => {
    if (!renameTarget) return;
    try {
      await renameWorkspace(renameTarget.name, values.new_name);
      message.success('重命名成功');
      setRenameOpen(false);
      setRenameTarget(null);
    } catch (e: any) {
      message.error(e.response?.data?.detail || '重命名失败');
    }
  };

  const handleDelete = async (name: string) => {
    try {
      await deleteWorkspace(name);
      message.success('删除成功');
    } catch (e: any) {
      message.error(e.response?.data?.detail || '删除失败');
    }
  };

  const handleSwitch = async (name: string) => {
    try {
      await switchWorkspace(name);
      message.success(`已切换到 "${name}"`);
    } catch (e: any) {
      message.error(e.response?.data?.detail || '切换失败');
    }
  };

  const columns = [
    { title: '名称', dataIndex: 'name', key: 'name',
      render: (text: string, record: Workspace) => (
        <Space>
          {text}
          {record.is_current && <Tag color="purple">当前</Tag>}
        </Space>
      ),
    },
    { title: '路径', dataIndex: 'path', key: 'path', ellipsis: true },
    { title: '章节数', dataIndex: 'chapters_count', key: 'chapters', width: 80 },
    {
      title: '状态', key: 'status', width: 80,
      render: (_: any, record: Workspace) => (
        <Tag color={record.is_ready ? 'green' : 'orange'}>
          {record.is_ready ? '就绪' : '待配置'}
        </Tag>
      ),
    },
    {
      title: '操作', key: 'actions', width: 240,
      render: (_: any, record: Workspace) => (
        <Space>
          {!record.is_current && (
            <Button
              type="link" size="small"
              icon={<SwapOutlined />}
              onClick={() => handleSwitch(record.name)}
            >
              切换
            </Button>
          )}
          <Button
            type="link" size="small"
            icon={<EditOutlined />}
            onClick={() => { setRenameTarget(record); setRenameOpen(true); }}
          >
            重命名
          </Button>
          <Popconfirm
            title="确定删除此工作空间？"
            description="删除后数据不可恢复"
            onConfirm={() => handleDelete(record.name)}
          >
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>工作空间管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
          新建工作空间
        </Button>
      </div>

      <Table
        dataSource={workspaces}
        columns={columns}
        rowKey="name"
        loading={loading}
        locale={{ emptyText: <Empty description="暂无工作空间，请创建" /> }}
      />

      {/* 创建对话框 */}
      <Modal
        title="新建工作空间"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={() => form.submit()}
      >
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="name" label="工作空间名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="例如: novel_xuanhuan" />
          </Form.Item>
          <Form.Item name="base_path" label="基础路径（可选）">
            <Input placeholder="默认为 ~/novels/" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 重命名对话框 */}
      <Modal
        title="重命名工作空间"
        open={renameOpen}
        onCancel={() => { setRenameOpen(false); setRenameTarget(null); }}
        onOk={() => renameForm.submit()}
      >
        <Form form={renameForm} layout="vertical" onFinish={handleRename}>
          <Form.Item name="new_name" label="新名称" rules={[{ required: true, message: '请输入新名称' }]}>
            <Input placeholder="新名称" defaultValue={renameTarget?.name} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}