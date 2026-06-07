import { useRoutes, Navigate } from 'react-router-dom';
import { App as AntdApp } from 'antd';
import MainLayout from './layouts/MainLayout';
import WorkspacePage from './pages/Workspace/WorkspacePage';
import CharactersPage from './pages/Content/CharactersPage';
import ChaptersPage from './pages/Content/ChaptersPage';
import ChapterDetailPage from './pages/Content/ChapterDetailPage';
import PlotLinesPage from './pages/Content/PlotLinesPage';
import AgentConfigPage from './pages/AgentConfig/AgentConfigPage';
import SettingsPage from './pages/Settings/SettingsPage';
import MemoryPage from './pages/Memory/MemoryPage';

export default function App() {
  const routes = useRoutes([
    {
      path: '/',
      element: <MainLayout />,
      children: [
        { index: true, element: <Navigate to="/content/chapters" replace /> },
        { path: 'settings/workspace', element: <WorkspacePage /> },
        { path: 'content/characters', element: <CharactersPage /> },
        { path: 'content/chapters', element: <ChaptersPage /> },
        { path: 'content/chapters/:chapterId', element: <ChapterDetailPage /> },
        { path: 'content/plotlines', element: <PlotLinesPage /> },
        { path: 'agents', element: <AgentConfigPage /> },
        { path: 'settings', element: <SettingsPage /> },
        { path: 'memory', element: <MemoryPage /> },
      ],
    },
  ]);

  return <AntdApp>{routes}</AntdApp>;
}