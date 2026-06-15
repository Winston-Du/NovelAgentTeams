import { useEffect, useState } from 'react';
import {
  Table, Button, Space, Typography, Tag, Drawer,
  Descriptions, message, Modal, Form, Input, Select, Popconfirm, Spin,
} from 'antd';
import {
  PlusOutlined, EyeOutlined, DeleteOutlined,
  EditOutlined, BulbOutlined,
} from '@ant-design/icons';
import { contentApi } from '../../services/api';

const { Title } = Typography;
const { TextArea } = Input;

const FIELD_LABELS: Record<string, string> = {
  name: '姓名',
  role: '角色定位',
  identity: '身份',
  tier: '等级',
  character_type: '类型',
  age: '年龄',
  brief: '简介',
  appearance: '外貌描述',
  core_personality: '核心性格',
  personality: '性格描述',
  character_flaw: '性格缺陷',
  core_motivation: '核心动机',
  bottom_line: '底线',
  unique_speaking_style: '对话风格',
  background: '背景故事',
  abilities: '能力特长',
  relationships: '人际关系',
  notes: '备注',
};

export default function CharactersPage() {
  const [characters, setCharacters] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedChar, setSelectedChar] = useState<any>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editingChar, setEditingChar] = useState<any>(null);
  const [optimizing, setOptimizing] = useState<string | null>(null); // 正在优化的字段名
  const [createForm] = Form.useForm();
  const [editForm] = Form.useForm();

  const fetchCharacters = async () => {
    setLoading(true);
    try {
      const res = await contentApi.getCharacters();
      const data = res.data;
      setCharacters(Array.isArray(data) ? data : []);
    } catch {
      setCharacters([]);
      message.error('获取人物列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchCharacters(); }, []);

  const handleDelete = async (name: string) => {
    try {
      await contentApi.deleteCharacter(name);
      message.success('删除成功');
      fetchCharacters();
    } catch {
      message.error('删除失败');
    }
  };

  const handleCreate = async (values: any) => {
    try {
      await contentApi.createCharacter(values);
      message.success('创建成功');
      setCreateOpen(false);
      createForm.resetFields();
      fetchCharacters();
    } catch (e: any) {
      message.error(e.response?.data?.detail || '创建失败');
    }
  };

  const handleEdit = async (record: any) => {
    try {
      const res = await contentApi.getCharacter(record.name);
      if (res.data && typeof res.data === 'object') {
        setEditingChar(res.data);
        // 将数组字段转为字符串以便编辑
        const formValues = { ...res.data };
        if (Array.isArray(formValues.core_personality)) {
          formValues.core_personality = formValues.core_personality.join('、');
        }
        if (Array.isArray(formValues.personality)) {
          formValues.personality = formValues.personality.join('、');
        }
        if (typeof formValues.unique_speaking_style === 'object') {
          formValues.unique_speaking_style = JSON.stringify(formValues.unique_speaking_style, null, 2);
        }
        editForm.setFieldsValue(formValues);
        setEditOpen(true);
      } else {
        message.error('获取人物详情失败：数据格式异常');
      }
    } catch (e: any) {
      message.error(e.response?.data?.detail || '获取人物详情失败');
    }
  };

  const handleEditSubmit = async () => {
    try {
      const values = await editForm.validateFields();
      await contentApi.updateCharacter(editingChar.name, values);
      message.success('更新成功');
      setEditOpen(false);
      fetchCharacters();
    } catch (e: any) {
      if (e.errorFields) return; // 表单验证错误
      message.error(e.response?.data?.detail || '更新失败');
    }
  };

  const handleOptimize = async (field: string) => {
    if (!editingChar) return;
    const currentValue = editForm.getFieldValue(field) || '';
    if (!currentValue.trim()) {
      message.warning('当前字段为空，请先填写内容再优化');
      return;
    }

    setOptimizing(field);
    try {
      // 构建上下文（排除当前字段）
      const context: Record<string, unknown> = {};
      for (const key of Object.keys(FIELD_LABELS)) {
        if (key !== field && key !== 'tier' && key !== 'name') {
          const val = editingChar[key];
          if (val) {
            context[key] = typeof val === 'object' ? JSON.stringify(val) : val;
          }
        }
      }

      const res = await contentApi.optimizeCharacter({
        field,
        current_value: currentValue,
        character_name: editingChar.name,
        context,
      });

      const optimized = res.data?.optimized_value || '';
      if (optimized) {
        editForm.setFieldsValue({ [field]: optimized });
        message.success(`${FIELD_LABELS[field] || field} 优化完成`);
      }
    } catch (e: any) {
      message.error(e.response?.data?.detail || 'AI 优化失败');
    } finally {
      setOptimizing(null);
    }
  };

  const tierColor: Record<string, string> = {
    s_tier: 'gold', a_tier: 'purple', b_tier: 'blue', c_tier: 'default',
  };

  const characterTypeColor: Record<string, string> = {
    main: 'red', support: 'green', antagonist: 'orange',
    sidekick: 'cyan', mentor: 'blue', other: 'default',
  };
  const characterTypeLabel: Record<string, string> = {
    main: '主角', support: '配角', antagonist: '反派',
    sidekick: '助手', mentor: '导师', other: '其他',
  };

  const columns = [
    { title: '姓名', dataIndex: 'name', key: 'name', width: 100 },
    {
      title: '类型', dataIndex: 'character_type', key: 'character_type', width: 80,
      render: (t: string) => t ? (
        <Tag color={characterTypeColor[t] || 'default'}>{characterTypeLabel[t] || t}</Tag>
      ) : '-',
    },
    {
      title: '等级', dataIndex: 'tier', key: 'tier', width: 70,
      render: (tier: string) => tier ? (
        <Tag color={tierColor[tier] || 'default'}>{tier?.replace('_tier', '').toUpperCase()}</Tag>
      ) : '-',
    },
    { title: '角色', dataIndex: 'role', key: 'role', width: 100 },
    { title: '身份', dataIndex: 'identity', key: 'identity', width: 120, ellipsis: true },
    { title: '简介', dataIndex: 'brief', key: 'brief', ellipsis: true },
    {
      title: '操作', key: 'actions', width: 220,
      render: (_: any, record: any) => (
        <Space>
          <Button type="link" size="small" icon={<EyeOutlined />} onClick={async () => {
            try {
              const res = await contentApi.getCharacter(record.name);
              if (res.data && typeof res.data === 'object') {
                setSelectedChar(res.data);
                setDrawerOpen(true);
              } else {
                message.error('获取详情失败：数据格式异常');
              }
            } catch (e: any) {
              message.error(e.response?.data?.detail || '获取详情失败');
            }
          }}>
            查看
          </Button>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)}>
            编辑
          </Button>
          <Popconfirm title="确定删除？" onConfirm={() => handleDelete(record.name)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  // 编辑表单中支持 AI 优化的字段
  const optimizableFields = [
    'brief', 'appearance', 'personality', 'core_personality',
    'character_flaw', 'core_motivation', 'bottom_line', 'role',
    'identity', 'unique_speaking_style', 'background', 'abilities',
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>人物卡管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
          添加人物
        </Button>
      </div>

      <Table dataSource={characters} columns={columns} rowKey="name" loading={loading} locale={{ emptyText: '暂无人物卡数据' }} />

      {/* 详情抽屉 */}
      <Drawer
        title={selectedChar?.name || '人物详情'}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        size="large"
      >
        {selectedChar && (
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="类型">
              {selectedChar.character_type
                ? <Tag color={characterTypeColor[selectedChar.character_type] || 'default'}>{characterTypeLabel[selectedChar.character_type] || selectedChar.character_type}</Tag>
                : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="等级">{selectedChar.tier || '-'}</Descriptions.Item>
            <Descriptions.Item label="角色">{selectedChar.role || '-'}</Descriptions.Item>
            {selectedChar.identity && <Descriptions.Item label="身份">{selectedChar.identity}</Descriptions.Item>}
            {selectedChar.age && <Descriptions.Item label="年龄">{selectedChar.age}</Descriptions.Item>}
            {selectedChar.brief && <Descriptions.Item label="简介">{selectedChar.brief}</Descriptions.Item>}
            {selectedChar.appearance && <Descriptions.Item label="外貌">{selectedChar.appearance}</Descriptions.Item>}
            {selectedChar.core_personality && (
              <Descriptions.Item label="核心性格">
                {Array.isArray(selectedChar.core_personality)
                  ? selectedChar.core_personality.join('、')
                  : selectedChar.core_personality}
              </Descriptions.Item>
            )}
            {selectedChar.personality && (
              <Descriptions.Item label="性格">
                {Array.isArray(selectedChar.personality)
                  ? selectedChar.personality.join('、')
                  : selectedChar.personality}
              </Descriptions.Item>
            )}
            {selectedChar.character_flaw && <Descriptions.Item label="性格缺陷">{selectedChar.character_flaw}</Descriptions.Item>}
            {selectedChar.core_motivation && <Descriptions.Item label="核心动机">{selectedChar.core_motivation}</Descriptions.Item>}
            {selectedChar.bottom_line && <Descriptions.Item label="底线">{selectedChar.bottom_line}</Descriptions.Item>}
            {selectedChar.unique_speaking_style && (
              <Descriptions.Item label="对话风格">
                {typeof selectedChar.unique_speaking_style === 'object'
                  ? (
                    <div>
                      {selectedChar.unique_speaking_style.tone && (
                        <div>语气: {selectedChar.unique_speaking_style.tone}</div>
                      )}
                      {selectedChar.unique_speaking_style.characteristics && (
                        <div>特点: {Array.isArray(selectedChar.unique_speaking_style.characteristics)
                          ? selectedChar.unique_speaking_style.characteristics.join('、')
                          : selectedChar.unique_speaking_style.characteristics}</div>
                      )}
                    </div>
                  )
                  : selectedChar.unique_speaking_style}
              </Descriptions.Item>
            )}
          </Descriptions>
        )}
      </Drawer>

      {/* 创建对话框 */}
      <Modal
        title="添加人物"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={() => createForm.submit()}
        width={600}
      >
        <Form form={createForm} layout="vertical" onFinish={handleCreate}>
          <Form.Item name="name" label="姓名" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="tier" label="等级">
            <Select options={[
              { label: 'S 级', value: 's_tier' },
              { label: 'A 级', value: 'a_tier' },
              { label: 'B 级', value: 'b_tier' },
            ]} />
          </Form.Item>
          <Form.Item name="role" label="角色">
            <Input placeholder="例如: 主角、反派、导师" />
          </Form.Item>
          <Form.Item name="brief" label="简介">
            <TextArea rows={2} />
          </Form.Item>
          <Form.Item name="appearance" label="外貌描述">
            <TextArea rows={2} />
          </Form.Item>
          <Form.Item name="core_motivation" label="核心动机">
            <Input />
          </Form.Item>
        </Form>
      </Modal>

      {/* 编辑对话框 */}
      <Modal
        title={`编辑人物 - ${editingChar?.name || ''}`}
        open={editOpen}
        onCancel={() => { setEditOpen(false); setOptimizing(null); }}
        onOk={handleEditSubmit}
        width={700}
        okText="保存"
        cancelText="取消"
        destroyOnHidden
      >
        <Form form={editForm} layout="vertical">
          <Form.Item name="name" label="姓名">
            <Input disabled />
          </Form.Item>
          <Form.Item name="tier" label="等级">
            <Select options={[
              { label: 'S 级', value: 's_tier' },
              { label: 'A 级', value: 'a_tier' },
              { label: 'B 级', value: 'b_tier' },
              { label: 'C 级', value: 'c_tier' },
            ]} />
          </Form.Item>
          <Form.Item name="character_type" label="类型">
            <Select options={[
              { label: '主角', value: 'main' },
              { label: '配角', value: 'support' },
              { label: '反派', value: 'antagonist' },
              { label: '助手', value: 'sidekick' },
              { label: '导师', value: 'mentor' },
              { label: '其他', value: 'other' },
            ]} />
          </Form.Item>
          {['role', 'identity', 'age', 'brief', 'appearance', 'core_personality',
            'personality', 'character_flaw', 'core_motivation', 'bottom_line',
            'unique_speaking_style', 'background', 'abilities', 'notes'].map((field) => (
            <Form.Item key={field} name={field} label={FIELD_LABELS[field] || field}>
              <div style={{ display: 'flex', gap: 8 }}>
                {field === 'brief' || field === 'appearance' || field === 'personality' ||
                 field === 'core_personality' || field === 'unique_speaking_style' ||
                 field === 'background' || field === 'abilities' || field === 'notes' ? (
                  <TextArea rows={field === 'brief' ? 2 : 3} style={{ flex: 1 }} />
                ) : (
                  <Input style={{ flex: 1 }} />
                )}
                {optimizableFields.includes(field) && (
                  <Button
                    icon={<BulbOutlined />}
                    loading={optimizing === field}
                    onClick={() => handleOptimize(field)}
                    style={{ flexShrink: 0 }}
                    title="通过模型优化内容"
                  >
                    AI优化
                  </Button>
                )}
              </div>
            </Form.Item>
          ))}
        </Form>
      </Modal>
    </div>
  );
}