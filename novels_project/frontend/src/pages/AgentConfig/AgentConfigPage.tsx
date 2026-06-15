import { useEffect, useState } from 'react';
import {
  Card, Row, Col, Switch, Slider, Input, Button,
  Typography, Space, Tag, message, Spin, Collapse, Descriptions, Select,
} from 'antd';
import {
  RobotOutlined, CheckCircleOutlined,
} from '@ant-design/icons';
import { agentApi } from '../../services/api';
import MemoryManagement from '../../components/AgentConfig/MemoryManagement';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;
const { Panel } = Collapse;

interface ModelInfo {
  id: string;
  name: string;
}

interface ProviderInfo {
  id: string;
  name: string;
  models: ModelInfo[];
}

export default function AgentConfigPage() {
  const [agents, setAgents] = useState<Record<string, any>>({});
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [agentProviders, setAgentProviders] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<Record<string, boolean>>({});

  useEffect(() => {
    Promise.all([agentApi.list(), agentApi.getModels()])
      .then(([agentsRes, modelsRes]) => {
        const agentsData = agentsRes.data;
        // API 返回 { providers: { id: { name, models, ... } } }
        // 转换为 ProviderInfo[] 数组
        const providersObj = modelsRes.data?.providers || {};
        const providersData: ProviderInfo[] = Object.entries(providersObj).map(
          ([id, data]: [string, any]) => ({
            id,
            name: data.name || id,
            models: data.models || [],
          }),
        );
        setAgents(agentsData);
        setProviders(providersData);

        // Determine which provider each agent's model belongs to
        const apMap: Record<string, string> = {};
        for (const [key, agent] of Object.entries(agentsData) as [string, any][]) {
          const modelId = agent.model;
          if (modelId) {
            const found = providersData.find((p) =>
              p.models.some((m) => m.id === modelId),
            );
            if (found) {
              apMap[key] = found.id;
            }
          }
        }
        setAgentProviders(apMap);
      })
      .catch(() => message.error('获取 Agent 配置失败'))
      .finally(() => setLoading(false));
  }, []);

  const getModelsForAgent = (agentKey: string): ModelInfo[] => {
    const providerId = agentProviders[agentKey];
    if (!providerId) return [];
    const provider = providers.find((p) => p.id === providerId);
    return provider ? provider.models : [];
  };

  const handleProviderChange = (agentKey: string, providerId: string) => {
    const provider = providers.find((p) => p.id === providerId);
    if (!provider) return;
    const firstModel = provider.models[0];
    setAgentProviders((prev) => ({ ...prev, [agentKey]: providerId }));
    setAgents((prev) => ({
      ...prev,
      [agentKey]: {
        ...prev[agentKey],
        model: firstModel ? firstModel.id : '',
      },
    }));
  };

  const handleModelChange = (agentKey: string, modelId: string) => {
    setAgents((prev) => ({
      ...prev,
      [agentKey]: { ...prev[agentKey], model: modelId },
    }));
  };

  const handleToggle = async (name: string, enabled: boolean) => {
    try {
      await agentApi.toggle(name, enabled);
      setAgents(prev => ({
        ...prev,
        [name]: { ...prev[name], enabled },
      }));
      message.success(`${name} ${enabled ? '已启用' : '已禁用'}`);
    } catch {
      message.error('操作失败');
    }
  };

  const handleSave = async (name: string, config: any) => {
    setSaving(prev => ({ ...prev, [name]: true }));
    try {
      await agentApi.update(name, config);
      message.success(`${name} 配置已保存`);
    } catch {
      message.error('保存失败');
    } finally {
      setSaving(prev => ({ ...prev, [name]: false }));
    }
  };

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;

  return (
    <div>
      <Title level={4}>Agent 配置</Title>
      <Paragraph type="secondary">
        配置各 Agent 的模型参数、行为模式和交互规则。修改后立即生效。
      </Paragraph>

      {/* 分层记忆配置区块 */}
      <Card style={{ marginBottom: 24 }}>
        <MemoryManagement />
      </Card>

      <Row gutter={[16, 16]}>
        {Object.entries(agents).map(([key, agent]) => (
          <Col xs={24} lg={12} key={key}>
            <Card
              title={
                <Space>
                  <RobotOutlined />
                  <span>{agent.name || key}</span>
                  <Tag color={agent.enabled ? 'green' : 'default'}>
                    {agent.enabled ? '运行中' : '已禁用'}
                  </Tag>
                </Space>
              }
              extra={
                <Switch
                  checked={agent.enabled}
                  onChange={(v) => handleToggle(key, v)}
                />
              }
              actions={[
                <Button
                  key={key}
                  type="primary"
                  icon={<CheckCircleOutlined />}
                  loading={saving[key]}
                  onClick={() => handleSave(key, {
                    model: agent.model,
                    temperature: agent.temperature,
                    max_tokens: agent.max_tokens,
                    system_prompt: agent.system_prompt,
                    rules: agent.rules,
                  })}
                >
                  保存配置
                </Button>,
              ]}
            >
              <Descriptions column={2} size="small" bordered>
                <Descriptions.Item label="角色" span={2}>{agent.role}</Descriptions.Item>
                <Descriptions.Item label="描述" span={2}>{agent.description}</Descriptions.Item>
                <Descriptions.Item label="模型供应商">
                  <Select
                    size="small"
                    style={{ width: '100%' }}
                    placeholder="选择供应商"
                    value={agentProviders[key] || undefined}
                    onChange={(v) => handleProviderChange(key, v)}
                    options={providers.map((p) => ({
                      label: p.name,
                      value: p.id,
                    }))}
                  />
                </Descriptions.Item>
                <Descriptions.Item label="模型">
                  <Select
                    size="small"
                    style={{ width: '100%' }}
                    placeholder="选择模型"
                    value={agent.model || undefined}
                    onChange={(v) => handleModelChange(key, v)}
                    options={getModelsForAgent(key).map((m) => ({
                      label: `${m.name} (${m.id})`,
                      value: m.id,
                    }))}
                  />
                </Descriptions.Item>
                <Descriptions.Item label="温度">
                  <Slider
                    min={0} max={2} step={0.1}
                    value={agent.temperature}
                    onChange={v => setAgents(prev => ({
                      ...prev,
                      [key]: { ...prev[key], temperature: v },
                    }))}
                  />
                  <Text type="secondary" style={{ fontSize: 12 }}>{agent.temperature}</Text>
                </Descriptions.Item>
                <Descriptions.Item label="Max Tokens">
                  <Input
                    size="small"
                    type="number"
                    value={agent.max_tokens}
                    onChange={e => setAgents(prev => ({
                      ...prev,
                      [key]: { ...prev[key], max_tokens: parseInt(e.target.value) || 0 },
                    }))}
                  />
                </Descriptions.Item>
              </Descriptions>

              <Collapse ghost style={{ marginTop: 8 }}>
                <Panel header="系统提示词 (System Prompt)" key="prompt">
                  <TextArea
                    rows={4}
                    value={agent.system_prompt || ''}
                    onChange={e => setAgents(prev => ({
                      ...prev,
                      [key]: { ...prev[key], system_prompt: e.target.value },
                    }))}
                    placeholder="自定义系统提示词..."
                  />
                </Panel>
              </Collapse>
            </Card>
          </Col>
        ))}
      </Row>
    </div>
  );
}