/**
 * Memory Management - 分层记忆配置区块
 *
 * 嵌入 Agent 设置页，提供 4 个 Agent 的记忆配置管理：
 * - 摘要滑动窗口（10 档固定）
 * - 对话压缩（阈值、保留消息数、摘要上限）
 * - 持久化参数
 * - [重置为默认] [保存] 按钮
 */
import { useEffect, useState } from 'react';
import {
  Tabs, Card, Slider, InputNumber, Button, Space, Tag,
  Typography, Row, Col, Spin, Empty, Popconfirm, message, Alert, Switch, Statistic,
} from 'antd';
import {
  ReloadOutlined, SaveOutlined, DatabaseOutlined,
  MessageOutlined, CloudSyncOutlined,
} from '@ant-design/icons';
import { memoryConfigApi } from '../../services/api';

const { Title, Text, Paragraph } = Typography;

// 固定的 10 档滑窗档位
const WINDOW_PRESETS = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000];

// 4 个 Agent（与后端 agents.yaml 对齐）
const AGENT_TABS = [
  { key: 'main', label: '主编 (Main)' },
  { key: 'plot_writer', label: '剧情撰写' },
  { key: 'proofreader', label: '资深校对' },
  { key: 'character_designer', label: '人物设计' },
];

interface AgentConfig {
  chapter_window?: number;
  max_summary_blocks?: number;
  summary_max_chars?: number;
  dialogue_compression_threshold?: number;
  preserve_recent_messages?: number;
  dialogue_summary_max_chars?: number;
  dialogue_context_summary_max_chars?: number;
  dialogue_compression_max_retries?: number;
  subagent_compression_enabled?: boolean;
  subagent_max_messages?: number;
  auto_compaction_threshold?: number;
  [key: string]: unknown;
}


interface AgentConfigResponse {
  agent_id: string;
  config: AgentConfig;
  global_config: AgentConfig;
  has_override: boolean;
}

interface MemoryManagementProps {
  /** 注入的 agentId（受控模式）。不传时使用内部 Tabs 切换。 */
  agentId?: string;
}

export default function MemoryManagement({ agentId: externalAgentId }: MemoryManagementProps = {}) {
  const [activeTab, setActiveTab] = useState(externalAgentId || AGENT_TABS[0].key);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [data, setData] = useState<AgentConfigResponse | null>(null);
  const [draft, setDraft] = useState<AgentConfig | null>(null);

  // 受控 agentId 时禁用 Tabs
  const tabsItems = externalAgentId ? [] : AGENT_TABS.map((t) => ({ key: t.key, label: t.label }));

  const loadConfig = async (agentKey: string) => {
    setLoading(true);
    try {
      const res = await memoryConfigApi.get(agentKey);
      setData(res.data);
      setDraft({ ...res.data.config });
    } catch (e: unknown) {
      const err = e as { message?: string };
      message.error(`加载配置失败: ${err?.message || '未知错误'}`);
      setData(null);
      setDraft(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadConfig(activeTab);
  }, [activeTab]);

  const handleChange = (field: keyof AgentConfig, value: number | boolean) => {
    if (!draft) return;
    setDraft({ ...draft, [field]: value });
  };

  const handleReset = async () => {
    if (!data) return;
    try {
      await memoryConfigApi.reset(data.agent_id);
      message.success('已重置为全局默认');
      await loadConfig(data.agent_id);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      const detail = err?.response?.data?.detail || err?.message || '未知错误';
      message.error(`重置失败: ${detail}`);
    }
  };

  const handleSave = async () => {
    if (!data || !draft) return;
    setSaving(true);
    try {
      // 只提交修改的字段
      const changed: Record<string, unknown> = {};
      for (const [key, val] of Object.entries(draft)) {
        if (val !== data.config[key]) {
          changed[key] = val;
        }
      }
      if (Object.keys(changed).length === 0) {
        message.info('未修改');
        return;
      }
      await memoryConfigApi.update(data.agent_id, changed);
      message.success('配置已保存');
      await loadConfig(data.agent_id);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      const detail = err?.response?.data?.detail || err?.message || '未知错误';
      message.error(`保存失败: ${detail}`);
    } finally {
      setSaving(false);
    }
  };

  const isInherited = (field: keyof AgentConfig) => {
    if (!data) return false;
    return data.config[field] === data.global_config[field];
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 60 }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!data || !draft) {
    return <Empty description="暂无配置数据" />;
  }

  const chapterWindow = (draft.chapter_window ?? 100) as number;
  const summaryBlocks = (draft.max_summary_blocks ?? 3) as number;
  const dialogueThreshold = (draft.dialogue_compression_threshold ?? 0.8) as number;
  const preserveMessages = (draft.preserve_recent_messages ?? 4) as number;
  const summaryMaxChars = (draft.dialogue_summary_max_chars ?? 4000) as number;
  const contextMaxChars = (draft.dialogue_context_summary_max_chars ?? 1500) as number;
  const maxRetries = (draft.dialogue_compression_max_retries ?? 2) as number;
  const subagentEnabled = (draft.subagent_compression_enabled ?? true) as boolean;
  const subagentMaxMessages = (draft.subagent_max_messages ?? 30) as number;
  const autoCompactionThreshold = (draft.auto_compaction_threshold ?? 100000) as number;

  const cardSection = (icon: React.ReactNode, title: string, children: React.ReactNode) => (
    <Card
      size="small"
      title={
        <Space>
          {icon}
          <Text strong>{title}</Text>
        </Space>
      }
      style={{ marginBottom: 16 }}
    >
      {children}
    </Card>
  );

  return (
    <div>
      <Space style={{ marginBottom: 16 }} align="center">
        <Title level={5} style={{ margin: 0 }}>
          <DatabaseOutlined /> 记忆管理
        </Title>
        {data.has_override
          ? <Tag color="blue">已自定义</Tag>
          : <Tag>继承全局</Tag>}
      </Space>
      <Paragraph type="secondary" style={{ marginBottom: 16 }}>
        分层记忆配置：4 层清晰分层（活跃对话 / 滚动摘要 / 剧情追踪 / 人物关系）。
        修改后点击「保存」立即生效。
      </Paragraph>

      {!externalAgentId && (
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={tabsItems}
          style={{ marginBottom: 16 }}
        />
      )}

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="当前滑窗"
              value={chapterWindow}
              suffix="章"
              prefix={<DatabaseOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="保留摘要块"
              value={summaryBlocks}
              suffix={`× ${chapterWindow} 章`}
              prefix={<CloudSyncOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="压缩阈值"
              value={(dialogueThreshold * 100).toFixed(0)}
              suffix="%"
              prefix={<MessageOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="自动压缩触发"
              value={autoCompactionThreshold >= 1000
                ? `${(autoCompactionThreshold / 1000).toFixed(0)}K`
                : autoCompactionThreshold}
              suffix=" tokens"
            />
          </Card>
        </Col>
      </Row>

      {/* 摘要滑动窗口 */}
      {cardSection(
        <DatabaseOutlined />,
        '摘要滑动窗口',
        <div>
          <Row align="middle" gutter={16}>
            <Col span={16}>
              <Slider
                min={1} max={10} step={1}
                value={WINDOW_PRESETS.indexOf(chapterWindow) >= 0
                  ? WINDOW_PRESETS.indexOf(chapterWindow) + 1
                  : Math.max(0, Math.min(9, Math.round(chapterWindow / 100)))}
                marks={WINDOW_PRESETS.reduce((acc, v, i) => {
                  acc[i + 1] = `${v}`;
                  return acc;
                }, {} as Record<number, string>)}
                onChange={(idx) => handleChange('chapter_window', WINDOW_PRESETS[idx - 1] || 100)}
                tooltip={{ formatter: (v) => `${WINDOW_PRESETS[(v || 1) - 1]} 章` }}
              />
            </Col>
            <Col span={6}>
              <InputNumber
                min={50} max={2000} step={50}
                value={chapterWindow}
                onChange={(v) => handleChange('chapter_window', v || 100)}
                addonAfter="章"
                style={{ width: '100%' }}
              />
            </Col>
          </Row>
          <Paragraph type="secondary" style={{ marginTop: 8, marginBottom: 0, fontSize: 12 }}>
            每 100~1000 章触发一次摘要压缩；超过保留块数时滑窗淘汰最旧的块。
            滑窗档位（10 档固定）：{WINDOW_PRESETS.join(', ')}
          </Paragraph>
        </div>
      )}

      {/* 摘要块参数 */}
      {cardSection(
        <CloudSyncOutlined />,
        '摘要块参数',
        <Row gutter={16}>
          <Col span={12}>
            <Text>保留摘要块数</Text>
            <InputNumber
              min={1} max={10} step={1}
              value={summaryBlocks}
              onChange={(v) => handleChange('max_summary_blocks', v || 3)}
              style={{ width: '100%' }}
            />
            <Text type="secondary" style={{ fontSize: 12 }}>
              {isInherited('max_summary_blocks') ? '继承自全局' : '已覆盖'}
            </Text>
          </Col>
          <Col span={12}>
            <Text>单块最大字符</Text>
            <InputNumber
              min={500} max={10000} step={100}
              value={(draft.summary_max_chars ?? 2000) as number}
              onChange={(v) => handleChange('summary_max_chars', v || 2000)}
              style={{ width: '100%' }}
              addonAfter="字符"
            />
            <Text type="secondary" style={{ fontSize: 12 }}>
              {isInherited('summary_max_chars') ? '继承自全局' : '已覆盖'}
            </Text>
          </Col>
        </Row>
      )}

      {/* 对话压缩 */}
      {cardSection(
        <MessageOutlined />,
        '对话压缩',
        <Row gutter={[16, 16]}>
          <Col span={12}>
            <Text>触发阈值（占上下文上限比例）</Text>
            <Slider
              min={0.5} max={0.95} step={0.05}
              value={dialogueThreshold}
              onChange={(v) => handleChange('dialogue_compression_threshold', v)}
              tooltip={{ formatter: (v) => `${((v || 0) * 100).toFixed(0)}%` }}
            />
            <Text type="secondary" style={{ fontSize: 12 }}>
              当前：{(dialogueThreshold * 100).toFixed(0)}%
              {isInherited('dialogue_compression_threshold') ? '（继承自全局）' : '（已覆盖）'}
            </Text>
          </Col>
          <Col span={12}>
            <Text>保留最近消息数</Text>
            <InputNumber
              min={2} max={20} step={1}
              value={preserveMessages}
              onChange={(v) => handleChange('preserve_recent_messages', v || 4)}
              style={{ width: '100%' }}
            />
            <Text type="secondary" style={{ fontSize: 12 }}>
              {isInherited('preserve_recent_messages') ? '继承自全局' : '已覆盖'}
            </Text>
          </Col>
          <Col span={12}>
            <Text>摘要上限（字符）</Text>
            <InputNumber
              min={1000} max={10000} step={100}
              value={summaryMaxChars}
              onChange={(v) => handleChange('dialogue_summary_max_chars', v || 4000)}
              style={{ width: '100%' }}
            />
          </Col>
          <Col span={12}>
            <Text>上下文摘要上限（字符）</Text>
            <InputNumber
              min={200} max={summaryMaxChars} step={100}
              value={contextMaxChars}
              onChange={(v) => handleChange('dialogue_context_summary_max_chars', v || 1500)}
              style={{ width: '100%' }}
            />
            <Text type="secondary" style={{ fontSize: 12 }}>
              不能超过摘要上限
            </Text>
          </Col>
          <Col span={12}>
            <Text>LLM 失败重试次数</Text>
            <InputNumber
              min={0} max={5} step={1}
              value={maxRetries}
              onChange={(v) => handleChange('dialogue_compression_max_retries', v ?? 2)}
              style={{ width: '100%' }}
            />
          </Col>
          <Col span={12}>
            <Text>子 agent 压缩</Text>
            <div>
              <Switch
                checked={subagentEnabled}
                onChange={(v) => handleChange('subagent_compression_enabled', v)}
                checkedChildren="启用"
                unCheckedChildren="禁用"
              />
              <span style={{ marginLeft: 12 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  子 agent 消息上限：
                </Text>
                <InputNumber
                  min={5} max={100} step={5}
                  value={subagentMaxMessages}
                  onChange={(v) => handleChange('subagent_max_messages', v || 30)}
                  style={{ width: 90, marginLeft: 4 }}
                  size="small"
                />
              </span>
            </div>
          </Col>
        </Row>
      )}

      {/* 高级：自动压缩触发阈值 */}
      {cardSection(
        <DatabaseOutlined />,
        '自动压缩触发',
        <div>
          <Text>累计 token 达到该值时自动压缩</Text>
          <InputNumber
            min={10000} max={500000} step={10000}
            value={autoCompactionThreshold}
            onChange={(v) => handleChange('auto_compaction_threshold', v || 100000)}
            style={{ width: '100%' }}
            formatter={(v) => `${v} tokens`}
            parser={(v) => parseInt((v || '').replace(/[^\d]/g, '')) || 100000}
          />
          <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 4 }}>
            范围：10K ~ 500K tokens。超过此值会触发 LLM 压缩（可能耗时 2-5s）。
          </Text>
        </div>
      )}

      <Alert
        message="配置分层优先级"
        description="agents.{name}.xxx > global.xxx > MemoryConfig 字段默认值。未显式配置的字段会继承全局。"
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
      />

      <Space>
        <Button
          type="default"
          icon={<ReloadOutlined />}
          onClick={handleReset}
        >
          重置为默认
        </Button>
        <Button
          type="primary"
          icon={<SaveOutlined />}
          loading={saving}
          onClick={handleSave}
        >
          保存
        </Button>
        <Popconfirm
          title="放弃当前修改？"
          onConfirm={() => loadConfig(data.agent_id)}
          okText="放弃"
          cancelText="取消"
        >
          <Button>放弃修改</Button>
        </Popconfirm>
      </Space>
    </div>
  );
}
