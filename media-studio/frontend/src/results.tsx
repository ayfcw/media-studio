import { useEffect, useRef, useState } from 'react'
import {
  Alert, Button, Card, Descriptions, Divider, Input, Progress, Space, Spin,
  Table, Tag, Typography, message,
} from 'antd'
import { CopyOutlined, DownloadOutlined, ReloadOutlined } from '@ant-design/icons'
import { api, MptTask, Task } from './api'

const { Text, Paragraph, Title } = Typography

// 演示模式警示：分析内容为内置示例，与提交的视频无关
function DemoBanner({ r }: { r: Record<string, any> }) {
  if (!r.demo_mode) return null
  return (
    <Alert type="warning" showIcon style={{ marginBottom: 16 }}
      message="演示模式：以下 AI 分析为内置示例数据，与提交的视频内容无关"
      description="采集层的视频数据是真实的（见下方「真实采集信息」）。到「系统设置」填入 LLM API Key 后，分析将自动变为基于真实视频内容的输出。"
    />
  )
}

// 原视频播放器：拆解时缓存的云端视频（直链会过期，缓存永久有效）
function SourceVideo({ s }: { s: Record<string, any> }) {
  if (!s.video_media_id) return null
  return (
    <Card size="small" title={<Tag color="green">原视频（无水印缓存）</Tag>} style={{ marginBottom: 16 }}>
      <video
        src={`/api/v1/media/${s.video_media_id}.mp4`}
        poster={s.cover_url || undefined}
        controls
        preload="metadata"
        style={{ width: '100%', maxHeight: 460, background: '#000', borderRadius: 6 }}
      />
      {s.duration_ms && (
        <Text type="secondary" style={{ fontSize: 12 }}>
          时长 {(s.duration_ms / 1000).toFixed(1)} 秒 · 视频已缓存到云端，随时可回看
        </Text>
      )}
    </Card>
  )
}

// 口播文案：AI 自动转写的逐字稿（拆解/复盘的核心依据）
function TranscriptPanel({ s }: { s: Record<string, any> }) {
  if (!s.transcript) return null
  return (
    <Card size="small" title={<Tag color="green">口播文案（AI 自动转写）</Tag>} style={{ marginBottom: 16 }}
      extra={
        <Button size="small" type="text" icon={<CopyOutlined />}
          onClick={() => { navigator.clipboard.writeText(s.transcript); message.success('已复制') }}>
          复制
        </Button>
      }>
      <Paragraph style={{ whiteSpace: 'pre-wrap', marginBottom: 0, maxHeight: 220, overflowY: 'auto' }}>
        {s.transcript}
      </Paragraph>
    </Card>
  )
}

// 真实采集信息卡片（DTK 返回的真实元数据）
function SourceCard({ s }: { s: Record<string, any> }) {
  const fmt = (v: unknown) => (typeof v === 'number' ? v.toLocaleString() : '-')
  return (
    <Card size="small" title={<Tag color="green">真实采集信息</Tag>} style={{ marginBottom: 16 }}>
      <Descriptions size="small" column={1} bordered>
        <Descriptions.Item label="标题">{s.title || '-'}</Descriptions.Item>
        <Descriptions.Item label="作者">
          {s.author ? `${s.author}${s.follower_count ? `（粉丝 ${fmt(s.follower_count)}）` : ''}` : '-'}
        </Descriptions.Item>
        <Descriptions.Item label="数据">
          {`👍 ${fmt(s.digg_count)}　⭐ ${fmt(s.collect_count)}　💬 ${fmt(s.comment_count)}　↗ ${fmt(s.share_count)}`}
        </Descriptions.Item>
        {s.tags?.length > 0 && (
          <Descriptions.Item label="标签"><Tags items={s.tags} color="blue" /></Descriptions.Item>
        )}
        {s.web_url && (
          <Descriptions.Item label="原文链接">
            <a href={s.web_url} target="_blank" rel="noreferrer">{s.web_url}</a>
          </Descriptions.Item>
        )}
      </Descriptions>
    </Card>
  )
}

function Tags({ items, color }: { items?: string[]; color?: string }) {
  if (!items?.length) return null
  return (
    <span>
      {items.map((t, i) => (
        <Tag key={i} color={color} style={{ marginRight: 4, marginBottom: 2 }}>{t}</Tag>
      ))}
    </span>
  )
}

// ---------- 1. 爆款拆解 ----------
function BreakdownView({ r }: { r: Record<string, any> }) {
  return (
    <>
      <DemoBanner r={r} />
      {r.source && <SourceVideo s={r.source} />}
      {r.source && <TranscriptPanel s={r.source} />}
      {r.source && <SourceCard s={r.source} />}
      {r.source && !r.source.video_media_id && (
        <Alert type="info" showIcon style={{ marginBottom: 16 }}
          message="此任务未缓存视频画面"
          description="该任务创建于视频缓存功能上线之前。新提交的拆解任务会自动缓存无水印原视频，可在报告中直接播放回看。" />
      )}
      <Title level={5} style={{ marginTop: 0 }}>AI 拆解报告</Title>
      <Descriptions size="small" column={1} bordered>
        <Descriptions.Item label="赛道">{r.topic}</Descriptions.Item>
        <Descriptions.Item label="钩子">{r.hook}</Descriptions.Item>
        <Descriptions.Item label="受众">{r.target_audience}</Descriptions.Item>
      </Descriptions>
      <Divider plain>结构拆解</Divider>
      <Table
        size="small" pagination={false} rowKey="name"
        dataSource={r.structure}
        columns={[
          { title: '段落', dataIndex: 'name', width: 90,
            render: (v: string) => <Tag color="blue">{v}</Tag> },
          { title: '内容', dataIndex: 'content' },
          { title: '为什么有效', dataIndex: 'purpose' },
        ]}
      />
      <Divider plain>要点</Divider>
      <p><Text type="secondary">爆点设计：</Text><Tags items={r.golden_points} color="gold" /></p>
      <p><Text type="secondary">可复用套路：</Text><Tags items={r.replicable_points} color="green" /></p>
      {r.risk_points?.length > 0 && (
        <p><Text type="secondary">风险提醒：</Text><Tags items={r.risk_points} color="red" /></p>
      )}
      <Alert type="info" showIcon message="改写建议" description={r.suggested_rewrite} />
    </>
  )
}

// ---------- 2. 博主对标 ----------
function BloggerView({ r }: { r: Record<string, any> }) {
  return (
    <>
      <Title level={5} style={{ marginTop: 0 }}>{r.blogger_name}</Title>
      <Descriptions size="small" column={1} bordered>
        <Descriptions.Item label="定位">{r.positioning}</Descriptions.Item>
        <Descriptions.Item label="受众">{r.audience}</Descriptions.Item>
        <Descriptions.Item label="风格">{r.style}</Descriptions.Item>
        <Descriptions.Item label="更新频率">{r.posting_frequency}</Descriptions.Item>
        {r.monetization && <Descriptions.Item label="变现">{r.monetization}</Descriptions.Item>}
      </Descriptions>
      <Divider plain>内容支柱</Divider>
      <Tags items={r.content_pillars} color="purple" />
      <Divider plain>对标作品</Divider>
      <Table size="small" pagination={false}
        rowKey="title" dataSource={r.benchmark_posts}
        columns={[
          { title: '标题', dataIndex: 'title' },
          { title: '点赞', dataIndex: 'likes', width: 90,
            render: (v: number) => v?.toLocaleString() },
          { title: '值得参考', dataIndex: 'highlight' },
        ]}
      />
      <Divider plain>优劣势与动作</Divider>
      <p><Text type="secondary">优势：</Text><Tags items={r.strengths} color="green" /></p>
      <p><Text type="secondary">短板：</Text><Tags items={r.weaknesses} color="red" /></p>
      <Alert type="success" showIcon message="我方可执行动作"
        description={<Tags items={r.actionable} color="blue" />} />
    </>
  )
}

// ---------- 3. 账号复盘 ----------
const SEVERITY: Record<string, { color: string; text: string }> = {
  high: { color: 'red', text: '高' }, medium: { color: 'orange', text: '中' },
  low: { color: 'blue', text: '低' },
}
function ReviewView({ r }: { r: Record<string, any> }) {
  return (
    <>
      {r.account_name && <Title level={5} style={{ marginTop: 0 }}>{r.account_name}</Title>}
      <Descriptions size="small" column={1} bordered>
        <Descriptions.Item label="定位">{r.positioning}</Descriptions.Item>
        <Descriptions.Item label="现状">{r.current_status}</Descriptions.Item>
        <Descriptions.Item label="数据概览">{r.data_summary}</Descriptions.Item>
      </Descriptions>
      <Divider plain>问题诊断</Divider>
      <Table size="small" pagination={false} rowKey="issue"
        dataSource={r.problems}
        columns={[
          { title: '问题', dataIndex: 'issue' },
          { title: '严重度', dataIndex: 'severity', width: 80,
            render: (v: string) => <Tag color={SEVERITY[v]?.color}>{SEVERITY[v]?.text ?? v}</Tag> },
          { title: '建议', dataIndex: 'suggestion' },
        ]}
      />
      <Divider plain>改进方向</Divider>
      <p><Text type="secondary">优势：</Text><Tags items={r.strengths} color="green" /></p>
      <p><Text type="secondary">建议：</Text><Tags items={r.suggestions} color="blue" /></p>
      <Alert type="warning" showIcon message="优先动作"
        description={<Tags items={r.priority_actions} color="orange" />} />
    </>
  )
}

// ---------- 4. 关键词找爆款 ----------
function KeywordsView({ r }: { r: Record<string, any> }) {
  return (
    <>
      <Descriptions size="small" column={1} bordered>
        <Descriptions.Item label="关键词">{r.keyword}</Descriptions.Item>
        <Descriptions.Item label="热度趋势">{r.trend}</Descriptions.Item>
      </Descriptions>
      <Divider plain>爆款清单</Divider>
      <Table size="small" pagination={false} rowKey="title"
        dataSource={r.hot_items}
        columns={[
          { title: '标题', dataIndex: 'title' },
          { title: '平台', dataIndex: 'platform', width: 90 },
          { title: '点赞', dataIndex: 'likes', width: 90,
            render: (v: number) => v?.toLocaleString() },
          { title: '为什么爆', dataIndex: 'reason' },
        ]}
      />
      <Divider plain>规律与角度</Divider>
      <p><Text type="secondary">爆款共性：</Text><Tags items={r.common_patterns} color="gold" /></p>
      <p><Text type="secondary">切入角度：</Text><Tags items={r.content_angles} color="cyan" /></p>
    </>
  )
}

// ---------- 5. 文案生成 ----------
export function ScriptCopy({ text, tip }: { text: string; tip?: string }) {
  return (
    <div>
      <Input.TextArea value={text} readOnly autoSize placeholder={tip} />
      <Button size="small" icon={<CopyOutlined />} style={{ marginTop: 4 }}
        onClick={() => { navigator.clipboard.writeText(text); message.success('已复制') }}>
        复制全文
      </Button>
    </div>
  )
}
function ScriptView({ r }: { r: Record<string, any> }) {
  return (
    <>
      <Title level={5} style={{ marginTop: 0 }}>候选标题</Title>
      <Tags items={r.title_options} color="geekblue" />
      <Divider plain>完整口播稿（可直接朗读）</Divider>
      <ScriptCopy text={r.full_script} />
      <Divider plain>分段</Divider>
      <Descriptions size="small" column={1} bordered>
        <Descriptions.Item label="钩子">{r.hook}</Descriptions.Item>
        <Descriptions.Item label="正文">{r.body}</Descriptions.Item>
        <Descriptions.Item label="CTA">{r.cta}</Descriptions.Item>
      </Descriptions>
      <Divider plain>发布配套</Divider>
      <p><Text type="secondary">话题标签：</Text><Tags items={r.hashtags} color="blue" /></p>
      <p><Text type="secondary">素材搜索词：</Text><Tags items={r.search_terms} color="cyan" /></p>
    </>
  )
}

// ---------- 6. 仿写三件套 ----------
const REWRITE_MODE: Record<string, string> = {
  structure: '结构仿写', topic: '选题提炼', dedup: '同主题去重',
}
function RewriteView({ r }: { r: Record<string, any> }) {
  return (
    <>
      <Descriptions size="small" column={1} bordered>
        <Descriptions.Item label="仿写模式">
          <Tag color="magenta">{REWRITE_MODE[r.mode] ?? r.mode}</Tag>
        </Descriptions.Item>
        <Descriptions.Item label="原文案概括">{r.source_summary}</Descriptions.Item>
        <Descriptions.Item label="提炼选题">{r.extracted_topic}</Descriptions.Item>
      </Descriptions>
      {r.structure_used?.length > 0 && (
        <>
          <Divider plain>复用结构</Divider>
          <Table size="small" pagination={false} rowKey="name"
            dataSource={r.structure_used}
            columns={[
              { title: '段落', dataIndex: 'name', width: 90,
                render: (v: string) => <Tag color="blue">{v}</Tag> },
              { title: '内容', dataIndex: 'content' },
              { title: '作用', dataIndex: 'purpose' },
            ]} />
        </>
      )}
      <Divider plain>新文案</Divider>
      <ScriptView r={r} />
      {r.dedup_notes?.length > 0 && (
        <Alert type="success" showIcon style={{ marginTop: 12 }} message="去重/差异化处理"
          description={<Tags items={r.dedup_notes} color="green" />} />
      )}
    </>
  )
}

// ---------- 成片进度 ----------
const MPT_STATE: Record<number, { text: string; color: string }> = {
  [-1]: { text: '失败', color: 'red' }, 4: { text: '合成中', color: 'blue' },
  1: { text: '完成', color: 'green' },
}
export function MptVideoPanel({ mptTaskId }: { mptTaskId: string }) {
  const [t, setT] = useState<MptTask | null>(null)
  const [err, setErr] = useState('')
  const timer = useRef<ReturnType<typeof setInterval> | undefined>(undefined)

  const load = async () => {
    try { setT(await api.getMptTask(mptTaskId)) } catch (e) { setErr(String(e)) }
  }
  useEffect(() => {
    load()
    timer.current = setInterval(load, 4000)
    return () => { if (timer.current) clearInterval(timer.current) }
  }, [mptTaskId])

  if (err) return <Alert type="error" message={`查询成片状态失败：${err}`} />
  if (!t) return <Spin />
  const st = MPT_STATE[t.state ?? 0] ?? { text: `state=${t.state}`, color: 'default' }
  const done = t.state === 1
  const failed = t.state === -1

  return (
    <Card size="small" title={<Space>成片任务 <Tag color={st.color}>{st.text}</Tag>
      <Text type="secondary" style={{ fontSize: 12 }}>{mptTaskId}</Text></Space>}
      extra={<Button size="small" icon={<ReloadOutlined />} onClick={load}>刷新</Button>}>
      {!done && !failed && <Progress percent={t.progress ?? 0} status="active" />}
      {failed && (
        <Alert type="error" showIcon
          message={`成片失败（阶段：${t.failed_stage ?? '未知'}）`}
          description={t.error || '常见原因：素材源 API Key 未配置（Pexels 等）、TTS 音色无效。'}
        />
      )}
      {done && (
        <>
          {t.videos?.map((v) => (
            <div key={v} style={{ marginBottom: 12 }}>
              <video src={v} controls style={{ maxWidth: '100%', maxHeight: 420 }} />
              <div>
                <Button size="small" type="primary" icon={<DownloadOutlined />}
                  href={v} target="_blank">下载视频</Button>
              </div>
            </div>
          ))}
          {!t.videos?.length && <Alert type="warning" message="任务完成但未返回视频文件" />}
        </>
      )}
    </Card>
  )
}

function VideoView({ r, task }: { r: Record<string, any>; task?: Task }) {
  return (
    <>
      {r.status === 'submitted' && r.mpt_task_id && (
        <Alert type="success" showIcon style={{ marginBottom: 12 }}
          message="已提交到成片引擎（MoneyPrinterTurbo）" />
      )}
      {r.status === 'deferred' && (
        <Alert type="warning" showIcon style={{ marginBottom: 12 }}
          message="成片暂缓（引擎不可用或缺少素材 Key）" description={r.reason} />
      )}
      {r.mpt_task_id && <MptVideoPanel mptTaskId={r.mpt_task_id} />}
      <Divider plain>本条文案</Divider>
      <ScriptCopy text={r.script ?? ''} />
      <p style={{ marginTop: 8 }}><Text type="secondary">素材搜索词：</Text>
        <Tags items={r.terms} color="cyan" /></p>
      {task && (
        <p style={{ marginTop: 8 }}>
          <Text type="secondary">输入参数：</Text>
          <Text code>{JSON.stringify(task.input)}</Text>
        </p>
      )}
    </>
  )
}

// ---------- 分发 ----------
export function ResultView({ task }: { task: Task }) {
  const r = task.result ?? {}
  const view = (() => {
    switch (r.kind ?? task.kind) {
    case 'breakdown': return <BreakdownView r={r} />
    case 'blogger': return <BloggerView r={r} />
    case 'review': return <ReviewView r={r} />
    case 'keywords': return <KeywordsView r={r} />
    case 'script': return <ScriptView r={r} />
    case 'rewrite': return <RewriteView r={r} />
    case 'analyze-link': return <BreakdownView r={r} />
    case 'analyze-blogger': return <BloggerView r={r} />
    case 'account-review': return <ReviewView r={r} />
    case 'search-keywords': return <KeywordsView r={r} />
    case 'generate-script': return <ScriptView r={r} />
    case 'generate-video': return <VideoView r={r} task={task} />
    default:
      return <Paragraph code copyable style={{ whiteSpace: 'pre-wrap' }}>
        {JSON.stringify(r, null, 2)}
      </Paragraph>
    }
  })()
  return (
    <>
      {!(r.kind === 'breakdown' || task.kind === 'analyze-link') && <DemoBanner r={r} />}
      {view}
    </>
  )
}
