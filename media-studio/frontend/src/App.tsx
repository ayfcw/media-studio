import { useEffect, useMemo, useState } from 'react'
import {
  Alert, Badge, Button, Card, Col, Descriptions, Drawer, Form, Input, InputNumber,
  Layout, Menu, Popconfirm, Progress, Row, Select, Space, Statistic, Switch, Table, Tabs,
  Tag, Typography, Upload, message,
} from 'antd'
import {
  AimOutlined, AppstoreOutlined, BookOutlined, CloudUploadOutlined, DashboardOutlined,
  DeleteOutlined, FileTextOutlined, InboxOutlined, PlayCircleOutlined, ReloadOutlined,
  SettingOutlined,
} from '@ant-design/icons'
import { api, ArchiveItem, HealthMap, MaterialItem, Settings as SettingsData, TASK_KINDS, Task } from './api'
import { ResultView } from './results'

const { Header, Sider, Content } = Layout
const { Text, Paragraph } = Typography

const STATUS_TAG: Record<string, { color: string; text: string }> = {
  pending: { color: 'default', text: '排队中' },
  running: { color: 'processing', text: '执行中' },
  succeeded: { color: 'success', text: '成功' },
  failed: { color: 'error', text: '失败' },
}

function useTasks(pollMs = 4000) {
  const [tasks, setTasks] = useState<Task[]>([])
  const load = async () => {
    try {
      const next = await api.listTasks()
      // 数据无变化时保持引用，避免轮询重渲染打断点击等交互
      setTasks((prev) => (JSON.stringify(prev) === JSON.stringify(next) ? prev : next))
    } catch { /* ignore */ }
  }
  useEffect(() => {
    load()
    const t = setInterval(load, pollMs)
    return () => clearInterval(t)
  }, [])
  return { tasks, reload: load }
}

// ==================== 仪表盘 ====================
function Dashboard({ go }: { go: (tab: string) => void }) {
  const [health, setHealth] = useState<HealthMap | null>(null)
  const { tasks } = useTasks(8000)
  const [archiveTotal, setArchiveTotal] = useState(0)
  const [llmReady, setLlmReady] = useState<boolean | null>(null)

  const loadHealth = () => api.health().then(setHealth).catch(() => setHealth(null))
  useEffect(() => {
    loadHealth()
    api.getSettings().then((s) => setLlmReady(!!s.llm?.api_key_configured)).catch(() => undefined)
    const t = setInterval(loadHealth, 10000)
    return () => clearInterval(t)
  }, [])
  useEffect(() => {
    api.listArchive().then((r) => setArchiveTotal(r.total)).catch(() => undefined)
  }, [tasks])

  const ok = tasks.filter((t) => t.status === 'succeeded').length
  const bad = tasks.filter((t) => t.status === 'failed').length

  const services = Object.entries(health ?? {})
  return (
    <>
      {llmReady === false && (
        <Alert type="info" showIcon style={{ marginBottom: 16 }} message="演示模式运行中"
          description="当前未配置大模型 API Key，AI 分析返回示例结果（Mock）。全流程可正常跑通——等你准备好，到「系统设置」填入 Key 即自动切换为真实 AI 分析，无需重启。" />
      )}
      <Row gutter={16}>
        <Col span={6}><Card><Statistic title="累计任务" value={tasks.length} /></Card></Col>
        <Col span={6}><Card><Statistic title="成功" value={ok} valueStyle={{ color: '#0a7d3e' }} /></Card></Col>
        <Col span={6}><Card><Statistic title="失败" value={bad} valueStyle={{ color: '#c2255c' }} /></Card></Col>
        <Col span={6}><Card><Statistic title="素材库沉淀" value={archiveTotal} /></Card></Col>
      </Row>
      <Row gutter={16} style={{ marginTop: 16 }}>
        <Col span={12}>
          <Card title="服务状态" extra={<Button size="small" icon={<ReloadOutlined />} onClick={loadHealth} />}>
            {services.map(([k, v]) => (
              <p key={k} style={{ margin: '8px 0' }}>
                <Badge status={v === 'up' ? 'success' : 'error'} text={`${k}：${v === 'up' ? '在线' : '离线'}`} />
              </p>
            ))}
          </Card>
        </Col>
        <Col span={12}>
          <Card title="快捷开始">
            <Space direction="vertical" style={{ width: '100%' }}>
              <Button block icon={<AimOutlined />} onClick={() => go('work')}>
                拆解一条爆款视频
              </Button>
              <Button block icon={<FileTextOutlined />} onClick={() => go('work')}>
                生成一条原创文案
              </Button>
              <Button block icon={<PlayCircleOutlined />} onClick={() => go('work')}>
                一键成片
              </Button>
            </Space>
          </Card>
        </Col>
      </Row>
    </>
  )
}

// ==================== 工作台 ====================
function Workbench({ onSubmitted }: { onSubmitted: (taskId: string) => void }) {
  const [kind, setKind] = useState('analyze-link')
  const [loading, setLoading] = useState(false)
  const [form] = Form.useForm()

  const submit = async () => {
    const values = await form.validateFields()
    // account-review 的 posts 需转 JSON
    const payload: Record<string, unknown> = { ...values }
    if (kind === 'account-review' && values.posts) {
      try { payload.posts = JSON.parse(values.posts) } catch {
        message.error('作品数据不是合法 JSON'); return
      }
    }
    setLoading(true)
    try {
      const { task_id } = await api.createTask(kind, payload)
      message.success(`任务已提交：${task_id.slice(0, 8)}…`)
      form.resetFields()
      onSubmitted(task_id)
    } catch (e) { message.error(String(e)) } finally { setLoading(false) }
  }

  return (
    <Card title={`提交任务 · ${TASK_KINDS[kind]}`} style={{ maxWidth: 680 }}>
      <Select style={{ width: 260, marginBottom: 20 }} value={kind}
        onChange={(k) => { setKind(k); form.resetFields() }}
        options={Object.entries(TASK_KINDS).map(([k, v]) => ({ value: k, label: v }))} />
      <Form form={form} layout="vertical" key={kind} onFinish={submit}>
        {kind === 'analyze-link' && (
          <Form.Item name="url" label="视频链接" rules={[{ required: true, message: '请粘贴视频链接' }]}>
            <Input placeholder="抖音 / 小红书 视频分享链接" />
          </Form.Item>
        )}
        {kind === 'analyze-blogger' && (
          <>
            <Form.Item name="url" label="博主主页链接" rules={[{ required: true, message: '请填写主页链接' }]}>
              <Input placeholder="博主主页 URL 或 ID" />
            </Form.Item>
            <Form.Item name="post_limit" label="采集作品数" initialValue={20}>
              <InputNumber min={1} max={100} style={{ width: 160 }} />
            </Form.Item>
          </>
        )}
        {kind === 'search-keywords' && (
          <>
            <Form.Item name="keyword" label="关键词" rules={[{ required: true, message: '请输入关键词' }]}>
              <Input placeholder="例如：减脂餐（多个用逗号分隔，取第一个搜索）" />
            </Form.Item>
            <Form.Item name="count" label="采集条数" initialValue={10}>
              <InputNumber min={1} max={50} style={{ width: 160 }} />
            </Form.Item>
          </>
        )}
        {kind === 'generate-script' && (
          <Form.Item name="topic" label="主题" rules={[{ required: true, message: '请输入主题' }]}>
            <Input.TextArea placeholder="例如：3分钟学会一道低卡减脂餐" autoSize />
          </Form.Item>
        )}
        {kind === 'generate-video' && (
          <>
            <Form.Item name="topic" label="主题（留空脚本时 AI 自动生成文案）"
              rules={[{ required: true, message: '请输入主题' }]}>
              <Input.TextArea placeholder="例如：新手健身避坑指南" autoSize />
            </Form.Item>
            <Form.Item name="ratio" label="画幅" initialValue="9:16">
              <Select style={{ width: 200 }} options={[
                { value: '9:16', label: '竖屏 9:16' }, { value: '16:9', label: '横屏 16:9' },
                { value: '1:1', label: '方形 1:1' }]} />
            </Form.Item>
            <Form.Item name="video_source" label="素材来源" initialValue="local"
              extra="本地素材库 = 「素材库 → 视频素材」里上传的视频片段（推荐，零外网依赖）；Pixabay 需要稳定的代理网络">
              <Select style={{ width: 220 }} options={[
                { value: 'local', label: '本地素材库' },
                { value: 'pixabay', label: 'Pixabay 在线取材' },
              ]} />
            </Form.Item>
            <Form.Item name="voice_name" label="配音音色（Edge TTS）" initialValue="zh-CN-XiaoxiaoNeural">
              <Select showSearch style={{ width: 320 }} options={[
                'zh-CN-XiaoxiaoNeural', 'zh-CN-YunxiNeural', 'zh-CN-YunyangNeural',
                'zh-CN-XiaoyiNeural', 'zh-CN-YunjianNeural',
              ].map((v) => ({ value: v, label: v }))} />
            </Form.Item>
            <Form.Item name="subtitle_enabled" label="烧录字幕" valuePropName="checked" initialValue={true}>
              <Switch />
            </Form.Item>
          </>
        )}
        {kind === 'rewrite' && (
          <>
            <Form.Item name="text" label="原爆款文案（粘贴全文）"
              rules={[{ required: true, message: '请粘贴要仿写的原文案' }]}>
              <Input.TextArea rows={6} placeholder="粘贴一条爆款文案，AI 将按所选模式仿写成适合你的新文案" />
            </Form.Item>
            <Form.Item name="mode" label="仿写模式" initialValue="structure">
              <Select style={{ width: 260 }} options={[
                { value: 'structure', label: '结构仿写（保留结构换内容）' },
                { value: 'topic', label: '选题提炼（只取选题重新创作）' },
                { value: 'dedup', label: '同主题去重（避开原文表达）' },
              ]} />
            </Form.Item>
            <Form.Item name="my_info" label="你的账号/赛道信息（选填，让文案更贴合你）">
              <Input.TextArea rows={3} placeholder="例如：我是做职场干货的，粉丝 5k，风格偏轻松吐槽" />
            </Form.Item>
          </>
        )}
        {kind === 'account-review' && (
          <>
            <Form.Item name="blogger" label="你的主页链接 / 分享文案 / 抖音号"
              extra="推荐：抖音 App → 我的头像进入主页 → 分享 → 复制链接，整段粘贴。纯数字抖音号可能定位不到主页，失败时请改用分享链接。">
              <Input.TextArea rows={2} placeholder="粘贴主页分享文案（含 https://v.douyin.com/... 链接）" />
            </Form.Item>
            <Form.Item name="post_limit" label="采集作品数" initialValue={20}>
              <InputNumber min={1} max={50} style={{ width: 160 }} />
            </Form.Item>
            <Form.Item name="posts" label="或直接粘贴作品数据 JSON（选填，粘贴了就不再采集）">
              <Input.TextArea rows={4} placeholder={'[{"title":"...", "likes": 1234, "comments": 56}]'} />
            </Form.Item>
          </>
        )}
        <Button type="primary" htmlType="submit" loading={loading} icon={<PlayCircleOutlined />}>
          提交任务
        </Button>
      </Form>
      <Paragraph type="secondary" style={{ marginTop: 12, fontSize: 12.5 }}>
        提示：演示模式下分析结果为示例数据；成片提交后需 MoneyPrinterTurbo 配好素材源 Key（如 Pexels）才会真正出片。
      </Paragraph>
    </Card>
  )
}

// ==================== 任务中心 ====================
function TasksPanel({ tasks, reload, focusTask, clearFocus }: {
  tasks: Task[]; reload: () => void; focusTask: string | null; clearFocus: () => void
}) {
  const [open, setOpen] = useState<Task | null>(null)
  useEffect(() => {
    if (!focusTask) return
    api.getTask(focusTask).then((t) => setOpen(t)).catch(() => undefined)
    clearFocus()
  }, [focusTask])

  const clearAll = async () => {
    try {
      const r = await api.clearTasks()
      message.success(`已清空 ${r.cleared} 条任务记录（素材库不受影响）`)
      if (open) setOpen(null)
      reload()
    } catch (e) { message.error(String(e)) }
  }

  const pollOpen = () => {
    if (open && (open.status === 'pending' || open.status === 'running')) {
      api.getTask(open.id).then(setOpen).catch(() => undefined)
    }
  }
  useEffect(() => {
    const t = setInterval(pollOpen, 3000)
    return () => clearInterval(t)
  }, [open])

  return (
    <>
      <Space style={{ marginBottom: 12 }}>
        <Button icon={<ReloadOutlined />} onClick={reload}>刷新</Button>
        <Popconfirm title="清空全部任务记录？" description="素材库沉淀不受影响"
          onConfirm={clearAll}>
          <Button danger icon={<DeleteOutlined />}>清空记录</Button>
        </Popconfirm>
        <Text type="secondary">每 4 秒自动刷新；点行查看结构化结果</Text>
      </Space>
      <Table<Task> rowKey="id" dataSource={tasks} size="small"
        pagination={{ pageSize: 10 }} onRow={(t) => ({ onClick: () => setOpen(t) })}
        columns={[
          { title: '类型', dataIndex: 'kind', width: 140,
            render: (k: string) => <Tag color="geekblue">{TASK_KINDS[k] ?? k}</Tag> },
          { title: '状态', dataIndex: 'status', width: 100,
            render: (s: string) => <Tag color={STATUS_TAG[s]?.color}>{STATUS_TAG[s]?.text ?? s}</Tag> },
          { title: '输入', dataIndex: 'input', ellipsis: true,
            render: (v: Record<string, unknown>) => {
              const s = v?.url || v?.keyword || v?.topic || v?.blogger || ''
              return String(s) || '-'
            } },
          { title: '创建时间', dataIndex: 'created_at', width: 180,
            render: (v: string) => v ? new Date(v).toLocaleString('zh-CN', { hour12: false }) : '-' },
          { title: '', width: 60,
            render: (_, t) => <Button size="small" type="link">详情</Button> },
        ]}
      />
      <Drawer title={<Space>{open && <Tag color="geekblue">{TASK_KINDS[open.kind] ?? open.kind}</Tag>}
        {open && <Tag color={STATUS_TAG[open.status]?.color}>{STATUS_TAG[open.status]?.text}</Tag>}</Space>}
        width={720} open={!!open} onClose={() => setOpen(null)}
        destroyOnClose>
        {open && open.status === 'failed' && (
          <Alert type="error" showIcon message="任务失败" description={open.error} />
        )}
        {open && (open.status === 'pending' || open.status === 'running') && (
          <Alert type="info" showIcon message="任务执行中，稍后自动刷新…" />
        )}
        {open?.status === 'succeeded' && <ResultView task={open} />}
        {open && open.status === 'succeeded' && open.kind !== 'generate-video' && (
          <FeishuSyncButtons taskId={open.id} />
        )}
      </Drawer>
    </>
  )
}

// ==================== 飞书同步 ====================
function FeishuSyncButtons({ taskId, report }: { taskId?: string; report?: Record<string, unknown> }) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [form] = Form.useForm()

  const sync = async () => {
    const v = await form.validateFields()
    setLoading(true)
    try {
      const r = await api.feishuSync({
        table_token: v.table_token, table_id: v.table_id,
        ...(taskId ? { task_id: taskId } : {}),
        ...(report ? { report } : {}),
      })
      if (r.status === 'ok') message.success('已同步到飞书多维表格')
      else message.error(`同步失败：${r.message}`)
      setOpen(false)
    } catch (e) { message.error(String(e)) } finally { setLoading(false) }
  }
  return (
    <>
      <Button icon={<CloudUploadOutlined />} style={{ marginTop: 16 }}
        onClick={() => setOpen(true)}>同步到飞书表格</Button>
      <Drawer title="同步到飞书多维表格" width={460} open={open}
        onClose={() => setOpen(false)} destroyOnClose>
        <Alert type="info" showIcon style={{ marginBottom: 16 }}
          message="需先在「系统设置」配置飞书 App ID / Secret，并对表格开通编辑权限" />
        <Form form={form} layout="vertical">
          <Form.Item name="table_token" label="多维表格 app_token"
            rules={[{ required: true }]}
            extra="表格 URL 中 /base/ 后面那段">
            <Input placeholder="例如：https://xxx.feishu.cn/base/【这一段】?table=…" />
          </Form.Item>
          <Form.Item name="table_id" label="数据表 table_id" rules={[{ required: true }]}
            extra="表格 URL 中 table= 参数">
            <Input placeholder="tblxxxxxxxx" />
          </Form.Item>
          <Button type="primary" loading={loading} onClick={sync}>开始同步</Button>
        </Form>
      </Drawer>
    </>
  )
}

// ==================== 视频素材（一键成片素材目录） ====================
const fmtSize = (n: number) =>
  n > 1024 * 1024 * 1024 ? `${(n / 1024 / 1024 / 1024).toFixed(2)} GB`
    : n > 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} MB`
    : `${(n / 1024).toFixed(0)} KB`

function MaterialsPanel() {
  const [items, setItems] = useState<MaterialItem[]>([])
  const [dir, setDir] = useState('')
  const [pct, setPct] = useState<number | null>(null)

  const load = () => api.listMaterials()
    .then((r) => { setItems(r.items); setDir(r.dir) })
    .catch(() => undefined)
  useEffect(() => { load() }, [])

  const doUpload = async (file: File) => {
    setPct(0)
    try {
      const r = await api.uploadMaterial(file, setPct)
      message.success(`已上传：${r.name}（${fmtSize(r.size)}）`)
      load()
    } catch (e) { message.error(String(e)) } finally { setPct(null) }
    return false
  }

  return (
    <>
      <Upload.Dragger
        accept=".mp4,.mov,.webm,.avi,.mkv"
        showUploadList={false}
        multiple
        customRequest={({ file }) => doUpload(file as File)}
        style={{ marginBottom: 16, background: '#fafafa' }}
      >
        <p className="ant-upload-drag-icon"><InboxOutlined /></p>
        <p className="ant-upload-text">点击或拖拽视频片段到这里上传</p>
        <p className="ant-upload-hint">
          支持 mp4 / mov / webm / avi / mkv，单个文件最大 200MB；
          上传后即可在「工作台 → 一键成片」选择本地素材库模式使用
        </p>
      </Upload.Dragger>
      {pct !== null && <Progress percent={pct} style={{ marginBottom: 12 }} />}
      <Space style={{ marginBottom: 12 }}>
        <Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>
        <Text type="secondary">共 {items.length} 个素材{dir ? ` · 云端目录 ${dir}` : ''}</Text>
      </Space>
      <Table<MaterialItem> rowKey="name" dataSource={items} size="small"
        pagination={{ pageSize: 10 }}
        columns={[
          { title: '文件名', dataIndex: 'name', ellipsis: true },
          { title: '大小', dataIndex: 'size', width: 110,
            render: (v: number) => fmtSize(v) },
          { title: '上传时间', dataIndex: 'modified_at', width: 180,
            render: (v: string) => v ? new Date(v).toLocaleString('zh-CN', { hour12: false }) : '-' },
          { title: '', width: 70,
            render: (_, it) => (
              <Popconfirm title="删除这个素材？" description="不影响已生成的成片"
                onConfirm={() => api.deleteMaterial(it.name).then(load)}>
                <Button size="small" type="text" danger icon={<DeleteOutlined />} />
              </Popconfirm>
            ) },
        ]}
      />
    </>
  )
}

// ==================== 素材库 ====================
function LibraryPage() {
  return (
    <Tabs
      defaultActiveKey="video"
      items={[
        { key: 'video', label: '视频素材', children: <MaterialsPanel /> },
        { key: 'archive', label: '内容沉淀', children: <ArchivePanel /> },
      ]}
    />
  )
}

function ArchivePanel() {
  const [items, setItems] = useState<ArchiveItem[]>([])
  const [keyword, setKeyword] = useState('')
  const [open, setOpen] = useState<ArchiveItem | null>(null)
  const [kind, setKind] = useState<string | undefined>()

  const load = async () => {
    try {
      const r = await api.listArchive(keyword || undefined, kind)
      setItems(r.items)
    } catch { /* ignore */ }
  }
  useEffect(() => { load() }, [keyword, kind])

  return (
    <>
      <Space style={{ marginBottom: 12 }} wrap>
        <Input.Search placeholder="搜索标题 / 摘要 / 内容" allowClear
          style={{ width: 280 }} onSearch={setKeyword} />
        <Select placeholder="全部类型" allowClear style={{ width: 170 }} value={kind}
          onChange={setKind}
          options={Object.entries(TASK_KINDS).map(([k, v]) => ({ value: k, label: v }))} />
        <Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>
        <Text type="secondary">任务成功后自动沉淀到素材库</Text>
      </Space>
      <Table<ArchiveItem> rowKey="id" dataSource={items} size="small"
        pagination={{ pageSize: 10 }} onRow={(it) => ({ onClick: () => setOpen(it) })}
        columns={[
          { title: '类型', dataIndex: 'kind', width: 130,
            render: (k: string) => <Tag color="purple">{TASK_KINDS[k] ?? k}</Tag> },
          { title: '标题', dataIndex: 'title', ellipsis: true },
          { title: '摘要', dataIndex: 'summary', ellipsis: true },
          { title: '时间', dataIndex: 'created_at', width: 170,
            render: (v: string) => v ? new Date(v).toLocaleString('zh-CN', { hour12: false }) : '-' },
          { title: '', width: 70,
            render: (_, it) => (
              <Popconfirm title="删除这条沉淀？" onConfirm={(e) => {
                e?.stopPropagation()
                api.deleteArchive(it.id).then(load)
              }} onCancel={(e) => e?.stopPropagation()}>
                <Button size="small" type="text" danger icon={<DeleteOutlined />}
                  onClick={(e) => e.stopPropagation()} />
              </Popconfirm>
            ) },
        ]}
      />
      <Drawer title={open?.title} width={720} open={!!open} onClose={() => setOpen(null)}
        destroyOnClose>
        {open && (
          <>
            <Descriptions size="small" column={1} bordered style={{ marginBottom: 16 }}>
              <Descriptions.Item label="来源任务">{open.source_task_id}</Descriptions.Item>
              <Descriptions.Item label="沉淀时间">
                {open.created_at ? new Date(open.created_at).toLocaleString('zh-CN', { hour12: false }) : '-'}
              </Descriptions.Item>
            </Descriptions>
            <ResultView task={{ id: open.id, kind: open.kind, status: 'succeeded', result: open.result }} />
            <FeishuSyncButtons report={open.result} />
          </>
        )}
      </Drawer>
    </>
  )
}

// ==================== 知识库（AnythingLLM 等外部 RAG） ====================
function KbPage() {
  const [url, setUrl] = useState<string | null>(null)
  const load = () => api.getSettings().then((s) => setUrl(s.kb?.url || '')).catch(() => undefined)
  useEffect(() => { load() }, [])

  if (!url) {
    return (
      <Alert type="info" showIcon style={{ maxWidth: 640 }} message="知识库还未配置"
        description="到「系统设置 → 知识库」填入知识库服务地址（如本地部署的 AnythingLLM：http://127.0.0.1:3001），保存后即可在这里直接打开使用。" />
    )
  }
  return (
    <>
      <Space style={{ marginBottom: 12 }}>
        <Button type="primary" icon={<BookOutlined />} onClick={() => window.open(url, '_blank')}>
          新窗口打开知识库
        </Button>
        <Text type="secondary">地址：{url} · 上传运营文档后即可对话式问答</Text>
      </Space>
      <iframe src={url} title="知识库" style={{ width: '100%', height: 'calc(100vh - 160px)', border: '1px solid #eee', borderRadius: 8 }} />
    </>
  )
}

// ==================== 系统设置 ====================
function SettingsPanel() {
  const [form] = Form.useForm()
  const [cfg, setCfg] = useState<SettingsData>({})

  const load = () => api.getSettings().then((s) => {
    setCfg(s)
    form.setFieldsValue({
      llm: { base_url: s.llm?.base_url, model: s.llm?.model },
      feishu: { app_id: s.feishu?.app_id },
    })
  }).catch(() => undefined)
  useEffect(() => { load() }, [])

  const save = async () => {
    const v = await form.validateFields()
    const body = {
      llm: { ...v.llm, api_key: v.llm?.api_key || undefined },
      feishu: { ...v.feishu, app_secret: v.feishu?.app_secret || undefined },
      dtk: { api_key: v.dtk?.api_key || undefined },
    }
    try {
      await api.putSettings(body)
      message.success('已加密保存')
      load()
    } catch (e) { message.error(String(e)) }
  }

  return (
    <div style={{ maxWidth: 680 }}>
      <Alert type="info" showIcon style={{ marginBottom: 16 }}
        message="所有凭据加密存储在本机（Fernet），永不明文回传；现在不填也完全可以，整个平台已在演示模式下可用。"
        description="填好 LLM Key 后，新的分析任务自动切换为真实 AI 输出，无需重启任何服务。" />
      <Card title="大模型（OpenAI 兼容协议）" style={{ marginBottom: 16 }}
        extra={cfg.llm?.api_key_configured
          ? <Tag color="green">Key 已配置 · 真实分析</Tag>
          : <Tag>未配置 · 演示模式（Mock）</Tag>}>
        <Form form={form} layout="vertical">
          <Form.Item name={['llm', 'base_url']} label="Base URL"
            extra="留空默认 DeepSeek（https://api.deepseek.com/v1）；OpenAI 填 https://api.openai.com/v1；本地 Ollama 填 http://127.0.0.1:11434/v1">
            <Input placeholder="https://api.deepseek.com/v1" />
          </Form.Item>
          <Form.Item name={['llm', 'api_key']} label="API Key"
            extra={cfg.llm?.api_key_configured ? '已配置，留空表示不修改' : '推荐 DeepSeek / Kimi / 通义，任意 OpenAI 兼容服务'}>
            <Input.Password placeholder="sk-..." autoComplete="new-password" />
          </Form.Item>
          <Form.Item name={['llm', 'model']} label="模型"
            extra="留空默认 deepseek-chat">
            <Input placeholder="deepseek-chat" />
          </Form.Item>
        </Form>
      </Card>
      <Card title="飞书多维表格" style={{ marginBottom: 16 }}
        extra={cfg.feishu?.app_secret_configured
          ? <Tag color="green">Secret 已配置</Tag> : <Tag>未配置</Tag>}>
        <Form form={form} layout="vertical">
          <Form.Item name={['feishu', 'app_id']} label="App ID">
            <Input placeholder="cli_xxx" />
          </Form.Item>
          <Form.Item name={['feishu', 'app_secret']} label="App Secret"
            extra={cfg.feishu?.app_secret_configured ? '已配置，留空表示不修改' : '飞书开放平台 → 企业自建应用凭据'}>
            <Input.Password autoComplete="new-password" />
          </Form.Item>
        </Form>
      </Card>
      <Card title="DTK 采集引擎（抖音/TikTok）" style={{ marginBottom: 16 }}
        extra={cfg.dtk?.api_key_configured
          ? <Tag color="green">Key 已配置</Tag> : <Tag>未配置 · 采集将降级</Tag>}>
        <Form form={form} layout="vertical">
          <Form.Item name={['dtk', 'api_key']} label="DTK API Key"
            extra="在 DTK 控制台 http://127.0.0.1:8000 的 API Keys 页创建；留空表示不修改">
            <Input.Password placeholder="dtk_..." autoComplete="new-password" />
          </Form.Item>
        </Form>
      </Card>
      <Card title="知识库（AnythingLLM 等 RAG 服务）" style={{ marginBottom: 16 }}
        extra={cfg.kb?.url ? <Tag color="green">已配置</Tag> : <Tag>未配置</Tag>}>
        <Form form={form} layout="vertical">
          <Form.Item name={['kb', 'url']} label="知识库地址"
            extra="例如本地部署的 AnythingLLM：http://127.0.0.1:3001；配置后左侧「知识库」页可直接打开，上传运营文档即可对话问答">
            <Input placeholder="http://127.0.0.1:3001" />
          </Form.Item>
        </Form>
      </Card>
      <Button type="primary" onClick={save} size="large">保存设置</Button>
    </div>
  )
}

// ==================== 根布局 ====================
export default function App() {
  const [tab, setTab] = useState('dash')
  const [health, setHealth] = useState<HealthMap | null>(null)
  const { tasks, reload } = useTasks(4000)
  const [focusTask, setFocusTask] = useState<string | null>(null)

  useEffect(() => {
    const load = () => api.health().then(setHealth).catch(() => setHealth(null))
    load()
    const t = setInterval(load, 10000)
    return () => clearInterval(t)
  }, [])

  const running = useMemo(
    () => tasks.filter((t) => t.status === 'pending' || t.status === 'running').length,
    [tasks])

  const items = [
    { key: 'dash', icon: <DashboardOutlined />, label: '仪表盘',
      children: <Dashboard go={setTab} /> },
    { key: 'work', icon: <PlayCircleOutlined />, label: '工作台',
      children: <Workbench onSubmitted={(tid) => { setFocusTask(tid); setTab('tasks') }} /> },
    { key: 'tasks', icon: <AppstoreOutlined />, label: <span>任务中心
      {running > 0 && <Badge count={running} size="small" style={{ marginLeft: 6 }} />}</span>,
      children: <TasksPanel tasks={tasks} reload={reload}
        focusTask={focusTask} clearFocus={() => setFocusTask(null)} /> },
    { key: 'archive', icon: <FileTextOutlined />, label: '素材库',
      children: <LibraryPage /> },
    { key: 'settings', icon: <SettingOutlined />, label: '系统设置',
      children: <SettingsPanel /> },
  ]

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider theme="dark" width={200}>
        <div style={{ color: '#fff', padding: '18px 16px 10px', fontWeight: 700, fontSize: 16 }}>
          陈镇鑫傻瓜式操作平台
        </div>
        <Menu theme="dark" mode="inline" selectedKeys={[tab]}
          onClick={(e) => setTab(e.key)} items={items.map(({ key, icon, label }) => ({ key, icon, label }))} />
      </Sider>
      <Layout>
        <Header style={{ background: '#fff', padding: '0 24px', borderBottom: '1px solid #eee',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: 52 }}>
          <Text strong style={{ fontSize: 15 }}>
            {items.find((i) => i.key === tab)?.label}
          </Text>
          <Space size={6}>
            {Object.entries(health ?? {}).map(([k, v]) => (
              <Tag key={k} color={v === 'up' ? 'green' : 'red'} style={{ marginRight: 0 }}>
                {k} {v === 'up' ? '●' : '○'}
              </Tag>
            ))}
          </Space>
        </Header>
        <Content style={{ padding: 20 }}>
          <Tabs activeKey={tab} onChange={setTab} items={items} hideAdd={false}
            tabBarStyle={{ display: 'none' }} type="card" />
        </Content>
      </Layout>
    </Layout>
  )
}
