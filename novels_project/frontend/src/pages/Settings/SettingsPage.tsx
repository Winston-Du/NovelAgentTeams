import { useEffect, useState } from 'react';
import {
  Card, Typography, Form, Select, Switch, Button,
  InputNumber, message, Space, Flex, Popconfirm, Divider,
  Modal, Input, Tag, Row, Col, Collapse, ConfigProvider, theme as antTheme,
} from 'antd';
import {
  SaveOutlined, UploadOutlined, DownloadOutlined, DeleteOutlined,
  PlusOutlined, EditOutlined, SearchOutlined,
  BulbOutlined, ExperimentOutlined, EyeInvisibleOutlined, EyeOutlined,
  WifiOutlined, SettingOutlined,
} from '@ant-design/icons';
import { settingsApi } from '../../services/api';
import { ensureArray } from '../../utils/dataGuards';
import { useWorkspaceStore } from '../../stores/workspaceStore';

const { Title, Text } = Typography;
const { TextArea } = Input;
const { Panel } = Collapse;

interface ModelInfo {
  id: string;
  name: string;
  max_tokens?: number;
  context_window?: number;
  supports_streaming?: boolean;
  supports_json_mode?: boolean;
}

interface AdvancedConfig {
  temperature?: number;
  top_p?: number;
  max_tokens?: number;
  frequency_penalty?: number;
  presence_penalty?: number;
  timeout?: number;
  system_prompt?: string;
}

interface ProviderInfo {
  id: string;
  name: string;
  base_url: string;
  api_key: string;
  protocol: string;
  models: ModelInfo[];
  advanced?: AdvancedConfig;
}

const PROTOCOL_OPTIONS = [
  { label: 'OpenAI 兼容 (Chat Completions)', value: 'OpenAI 兼容 (Chat Completions)' },
  { label: 'Anthropic Claude', value: 'Anthropic Claude' },
  { label: 'Google Gemini', value: 'Google Gemini' },
  { label: 'Ollama (Local)', value: 'Ollama (Local)' },
];

export default function SettingsPage() {
  const [settings, setSettings] = useState<any>(null);
  const [backups, setBackups] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [form] = Form.useForm();

  // 工作空间管理
  const { fetchWorkspaces } = useWorkspaceStore();

  // 模型供应商管理
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [providersLoading, setProvidersLoading] = useState(false);
  const [providerModalOpen, setProviderModalOpen] = useState(false);
  const [editingProvider, setEditingProvider] = useState<ProviderInfo | null>(null);
  const [providerForm] = Form.useForm();
  const [testingProviderId, setTestingProviderId] = useState<string | null>(null);
  const [modelSearch, setModelSearch] = useState('');
  
  const [keyVisible, setKeyVisible] = useState<Record<string, boolean>>({});
  const [vectorApiKeyVisible, setVectorApiKeyVisible] = useState(false);
  const [testingVectorConnection, setTestingVectorConnection] = useState(false);
  const [testResult, setTestResult] = useState<'success' | 'error' | null>(null);
  const [testMessage, setTestMessage] = useState('');
  const [initializingVectorDb, setInitializingVectorDb] = useState(false);
  const [initProgress, setInitProgress] = useState(0);
  const [showInitProgress, setShowInitProgress] = useState(false);
  const [modelChanged, setModelChanged] = useState(false);
  
  // 模型配置弹窗
  const [modelConfigModalOpen, setModelConfigModalOpen] = useState(false);
  const [editingModel, setEditingModel] = useState<ModelInfo | null>(null);
  const [modelConfigForm] = Form.useForm();

  const handleVectorTest = async () => {
    setTestingVectorConnection(true);
    setTestResult(null);
    setTestMessage('');
    
    try {
      const values = form.getFieldsValue(['vector_retrieval']);
      const vectorConfig = values.vector_retrieval;
      
      const res = await settingsApi.testVectorProvider({
        api_endpoint: vectorConfig.api_endpoint,
        api_key: vectorConfig.api_key,
        model_id: vectorConfig.embedding_model,
        timeout: vectorConfig.timeout || 60,
      });
      
      setTestResult('success');
      setTestMessage(res.data?.message || '连接测试成功');
    } catch (err: any) {
      setTestResult('error');
      setTestMessage(err.response?.data?.detail || err.message || '连接测试失败');
    } finally {
      setTestingVectorConnection(false);
    }
  };

  const handleVectorInit = async () => {
    setInitializingVectorDb(true);
    setShowInitProgress(true);
    setInitProgress(0);
    
    try {
      const response = await fetch('/api/vector/init', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new Error(errorData?.detail || '初始化失败');
      }
      
      const data = await response.json();
      setInitProgress(100);
      
      message.success(`向量库初始化完成，共 ${data.document_count || 0} 个文档`);
    } catch (err: any) {
      message.error(`向量库初始化失败: ${err.message}`);
    } finally {
      setInitializingVectorDb(false);
    }
  };

  const handleEmbeddingModelChange = () => {
    setModelChanged(true);
  };

  useEffect(() => {
    loadSettings();
    loadBackups();
    loadProviders();
    fetchWorkspaces();
  }, []);

  const loadSettings = async () => {
    try {
      console.log('[SettingsPage] loadSettings: 开始请求系统设置');
      const res = await settingsApi.get();
      console.log('[SettingsPage] loadSettings: 原始响应类型', typeof res.data, res.data);
      const data = res.data && typeof res.data === 'object' && !Array.isArray(res.data) ? res.data : {};
      setSettings(data);
      form.setFieldsValue(data);
    } catch (err) {
      console.error('[SettingsPage] loadSettings: 请求失败', err);
      message.error('获取设置失败');
    }
  };

  const loadBackups = async () => {
    try {
      console.log('[SettingsPage] loadBackups: 开始请求备份列表');
      const res = await settingsApi.backups();
      console.log('[SettingsPage] loadBackups: 原始响应类型', typeof res.data, '是否为数组', Array.isArray(res.data));
      setBackups(ensureArray(res.data));
    } catch (err) {
      console.error('[SettingsPage] loadBackups: 请求失败', err);
    }
  };

  const loadProviders = async () => {
    setProvidersLoading(true);
    try {
      console.log('[SettingsPage] loadProviders: 开始请求模型供应商列表');
      const res = await settingsApi.getModels();
      console.log('[SettingsPage] loadProviders: 原始响应类型', typeof res.data);
      const providersObj = res.data?.providers || {};
      const providersData: ProviderInfo[] = Object.entries(providersObj).map(
        ([id, data]: [string, any]) => ({
          id,
          name: data.name || id,
          base_url: data.base_url || '',
          api_key: data.api_key || '',
          protocol: data.protocol || 'OpenAI 兼容 (Chat Completions)',
          models: ensureArray<ModelInfo>(data.models),
          advanced: data.advanced || null,
        }),
      );
      console.log('[SettingsPage] loadProviders: 转换后数组长度', providersData.length);
      setProviders(providersData);
    } catch (err) {
      console.error('[SettingsPage] loadProviders: 请求失败', err);
    } finally { setProvidersLoading(false); }
  };

  const handleSave = async (values: any) => {
    setLoading(true);
    try {
      await settingsApi.update(values);
      message.success('设置已保存');
      setSettings(values);
    } catch {
      message.error('保存失败');
    } finally {
      setLoading(false);
    }
  };

  const handleBackup = async () => {
    try {
      await settingsApi.createBackup();
      message.success('备份创建成功');
      loadBackups();
    } catch {
      message.error('备份失败');
    }
  };

  const handleRestore = async (name: string) => {
    try {
      await settingsApi.restore(name);
      message.success('数据已恢复');
    } catch {
      message.error('恢复失败');
    }
  };

  // ---- 模型供应商操作 ----
  const openAddProvider = () => {
    setEditingProvider(null);
    providerForm.resetFields();
    providerForm.setFieldsValue({
      protocol: 'OpenAI 兼容 (Chat Completions)',
      models: [{ id: '', name: '' }],
      advanced: {
        temperature: 0.7,
        top_p: 1.0,
        max_tokens: 4096,
        frequency_penalty: 0.0,
        presence_penalty: 0.0,
        timeout: 120,
        system_prompt: '',
      },
    });
    setProviderModalOpen(true);
  };

  const openEditProvider = (provider: ProviderInfo) => {
    setEditingProvider(provider);
    const defaultAdvanced = provider.advanced || {
      temperature: 0.7,
      top_p: 1.0,
      max_tokens: 4096,
      frequency_penalty: 0.0,
      presence_penalty: 0.0,
      timeout: 120,
      system_prompt: '',
    };
    providerForm.setFieldsValue({
      name: provider.name,
      base_url: provider.base_url,
      api_key: provider.api_key,
      protocol: provider.protocol || 'OpenAI 兼容 (Chat Completions)',
      models: provider.models.length > 0 ? provider.models : [{ id: '', name: '' }],
      advanced: defaultAdvanced,
    });
    setProviderModalOpen(true);
  };

  const handleProviderSave = async () => {
    try {
      const values = await providerForm.validateFields();
      const payload = {
        name: values.name,
        base_url: values.base_url,
        api_key: values.api_key,
        protocol: values.protocol || 'OpenAI 兼容 (Chat Completions)',
        models: values.models || [],
        advanced: values.advanced || null,
      };

      if (editingProvider) {
        await settingsApi.updateModelProvider(editingProvider.id, payload);
        message.success('供应商已更新');
      } else {
        await settingsApi.saveModelProvider(values.provider_key, payload);
        message.success('供应商已添加');
      }

      setProviderModalOpen(false);
      loadProviders();
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error('操作失败');
    }
  };

  const handleProviderDelete = async (providerId: string) => {
    try {
      await settingsApi.deleteModelProvider(providerId);
      message.success('供应商已删除');
      loadProviders();
    } catch {
      message.error('删除失败');
    }
  };

  const handleProviderTest = async (provider: ProviderInfo) => {
    if (!provider.models || provider.models.length === 0) {
      message.warning('该供应商未配置模型');
      return;
    }
    const testModel = provider.models[0].id;
    setTestingProviderId(provider.id);
    try {
      const res = await settingsApi.testProvider({
        base_url: provider.base_url,
        api_key: provider.api_key,
        model_id: testModel,
        protocol: provider.protocol,
      });
      message.success('连接成功');
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message;
      message.error(`测试失败: ${errorMsg}`);
    } finally {
      setTestingProviderId(null);
    }
  };

  const isMultimodalModel = (modelId: string): boolean => {
    const multimodalKeywords = ['vision', 'gpt-4v', 'gpt-4o', 'dall-e', 'image', 'multi', 'vision-pro', 'kimi', 'qwen-vl'];
    const lowerModelId = modelId.toLowerCase();
    return multimodalKeywords.some(keyword => lowerModelId.includes(keyword));
  };

  const testModelConnection = async (provider: ProviderInfo, model: ModelInfo) => {
    setTestingProviderId(provider.id);
    try {
      await settingsApi.testProvider({
        base_url: provider.base_url,
        api_key: provider.api_key,
        model_id: model.id,
        protocol: provider.protocol,
      });
      message.success(`模型 ${model.id} 连接成功`);
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message;
      message.error(`模型 ${model.id} 测试失败: ${errorMsg}`);
    } finally {
      setTestingProviderId(null);
    }
  };

  const openModelConfig = (model: ModelInfo) => {
    setEditingModel(model);
    modelConfigForm.setFieldsValue({
      max_tokens: model.max_tokens || 4096,
      context_window: model.context_window || 8192,
    });
    setModelConfigModalOpen(true);
  };

  const handleRevokeKey = async () => {
    if (!editingProvider) return;
    Modal.confirm({
      title: '确认撤销授权？',
      content: '将清除当前供应商的 API 密钥，撤销后该供应商无法使用，除非重新输入密钥。',
      okText: '确认撤销',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await settingsApi.updateModelProvider(editingProvider.id, { ...editingProvider, api_key: '' });
          message.success('授权已撤销');
          providerForm.setFieldsValue({ api_key: '' });
          loadProviders();
        } catch {
          message.error('撤销失败');
        }
      },
    });
  };

  // ---- 模型操作 ----
  const handleDeleteModel = async (providerId: string, modelId: string) => {
    const provider = providers.find(p => p.id === providerId);
    if (!provider) return;
    const updatedModels = provider.models.filter(m => m.id !== modelId);
    try {
      await settingsApi.updateModelProvider(providerId, {
        ...provider,
        models: updatedModels,
      });
      message.success('模型已删除');
      loadProviders();
    } catch {
      message.error('删除失败');
    }
  };

  const maskApiKey = (key: string) => {
    if (!key) return '未设置';
    if (key.length <= 8) return '****';
    return key.substring(0, 4) + '****' + key.substring(key.length - 4);
  };

  // 过滤出符合搜索的模型
  const filterModels = (models: ModelInfo[], query: string): ModelInfo[] => {
    if (!query.trim()) return models;
    const q = query.toLowerCase();
    return models.filter(m =>
      m.id.toLowerCase().includes(q) ||
      (m.name || '').toLowerCase().includes(q)
    );
  };

  if (!settings) return null;

  return (
    <div>
      <Title level={4}>基础设置</Title>

      <Form
        form={form}
        layout="vertical"
        initialValues={settings}
        onFinish={handleSave}
        style={{ maxWidth: 600 }}
      >
        <Card title="界面设置" style={{ marginBottom: 16 }}>
          <Form.Item name="theme" label="主题">
            <Select options={[
              { label: '浅色模式', value: 'light' },
              { label: '深色模式', value: 'dark' },
            ]} />
          </Form.Item>
          <Form.Item name="language" label="语言">
            <Select options={[
              { label: '中文', value: 'zh' },
              { label: 'English', value: 'en' },
            ]} />
          </Form.Item>
        </Card>

        <Card title="编辑器设置" style={{ marginBottom: 16 }}>
          <Form.Item name={['editor', 'font_size']} label="字体大小">
            <InputNumber min={12} max={24} />
          </Form.Item>
          <Form.Item name={['editor', 'auto_save']} label="自动保存" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Card>

        <Card title="通知设置" style={{ marginBottom: 16 }}>
          <Form.Item name={['notifications', 'enabled']} label="启用通知" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name={['notifications', 'chapter_complete']} label="章节完成通知" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name={['notifications', 'sync_complete']} label="同步完成通知" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name={['notifications', 'backup_reminder']} label="备份提醒" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Card>

        <Card title="向量检索 API 配置" style={{ marginBottom: 16 }}>
          <Form.Item
            name={['vector_retrieval', 'enabled']}
            label="启用向量检索"
            valuePropName="checked"
            extra="启用后将使用 Embedding 模型提升检索效果"
          >
            <Switch />
          </Form.Item>
          
          <Form.Item
            name={['vector_retrieval', 'api_endpoint']}
            label="API 端点 URL"
            rules={[
              { required: true, message: '请输入 API 端点 URL' },
              { type: 'url', message: '请输入有效的 URL' },
            ]}
          >
            <Input placeholder="https://api.siliconflow.cn/v1" />
          </Form.Item>
          
          <Form.Item
            name={['vector_retrieval', 'api_key']}
            label="API 密钥"
            extra="支持环境变量引用如 ${siliconflow_api}，建议优先使用环境变量"
          >
            <Input.Password
              placeholder="输入 API Key 或 ${ENV_VAR}"
              iconRender={(visible) => (visible ? <EyeOutlined /> : <EyeInvisibleOutlined />)}
              visibilityToggle={{
                visible: vectorApiKeyVisible,
                onVisibleChange: setVectorApiKeyVisible,
              }}
            />
          </Form.Item>
          
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name={['vector_retrieval', 'embedding_model']}
                label="模型 ID"
                rules={[{ required: true, message: '请输入模型 ID' }]}
                extra=""
              >
                <Input
                  placeholder="例如: BAAI/bge-large-zh-v1.5"
                  onChange={handleEmbeddingModelChange}
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name={['vector_retrieval', 'timeout']}
                label="超时时间 (秒)"
                rules={[{ required: true, message: '请输入超时时间' }]}
              >
                <InputNumber min={10} max={300} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>

          <Space style={{ marginBottom: 16 }}>
            <Button
              type="default"
              icon={<ExperimentOutlined />}
              onClick={handleVectorTest}
              loading={testingVectorConnection}
            >
              测试连接
            </Button>
            <Button
              type="primary"
              icon={<UploadOutlined />}
              onClick={handleVectorInit}
              loading={initializingVectorDb}
              disabled={!form.getFieldValue(['vector_retrieval', 'enabled'])}
            >
              初始化向量库
            </Button>
          </Space>

          {testResult && (
            <div
              style={{
                padding: 12,
                borderRadius: 6,
                marginBottom: 16,
                background: testResult === 'success' ? '#f6ffed' : '#fff2f0',
                border: `1px solid ${testResult === 'success' ? '#b7eb8f' : '#ffccc7'}`,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center' }}>
                {testResult === 'success' ? (
                  <span role="img" aria-label="success" style={{ marginRight: 8, fontSize: 20 }}>
                    ✓
                  </span>
                ) : (
                  <span role="img" aria-label="error" style={{ marginRight: 8, fontSize: 20 }}>
                    ✗
                  </span>
                )}
                <span style={{ color: testResult === 'success' ? '#52c41a' : '#ff4d4f' }}>
                  {testMessage}
                </span>
              </div>
            </div>
          )}

          {showInitProgress && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ marginBottom: 8 }}>
                <span style={{ fontSize: 14, fontWeight: 500 }}>初始化进度</span>
              </div>
              <div style={{ background: '#f0f0f0', borderRadius: 6, overflow: 'hidden' }}>
                <div
                  style={{
                    height: 24,
                    background: '#1890ff',
                    transition: 'width 0.3s ease',
                    width: `${initProgress}%`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <span style={{ color: '#fff', fontSize: 12, fontWeight: 500 }}>
                    {initProgress}%
                  </span>
                </div>
              </div>
            </div>
          )}

          {modelChanged && form.getFieldValue(['vector_retrieval', 'enabled']) && (
            <div
              style={{
                padding: 12,
                background: '#fffbe6',
                borderRadius: 6,
                marginBottom: 16,
                border: '1px solid #ffe58f',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
                <BulbOutlined style={{ color: '#faad14', marginRight: 8 }} />
                <span style={{ fontWeight: 500 }}>模型已更改</span>
              </div>
              <p style={{ margin: 0, fontSize: 13, color: '#d48806' }}>
                检测到 Embedding 模型已更改，建议重新初始化向量库以应用新模型。
              </p>
            </div>
          )}
          
          <div style={{ padding: 12, background: '#f5f5f5', borderRadius: 6 }}>
            <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
              <BulbOutlined style={{ color: '#faad14', marginRight: 8 }} />
              <span style={{ fontWeight: 500 }}>使用说明</span>
            </div>
            <ul style={{ margin: 0, paddingLeft: 24, fontSize: 13, color: '#666' }}>
              <li style={{ marginBottom: 4 }}>向量检索用于在写作时检索相似样例，提供写作参考</li>
              <li>推荐使用环境变量配置：export siliconflow_api=your_key</li>
            </ul>
          </div>
        </Card>

        <Button type="primary" htmlType="submit" icon={<SaveOutlined />} loading={loading}>
          保存设置
        </Button>
      </Form>

      <Divider />

      <Card title="数据备份与恢复" style={{ maxWidth: 600 }}>
        <Space style={{ marginBottom: 16 }}>
          <Button icon={<UploadOutlined />} onClick={handleBackup}>
            创建备份
          </Button>
        </Space>

        <Flex
          vertical
          gap="small"
          style={{ width: '100%' }}
        >
          {backups.length === 0 ? (
            <Text type="secondary">暂无备份</Text>
          ) : (
            backups.map((item: any) => (
              <Flex
                key={item.name}
                align="center"
                justify="space-between"
                style={{ padding: '8px 12px', border: '1px solid #f0f0f0', borderRadius: 6 }}
              >
                <Flex vertical gap={2}>
                  <Text strong>{item.name}</Text>
                  <Space size="middle">
                    <Text type="secondary">{item.size ? `${(item.size / 1024).toFixed(1)} KB` : ''}</Text>
                    <Text type="secondary">{item.created_at}</Text>
                  </Space>
                </Flex>
                <Popconfirm title="确定恢复此备份？" onConfirm={() => handleRestore(item.name)}>
                  <Button type="link" icon={<DownloadOutlined />}>恢复</Button>
                </Popconfirm>
              </Flex>
            ))
          )}
        </Flex>
      </Card>

      <Divider />

      <Card
        title="模型供应商管理"
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={openAddProvider}>
            添加供应商
          </Button>
        }
        style={{ maxWidth: 900 }}
        loading={providersLoading}
      >
        {providers.length === 0 ? (
          <Text type="secondary">暂无模型供应商，点击&quot;添加供应商&quot;开始配置</Text>
        ) : (
          <>
            {/* 供应商列表 */}
            {providers.map((provider) => (
              <div
                key={provider.id}
                style={{
                  border: '1px solid #f0f0f0',
                  borderRadius: 8,
                  padding: 16,
                  marginBottom: 16,
                  background: '#fff',
                }}
              >
                <Row justify="space-between" align="middle" style={{ marginBottom: 12 }}>
                  <div>
                    <Space>
                      <Text strong style={{ fontSize: 16 }}>{provider.name}</Text>
                      <Tag color="blue">{provider.id}</Tag>
                      <Tag color="geekblue">{provider.protocol}</Tag>
                    </Space>
                    <div style={{ marginTop: 8, color: '#666', fontSize: 13 }}>
                      <Text code>{provider.base_url}</Text>
                      <span style={{ marginLeft: 16 }}>
                        API Key: <Text code>{maskApiKey(provider.api_key)}</Text>
                      </span>
                    </div>
                  </div>
                  <Space>
                    <Button
                      icon={<ExperimentOutlined />}
                      onClick={() => handleProviderTest(provider)}
                      loading={testingProviderId === provider.id}
                    >
                      测试
                    </Button>
                    <Button
                      icon={<EditOutlined />}
                      onClick={() => openEditProvider(provider)}
                    >
                      配置
                    </Button>
                    <Popconfirm
                      title="确定删除此供应商？"
                      onConfirm={() => handleProviderDelete(provider.id)}
                      okText="删除"
                      okType="danger"
                      cancelText="取消"
                    >
                      <Button danger icon={<DeleteOutlined />}>删除</Button>
                    </Popconfirm>
                  </Space>
                </Row>

                {/* 模型列表 */}
                <Divider style={{ margin: '12px 0' }} />

                <Input
                  placeholder="搜索模型..."
                  prefix={<SearchOutlined />}
                  allowClear
                  value={modelSearch}
                  onChange={(e) => setModelSearch(e.target.value)}
                  style={{ marginBottom: 12, maxWidth: 400 }}
                />

                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {filterModels(provider.models, modelSearch).map((model) => (
                    <div
                      key={model.id}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        padding: '12px 16px',
                        border: '1px solid #f0f0f0',
                        borderRadius: 6,
                        background: '#fafafa',
                      }}
                    >
                      <div>
                        <Text strong>{model.id}</Text>
                        <div style={{ color: '#8c8c8c', fontSize: 12, marginTop: 2 }}>
                          {model.name || model.id}
                        </div>
                      </div>
                      <Space>
                        <Tag color={isMultimodalModel(model.id) ? 'purple' : 'default'}>
                          {isMultimodalModel(model.id) ? '多模态' : '文本'}
                        </Tag>
                        <Tag color="blue">用户添加</Tag>
                        <Button
                          type="text"
                          size="small"
                          icon={<WifiOutlined />}
                          title="测试模型连通性"
                          onClick={() => testModelConnection(provider, model)}
                        />
                        <Button
                          type="text"
                          size="small"
                          icon={<SettingOutlined />}
                          title="模型参数配置"
                          onClick={() => openModelConfig(model)}
                        />
                        <Popconfirm
                          title="确定删除此模型？"
                          onConfirm={() => handleDeleteModel(provider.id, model.id)}
                          okText="删除"
                          okType="danger"
                          cancelText="取消"
                        >
                          <Button type="text" size="small" danger icon={<DeleteOutlined />} />
                        </Popconfirm>
                      </Space>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </>
        )}
      </Card>

      {/* 添加/编辑供应商弹窗 */}
      <Modal
        title={editingProvider ? '配置模型供应商' : '添加模型供应商'}
        open={providerModalOpen}
        onCancel={() => setProviderModalOpen(false)}
        onOk={handleProviderSave}
        width={700}
        destroyOnHidden
        okText="保存"
        cancelText="取消"
        okButtonProps={{
          style: {
            backgroundColor: '#fa8c16',
            borderColor: '#fa8c16',
          },
        }}
      >
        <Form form={providerForm} layout="vertical">
          {!editingProvider && (
            <Form.Item
              name="provider_key"
              label="供应商标识 (Key)"
              rules={[{ required: true, message: '请输入供应商标识' }]}
              extra="唯一标识符，例如 openai、deepseek"
            >
              <Input placeholder="例如: openai" />
            </Form.Item>
          )}
          <Form.Item
            name="name"
            label="供应商名称"
            rules={[{ required: true, message: '请输入供应商名称' }]}
          >
            <Input placeholder="例如: OpenAI" />
          </Form.Item>
          <Form.Item
            name="protocol"
            label="协议"
            rules={[{ required: true, message: '请选择协议' }]}
            extra="为当前配置选择提供商 API 协议"
          >
            <Select options={PROTOCOL_OPTIONS} />
          </Form.Item>
          <Form.Item
            name="base_url"
            label="基础 URL"
            rules={[{ required: true, message: '请输入 Base URL' }]}
            extra="OpenAI 兼容端点，例如 https://api.example.com（仅在你的服务要求时再追加 /v1）"
          >
            <Input placeholder="例如: https://api.openai.com/v1 或 https://integrate.api.nvidia.com/v1" />
          </Form.Item>
          <Form.Item
            name="api_key"
            label="API 密钥"
            extra="留空以保持当前密钥，支持环境变量引用如 ${OPENAI_API_KEY}"
          >
            <Input.Password
              placeholder="输入 API Key 或 ${ENV_VAR}"
              iconRender={(visible) => (visible ? <EyeOutlined /> : <EyeInvisibleOutlined />)}
            />
          </Form.Item>

          {/* 进阶配置 - 折叠面板 */}
          <Collapse
            style={{ background: '#fff', marginBottom: 8 }}
            items={[{
              key: '1',
              label: <span style={{ fontWeight: 500 }}>进阶配置</span>,
              children: (
                <Row gutter={16}>
                  <Col span={8}>
                    <Form.Item
                      name={['advanced', 'temperature']}
                      label="Temperature"
                      extra="控制输出随机性 (0-2)"
                    >
                      <InputNumber min={0} max={2} step={0.1} style={{ width: '100%' }} />
                    </Form.Item>
                  </Col>
                  <Col span={8}>
                    <Form.Item
                      name={['advanced', 'top_p']}
                      label="Top P"
                      extra="核采样阈值 (0-1)"
                    >
                      <InputNumber min={0} max={1} step={0.05} style={{ width: '100%' }} />
                    </Form.Item>
                  </Col>
                  <Col span={8}>
                    <Form.Item
                      name={['advanced', 'max_tokens']}
                      label="最大 Token 数"
                      extra="单次调用的最大输出长度"
                    >
                      <InputNumber min={1} max={128000} style={{ width: '100%' }} />
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item
                      name={['advanced', 'frequency_penalty']}
                      label="频率惩罚"
                      extra="-2 到 2 之间，正值降低重复"
                    >
                      <InputNumber min={-2} max={2} step={0.1} style={{ width: '100%' }} />
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item
                      name={['advanced', 'presence_penalty']}
                      label="存在惩罚"
                      extra="-2 到 2 之间，正值鼓励新话题"
                    >
                      <InputNumber min={-2} max={2} step={0.1} style={{ width: '100%' }} />
                    </Form.Item>
                  </Col>
                  <Col span={24}>
                    <Form.Item
                      name={['advanced', 'timeout']}
                      label="超时时间 (秒)"
                      extra="API 调用超时秒数"
                    >
                      <InputNumber min={1} max={600} style={{ width: 200 }} />
                    </Form.Item>
                  </Col>
                  <Col span={24}>
                    <Form.Item
                      name={['advanced', 'system_prompt']}
                      label="全局 System Prompt"
                      extra="可选，对所有调用附加的系统提示词"
                    >
                      <TextArea
                        rows={3}
                        placeholder="例如：你是一个专业的小说编辑助手，帮助用户进行创意写作..."
                      />
                    </Form.Item>
                  </Col>
                </Row>
              ),
            }]}
          />

          {/* 模型列表 */}
          <Divider plain style={{ margin: '16px 0' }}>模型列表</Divider>
          <Form.List name="models">
            {(fields, { add, remove }) => (
              <div style={{ maxHeight: 300, overflowY: 'auto', border: '1px solid #e8e8e8', borderRadius: 6 }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead style={{ position: 'sticky', top: 0, background: '#fafafa', zIndex: 1 }}>
                    <tr>
                      <th
                        style={{
                          padding: '12px 16px',
                          textAlign: 'left',
                          fontSize: 14,
                          fontWeight: 500,
                          color: '#333',
                          borderBottom: '1px solid #e8e8e8',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        模型标识符
                        <div style={{ fontSize: 12, fontWeight: 400, color: '#8c8c8c', marginTop: 4 }}>
                          模型的唯一标识符，调用 API 时使用
                        </div>
                      </th>
                      <th
                        style={{
                          padding: '12px 16px',
                          textAlign: 'left',
                          fontSize: 14,
                          fontWeight: 500,
                          color: '#333',
                          borderBottom: '1px solid #e8e8e8',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        系统模型名称
                        <div style={{ fontSize: 12, fontWeight: 400, color: '#8c8c8c', marginTop: 4 }}>
                          在系统界面中展示的友好名称
                        </div>
                      </th>
                      <th
                        style={{
                          padding: '12px 16px',
                          textAlign: 'center',
                          fontSize: 14,
                          fontWeight: 500,
                          color: '#333',
                          borderBottom: '1px solid #e8e8e8',
                          width: 60,
                        }}
                      >
                        操作
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {fields.map(({ key, name, ...rest }) => (
                      <tr
                        key={key}
                        style={{
                          borderBottom: '1px solid #f0f0f0',
                        }}
                      >
                        <td style={{ padding: '12px 16px' }}>
                          <Form.Item
                            {...rest}
                            name={[name, 'id']}
                            rules={[{ required: true, message: '请输入模型 ID' }]}
                            style={{ marginBottom: 0 }}
                          >
                            <Input placeholder="模型 ID (如 gpt-4o)" />
                          </Form.Item>
                        </td>
                        <td style={{ padding: '12px 16px' }}>
                          <Form.Item
                            {...rest}
                            name={[name, 'name']}
                            rules={[{ required: true, message: '请输入模型名称' }]}
                            style={{ marginBottom: 0 }}
                          >
                            <Input placeholder="模型名称 (如 GPT-4o)" />
                          </Form.Item>
                        </td>
                        <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                          <DeleteOutlined
                            onClick={() => remove(name)}
                            style={{ color: '#ff4d4f', cursor: 'pointer', fontSize: 16 }}
                          />
                        </td>
                      </tr>
                    ))}
                    <tr>
                      <td colSpan={3} style={{ padding: 0 }}>
                        <Button
                          type="dashed"
                          onClick={() => add({ id: '', name: '' })}
                          block
                          icon={<PlusOutlined />}
                          style={{ borderRadius: 0 }}
                        >
                          添加模型
                        </Button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            )}
          </Form.List>

          {/* 撤销授权 - 仅编辑模式显示 */}
          {editingProvider && editingProvider.api_key && (
            <>
              <Divider style={{ margin: '24px 0 12px 0' }} />
              <div style={{ textAlign: 'left' }}>
                <Button
                  type="text"
                  danger
                  onClick={handleRevokeKey}
                  style={{ paddingLeft: 0 }}
                >
                  撤销授权
                </Button>
              </div>
            </>
          )}
        </Form>
      </Modal>

      {/* 模型配置弹窗 */}
      <Modal
        title={`模型配置 - ${editingModel?.id}`}
        open={modelConfigModalOpen}
        onCancel={() => setModelConfigModalOpen(false)}
        onOk={() => {
          setModelConfigModalOpen(false);
          message.success('模型配置已保存');
        }}
        width={500}
        destroyOnHidden
        okText="保存"
        cancelText="取消"
      >
        <Form form={modelConfigForm} layout="vertical">
          <Form.Item
            name="max_tokens"
            label="最大输出 Tokens"
            rules={[{ required: true, message: '请输入最大输出 Tokens' }]}
            extra="模型单次响应的最大 Token 数量"
          >
            <InputNumber min={1} max={128000} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item
            name="context_window"
            label="最大上下文长度"
            rules={[{ required: true, message: '请输入最大上下文长度' }]}
            extra="模型能处理的最大上下文 Token 数量"
          >
            <InputNumber min={1} max={262144} style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
