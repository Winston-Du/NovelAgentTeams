import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Typography, Button, Space, Spin, Descriptions, Tag, Divider, Collapse, Input,
} from 'antd';
import { message } from 'antd'; // will be replaced by useMessage hook in component
import { ArrowLeftOutlined, EditOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import rehypeHighlight from 'rehype-highlight';
import { contentApi } from '../../services/api';

const { Title } = Typography;
const { TextArea } = Input;

export default function ChapterDetailPage() {
  const [msgApi, contextHolder] = message.useMessage();
  const { chapterId } = useParams<{ chapterId: string }>();
  const navigate = useNavigate();
  const [chapter, setChapter] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  // Annotation state
  const [note, setNote] = useState('');
  const [modification, setModification] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!chapterId) return;
    setLoading(true);
    contentApi.getChapter(chapterId)
      .then(res => setChapter(res.data))
      .catch(() => msgApi.error('获取章节失败'))
      .finally(() => setLoading(false));
  }, [chapterId]);

  const handleSubmitAnnotation = async () => {
    const noteText = note.trim();
    const modText = modification.trim();
    if (!noteText && !modText) {
      message.warning('请填写批注或修改指令');
      return;
    }
    setSubmitting(true);
    try {
      const payload: any = { content_type: 'chapter', content_id: chapterId };
      if (noteText) payload.note = noteText;
      if (modText) payload.note = `${payload.note || ''}\n\n修改指令:\n${modText}`;
      await contentApi.annotate(payload);
      message.success('批注提交成功');
      setNote('');
      setModification('');
    } catch {
      message.error('批注提交失败');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  if (!chapter) return <div>章节不存在</div>;

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate('/content/chapters')}
        >
          返回列表
        </Button>
        <Title level={4} style={{ margin: 0 }}>
          {chapter.title || `第 ${chapter.chapter_id} 章`}
        </Title>
        <Tag color="purple">第 {chapter.chapter_id} 章</Tag>
      </Space>

      {chapter.summary && (
        <>
          <Divider orientationMargin={0} style={{ borderColor: '#722ed1' }}>章节摘要</Divider>
          <Descriptions bordered size="small" column={2}>
            {chapter.summary.summary && (
              <Descriptions.Item label="摘要" span={2}>{chapter.summary.summary}</Descriptions.Item>
            )}
            {chapter.summary.key_events && (
              <Descriptions.Item label="关键事件" span={2}>
                {chapter.summary.key_events.map((e: string, i: number) => (
                  <Tag key={i} style={{ marginBottom: 4 }}>{e}</Tag>
                ))}
              </Descriptions.Item>
            )}
            {chapter.summary.characters_appeared && (
              <Descriptions.Item label="出场人物" span={2}>
                {chapter.summary.characters_appeared.map((c: string, i: number) => (
                  <Tag key={i} color="blue">{c}</Tag>
                ))}
              </Descriptions.Item>
            )}
          </Descriptions>
        </>
      )}

      <Divider orientationMargin={0} style={{ borderColor: '#722ed1' }}>正文内容</Divider>
      <div className="markdown-body">
        <ReactMarkdown rehypePlugins={[rehypeHighlight]}>
          {chapter.content}
        </ReactMarkdown>
      </div>

      {/* 批注/反馈面板 */}
      <Divider style={{ marginTop: 32 }} />
      <Collapse
        size="small"
        items={[{
          key: 'annotation',
          label: (
            <Space>
              <EditOutlined />
              <span>批注与反馈</span>
            </Space>
          ),
          children: (
            <div>
              <div style={{ marginBottom: 12 }}>
                <div style={{ marginBottom: 4, fontWeight: 500 }}>批注/笔记</div>
                <TextArea
                  rows={3}
                  placeholder="在此记录您对本章内容的批注、笔记或修改建议..."
                  value={note}
                  onChange={e => setNote(e.target.value)}
                />
              </div>
              <div style={{ marginBottom: 12 }}>
                <div style={{ marginBottom: 4, fontWeight: 500 }}>修改指令（可选）</div>
                <TextArea
                  rows={2}
                  placeholder="输入具体的修改指令，例如：'让主角的对话更激烈一些'..."
                  value={modification}
                  onChange={e => setModification(e.target.value)}
                />
              </div>
              <Button
                type="primary"
                loading={submitting}
                onClick={handleSubmitAnnotation}
              >
                提交批注
              </Button>
            </div>
          ),
        }]}
        style={{ background: '#fafafa' }}
      />
    </div>
  );
}