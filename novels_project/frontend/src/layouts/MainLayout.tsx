import { useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import {
  Layout, Menu, Button, Typography, Space,
  theme as antTheme,
} from 'antd';
import {
  FileTextOutlined, RobotOutlined,
  SettingOutlined, DatabaseOutlined, MenuFoldOutlined,
  MenuUnfoldOutlined, PlusOutlined,
} from '@ant-design/icons';
import { useWorkspaceStore } from '../stores/workspaceStore';

const { Header, Sider, Content } = Layout;

const menuItems = [
  {
    key: 'content',
    icon: <FileTextOutlined />,
    label: '内容管理',
    children: [
      { key: '/content/characters', label: '人物卡管理' },
      { key: '/content/chapters', label: '章节管理' },
      { key: '/content/plotlines', label: '暗线管理' },
    ],
  },
  { key: '/agents', icon: <RobotOutlined />, label: 'Agent 配置' },
  { key: '/memory', icon: <DatabaseOutlined />, label: '记忆管理' },
  {
    key: 'settings-group',
    icon: <SettingOutlined />,
    label: '基础设置',
    children: [
      { key: '/settings/workspace', label: '工作空间管理' },
      { key: '/settings', label: '基础设置' },
    ],
  },
];

export default function MainLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { token } = antTheme.useToken();
  const { currentWorkspace } = useWorkspaceStore();

  const selectedKey = (() => {
    const path = location.pathname;
    if (path.startsWith('/content')) {
      for (const item of menuItems) {
        if (item.key === 'content' && item.children) {
          const child = item.children.find(c => path.startsWith(c.key));
          if (child) return child.key;
        }
      }
    }
    if (path.startsWith('/settings')) {
      for (const item of menuItems) {
        if (item.key === 'settings-group' && item.children) {
          const child = item.children.find(c => path === c.key);
          if (child) return child.key;
        }
      }
      return '/settings';
    }
    return path || '/content/chapters';
  })();

  const openKeys = (() => {
    if (location.pathname.startsWith('/content')) return ['content'];
    if (location.pathname.startsWith('/settings')) return ['settings-group'];
    return [];
  })();

  return (
    <Layout style={{ height: '100vh' }}>
      <Sider
        trigger={null}
        collapsible
        collapsed={collapsed}
        theme="light"
        width={220}
        style={{
          borderRight: `1px solid ${token.colorBorderSecondary}`,
          overflow: 'auto',
        }}
      >
        <div style={{
          height: 64,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderBottom: `1px solid ${token.colorBorderSecondary}`,
        }}>
          <Typography.Title level={4} style={{ margin: 0, color: token.colorPrimary }}>
            {collapsed ? 'NA' : 'NovelAgents'}
          </Typography.Title>
        </div>

        <Menu
          mode="inline"
          selectedKeys={[selectedKey]}
          defaultOpenKeys={openKeys}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{ borderRight: 0, marginTop: 8 }}
        />
      </Sider>

      <Layout>
        <Header style={{
          padding: '0 24px',
          background: token.colorBgContainer,
          borderBottom: `1px solid ${token.colorBorderSecondary}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
          <Space>
            <Button
              type="text"
              icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={() => setCollapsed(!collapsed)}
            />
            <Typography.Text type="secondary">
              {currentWorkspace ? `当前工作空间: ${currentWorkspace.name}` : '未选择工作空间'}
            </Typography.Text>
          </Space>

          <Space>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => navigate('/settings/workspace')}
            >
              新建工作空间
            </Button>
          </Space>
        </Header>

        <Content style={{
          margin: 24,
          padding: 24,
          background: token.colorBgContainer,
          borderRadius: token.borderRadiusLG,
          overflow: 'auto',
          minHeight: 280,
        }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}