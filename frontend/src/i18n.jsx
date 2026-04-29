import { createContext, useContext, useEffect, useState } from 'react'

/* ── Translation table ───────────────────────────────────────────────── */

const translations = {
  en: {
    'sidebar.workspaces':      'Workspaces',
    'sidebar.no_workspaces':   'No workspaces yet',
    'sidebar.new_workspace':   'New workspace',
    'sidebar.chats':           'Chats',
    'sidebar.no_chats':        'No chats yet',
    'sidebar.new_chat':        'New chat',
    'sidebar.toggle_light':    'Switch to light mode',
    'sidebar.toggle_dark':     'Switch to dark mode',
    'sidebar.toggle_lang':     'Switch to 中文',
    'sidebar.footer':          'v0.1 · local-first',

    'chat.empty_chat':         'Select or create a chat',
    'chat.empty_workspace':    'Select a workspace to begin',
    'chat.send_to_start':      'Send a message to begin',
    'chat.deep_thinking':      'Deep thinking',
    'chat.placeholder':        'Type a message...  (Enter to send, Shift+Enter for newline)',
    'chat.thinking':           'Thinking...',
    'chat.process':            'Run',
    'chat.new_chat_default':   'New chat',

    'plan.title':              'Plan',
    'plan.depends_on':         '← depends on step',
    'thinking.title':          'Deep thinking',

    'agent.running':           'Running...',
    'agent.file_agent':        'File',
    'agent.search_agent':      'Search',
    'agent.code_agent':        'Code',
    'agent.writer_agent':      'Writer',

    'notes.title':             'Notes',
    'notes.empty':             'No notes yet',
    'notes.new':               'New note',
    'notes.new_default':       'Untitled',
    'notes.empty_placeholder': '(empty)',
    'notes.title_placeholder': 'Title',
    'notes.content_placeholder':'Write something...',

    'common.save':             'Save',
    'common.cancel':           'Cancel',

    'modal.workspace_title':   'New workspace',
    'modal.name':              'Name',
    'modal.name_placeholder':  'My project',
    'modal.path':              'Path',
    'modal.create':            'Create',
    'modal.creating':          'Creating...',
    'modal.pick_this':         'Use this folder',
    'modal.pick':              'Pick',
    'modal.empty_dir':         'Empty folder',
  },

  zh: {
    'sidebar.workspaces':      '工作区',
    'sidebar.no_workspaces':   '还没有工作区',
    'sidebar.new_workspace':   '新建工作区',
    'sidebar.chats':           '对话',
    'sidebar.no_chats':        '暂无对话',
    'sidebar.new_chat':        '新建对话',
    'sidebar.toggle_light':    '切换浅色模式',
    'sidebar.toggle_dark':     '切换深色模式',
    'sidebar.toggle_lang':     'Switch to English',
    'sidebar.footer':          'v0.1 · 本地优先',

    'chat.empty_chat':         '选择或创建一个对话',
    'chat.empty_workspace':    '选择一个工作区开始',
    'chat.send_to_start':      '发送一条消息开始对话',
    'chat.deep_thinking':      '深度思考',
    'chat.placeholder':        '输入消息...  (Enter 发送, Shift+Enter 换行)',
    'chat.thinking':           '思考中...',
    'chat.process':            '执行过程',
    'chat.new_chat_default':   '新对话',

    'plan.title':              '执行计划',
    'plan.depends_on':         '← 依赖步骤',
    'thinking.title':          '深度思考',

    'agent.running':           '执行中...',
    'agent.file_agent':        '文件分析',
    'agent.search_agent':      '搜索',
    'agent.code_agent':        '代码分析',
    'agent.writer_agent':      '写作',

    'notes.title':             '笔记',
    'notes.empty':             '暂无笔记',
    'notes.new':               '新建笔记',
    'notes.new_default':       '新笔记',
    'notes.empty_placeholder': '(空)',
    'notes.title_placeholder': '标题',
    'notes.content_placeholder':'写点什么...',

    'common.save':             '保存',
    'common.cancel':           '取消',

    'modal.workspace_title':   '新建工作区',
    'modal.name':              '名称',
    'modal.name_placeholder':  '我的项目',
    'modal.path':              '路径',
    'modal.create':            '创建',
    'modal.creating':          '创建中...',
    'modal.pick_this':         '选择此目录',
    'modal.pick':              '选择',
    'modal.empty_dir':         '空目录',
  },
}

/* ── Context ─────────────────────────────────────────────────────────── */

const LangContext = createContext({ lang: 'en', t: k => k, setLang: () => {} })

export function LangProvider({ children }) {
  const [lang, setLangState] = useState(() => {
    const saved = typeof localStorage !== 'undefined' && localStorage.getItem('atelier-lang')
    if (saved === 'zh' || saved === 'en') return saved
    // First visit: default to English; flip to zh if browser tells us so
    if (typeof navigator !== 'undefined' && /^zh\b/i.test(navigator.language)) return 'zh'
    return 'en'
  })

  useEffect(() => {
    document.documentElement.setAttribute('lang', lang === 'zh' ? 'zh-CN' : 'en')
    localStorage.setItem('atelier-lang', lang)
  }, [lang])

  function setLang(l) { setLangState(l) }
  function t(key) { return translations[lang]?.[key] ?? translations.en[key] ?? key }

  return <LangContext.Provider value={{ lang, t, setLang }}>{children}</LangContext.Provider>
}

export function useLang() { return useContext(LangContext) }
