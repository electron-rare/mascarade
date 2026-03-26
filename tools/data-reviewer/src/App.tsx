import { useState, useEffect, useCallback, useRef } from 'react'

interface ConvEntry { from: string; value: string }
interface Example { id: number; conversations: ConvEntry[]; domain?: string; source?: string; score?: number; approved?: boolean; notes?: string }
interface DatasetInfo { name: string; count: number; domain: string; path: string }

function CodeBlock({ code }: { code: string }) {
  const lines = code.split('\n')
  return (
    <div className="bg-gray-900 rounded overflow-x-auto text-xs">
      <table className="w-full">
        <tbody>
          {lines.map((line, i) => (
            <tr key={i} className="hover:bg-gray-800/50">
              <td className="text-gray-600 text-right pr-3 pl-2 select-none w-8 border-r border-gray-800">{i+1}</td>
              <td className="pl-3 pr-4"><pre className="whitespace-pre">{line}</pre></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function RichText({ text, editing, onEdit }: { text: string; editing: boolean; onEdit: (v: string) => void }) {
  if (editing) {
    return <textarea value={text} onChange={e => onEdit(e.target.value)}
      className="w-full h-64 bg-gray-900 text-green-200 p-3 rounded font-mono text-sm resize-y border border-gray-700 focus:border-blue-500 outline-none" />
  }
  const parts = text.split(/(```[\s\S]*?```)/g)
  return (
    <div className="space-y-2">
      {parts.map((part, i) => {
        if (part.startsWith('```')) {
          const code = part.replace(/^```\w*\n?/, '').replace(/\n?```$/, '')
          return <CodeBlock key={i} code={code} />
        }
        return part.trim() ? <p key={i} className="text-sm leading-relaxed whitespace-pre-wrap">{part}</p> : null
      })}
    </div>
  )
}

function App() {
  const [datasets, setDatasets] = useState<DatasetInfo[]>([])
  const [selected, setSelected] = useState('')
  const [examples, setExamples] = useState<Example[]>([])
  const [idx, setIdx] = useState(0)
  const [filter, setFilter] = useState<'all'|'pending'|'approved'|'rejected'>('all')
  const [loading, setLoading] = useState(false)
  const [stats, setStats] = useState({ total: 0, approved: 0, rejected: 0, pending: 0 })
  const [editMode, setEditMode] = useState(false)
  const [editIdx, setEditIdx] = useState(-1)
  const [editText, setEditText] = useState('')
  const [searchQ, setSearchQ] = useState('')
  const [compareMode, setCompareMode] = useState(false)
  const [compareData, setCompareData] = useState<Example[]>([])
  const [toast, setToast] = useState('')
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => { fetch('/api/datasets').then(r => r.json()).then(setDatasets) }, [])

  const loadDataset = (name: string) => {
    setLoading(true)
    setSelected(name)
    setEditMode(false)
    setCompareMode(false)
    fetch(`/api/dataset/${name}`).then(r => r.json()).then(d => {
      setExamples(d.examples)
      setStats(d.stats)
      setIdx(0)
      setLoading(false)
    })
  }

  const loadCompare = (name: string) => {
    const impName = name.replace('_final', '_improved')
    fetch(`/api/dataset/${impName}`).then(r => r.json()).then(d => {
      setCompareData(d.examples)
      setCompareMode(true)
    }).catch(() => setToast('No improved version found'))
  }

  const save = useCallback((id: number, updates: Partial<Example>) => {
    fetch(`/api/example/${selected}/${id}`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates)
    }).then(r => r.json()).then(d => {
      setStats(d.stats)
      setExamples(prev => prev.map(e => e.id === id ? { ...e, ...updates } : e))
    })
  }, [selected])

  const showToast = (msg: string) => { setToast(msg); setTimeout(() => setToast(''), 2000) }

  const getFiltered = useCallback(() => {
    return examples.filter(e => {
      if (filter === 'approved') return e.approved === true
      if (filter === 'rejected') return e.approved === false
      if (filter === 'pending') return e.approved === undefined
      return true
    }).filter(e => {
      if (!searchQ) return true
      return e.conversations.map(c => c.value).join(' ').toLowerCase().includes(searchQ.toLowerCase())
    })
  }, [examples, filter, searchQ])

  const doApprove = useCallback(() => {
    const curFiltered = examples.filter(e => {
      if (filter === 'approved') return e.approved === true
      if (filter === 'rejected') return e.approved === false
      if (filter === 'pending') return e.approved === undefined
      return true
    })
    const cur = curFiltered[idx]
    if (!cur) return
    save(cur.id, { approved: true })
    showToast('Approved')
    setIdx(i => Math.min(curFiltered.length - 1, i + 1))
  }, [save, idx, examples, filter])

  const doReject = useCallback(() => {
    const curFiltered = examples.filter(e => {
      if (filter === 'approved') return e.approved === true
      if (filter === 'rejected') return e.approved === false
      if (filter === 'pending') return e.approved === undefined
      return true
    })
    const cur = curFiltered[idx]
    if (!cur) return
    save(cur.id, { approved: false })
    showToast('Rejected')
    setIdx(i => Math.min(curFiltered.length - 1, i + 1))
  }, [save, idx, examples, filter])

  const startEdit = (convIdx: number, conversations: ConvEntry[]) => {
    setEditMode(true)
    setEditIdx(convIdx)
    setEditText(conversations[convIdx].value)
  }

  const saveEdit = () => {
    const curEx = getFiltered()[idx]
    if (!curEx || editIdx < 0) return
    fetch(`/api/example/${selected}/${curEx.id}/edit`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ conv_idx: editIdx, value: editText })
    }).then(r => r.json()).then(() => {
      curEx.conversations[editIdx].value = editText
      setEditMode(false)
      setEditIdx(-1)
      showToast('Saved edit')
    })
  }

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (editMode) return
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return
      switch(e.key) {
        case 'a': case 'A': doApprove(); break
        case 'r': case 'R': doReject(); break
        case 'ArrowRight': case 'j': setIdx(i => Math.min(filtered.length - 1, i + 1)); break
        case 'ArrowLeft': case 'k': setIdx(i => Math.max(0, i - 1)); break
        case 'e': case 'E': {
          const curEx = examples.filter(e => filter === 'all' || (filter === 'approved' && e.approved === true) || (filter === 'rejected' && e.approved === false) || (filter === 'pending' && e.approved === undefined))[idx]
          if (curEx) { const gptIdx = curEx.conversations.findIndex(c => c.from === 'gpt' || c.from === 'assistant'); if (gptIdx >= 0) startEdit(gptIdx, curEx.conversations) }
          break
        }
        case 'Escape': setEditMode(false); break
        case '1': case '2': case '3': case '4': case '5': case '6': case '7': case '8': case '9': {
          const cur2 = getFiltered()[idx]
          if (cur2) save(cur2.id, { score: parseInt(e.key) }); showToast(`Score: ${e.key}/10`); break
        }
        case '0': {
          const cur3 = getFiltered()[idx]
          if (cur3) save(cur3.id, { score: 10 }); showToast('Score: 10/10'); break
        }
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [doApprove, doReject, editMode, getFiltered, idx, save])

  const filtered = getFiltered()

  const ex = filtered[idx]
  const compareEx = compareMode && ex ? compareData.find(c => c.id === ex.id) : null

  const roleStyle = (from: string) => {
    if (from === 'system') return 'border-l-4 border-gray-600 bg-gray-900/50'
    if (from === 'human' || from === 'user') return 'border-l-4 border-blue-500 bg-blue-950/30'
    return 'border-l-4 border-green-500 bg-green-950/30'
  }

  const roleIcon = (from: string) => {
    if (from === 'system') return 'SYS'
    if (from === 'human' || from === 'user') return 'USR'
    return 'AI'
  }

  const statusBadge = (e: Example) => {
    if (e.approved === true) return <span className="px-1.5 py-0.5 bg-green-800 text-green-200 rounded text-xs">OK</span>
    if (e.approved === false) return <span className="px-1.5 py-0.5 bg-red-800 text-red-200 rounded text-xs">REJ</span>
    return <span className="px-1.5 py-0.5 bg-gray-700 text-gray-400 rounded text-xs">?</span>
  }

  const progressBar = () => {
    return (
      <div className="w-full h-2 bg-gray-800 rounded overflow-hidden">
        <div className="h-full flex">
          <div className="bg-green-600 transition-all" style={{ width: `${stats.approved / Math.max(stats.total, 1) * 100}%` }} />
          <div className="bg-red-600 transition-all" style={{ width: `${stats.rejected / Math.max(stats.total, 1) * 100}%` }} />
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100" ref={containerRef}>
      {/* Toast */}
      {toast && <div className="fixed top-4 right-4 z-50 px-4 py-2 bg-blue-600 rounded shadow-lg text-sm animate-pulse">{toast}</div>}

      {/* Header */}
      <div className="sticky top-0 z-40 bg-gray-950/95 backdrop-blur border-b border-gray-800 px-4 py-3">
        <div className="max-w-7xl mx-auto">
          <div className="flex items-center justify-between mb-2">
            <h1 className="text-lg font-bold">Mascarade Data Reviewer</h1>
            <div className="flex items-center gap-3 text-xs">
              <kbd className="px-1.5 py-0.5 bg-gray-800 rounded">A</kbd><span className="text-gray-500">approve</span>
              <kbd className="px-1.5 py-0.5 bg-gray-800 rounded">R</kbd><span className="text-gray-500">reject</span>
              <kbd className="px-1.5 py-0.5 bg-gray-800 rounded">E</kbd><span className="text-gray-500">edit</span>
              <kbd className="px-1.5 py-0.5 bg-gray-800 rounded">1-0</kbd><span className="text-gray-500">score</span>
              <kbd className="px-1.5 py-0.5 bg-gray-800 rounded">J/K</kbd><span className="text-gray-500">nav</span>
            </div>
          </div>

          {/* Dataset tabs */}
          <div className="flex gap-1 mb-2 overflow-x-auto pb-1">
            {datasets.filter(d => d.count > 1).map(d => (
              <button key={d.name} onClick={() => loadDataset(d.name)}
                className={`px-2 py-1 rounded text-xs whitespace-nowrap transition ${selected === d.name ? 'bg-blue-600 text-white' : 'bg-gray-800/80 text-gray-400 hover:bg-gray-700 hover:text-gray-200'}`}>
                {d.name.replace('_final.jsonl','').replace('_improved.jsonl','').replace('_improved','')}
                <span className="ml-1 text-gray-500">{d.count}</span>
              </button>
            ))}
          </div>

          {selected && (
            <div className="flex items-center gap-3">
              {progressBar()}
              <div className="flex gap-3 text-xs whitespace-nowrap">
                <span className="text-green-400">{stats.approved} ok</span>
                <span className="text-red-400">{stats.rejected} rej</span>
                <span className="text-gray-500">{stats.pending} left</span>
              </div>
              <div className="flex gap-1">
                {(['all','pending','approved','rejected'] as const).map(f => (
                  <button key={f} onClick={() => { setFilter(f); setIdx(0) }}
                    className={`px-2 py-0.5 rounded text-xs ${filter === f ? 'bg-blue-600' : 'bg-gray-800 hover:bg-gray-700'}`}>{f}</button>
                ))}
              </div>
              <input type="text" placeholder="Search..." value={searchQ} onChange={e => { setSearchQ(e.target.value); setIdx(0) }}
                className="bg-gray-800 px-2 py-1 rounded text-xs w-40 border border-gray-700 focus:border-blue-500 outline-none" />
              {selected.includes('_final') && (
                <button onClick={() => compareMode ? setCompareMode(false) : loadCompare(selected)}
                  className={`px-2 py-0.5 rounded text-xs ${compareMode ? 'bg-orange-600' : 'bg-gray-800 hover:bg-gray-700'}`}>
                  {compareMode ? 'Hide diff' : 'Compare improved'}
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Main content */}
      <div className="max-w-7xl mx-auto p-4">
        {selected && !loading && (
          <div className="flex gap-4">
            {/* Left: mini-list */}
            <div className="w-64 shrink-0 space-y-1 max-h-[calc(100vh-200px)] overflow-y-auto">
              {filtered.slice(Math.max(0, idx - 10), idx + 30).map((e, i) => {
                const realIdx = Math.max(0, idx - 10) + i
                const q = e.conversations.find(c => c.from === 'human' || c.from === 'user')?.value || ''
                return (
                  <button key={e.id} onClick={() => setIdx(realIdx)}
                    className={`w-full text-left px-2 py-1.5 rounded text-xs truncate transition ${realIdx === idx ? 'bg-blue-900/50 text-blue-200 border border-blue-700' : 'bg-gray-900/50 text-gray-400 hover:bg-gray-800'}`}>
                    <div className="flex items-center gap-1">
                      {statusBadge(e)}
                      {e.score ? <span className="text-yellow-500">{e.score}</span> : null}
                      <span className="truncate">{q.slice(0, 60)}</span>
                    </div>
                  </button>
                )
              })}
            </div>

            {/* Right: example detail */}
            <div className="flex-1 min-w-0">
              {ex ? (
                <div className="space-y-3">
                  {/* Meta */}
                  <div className="flex items-center gap-2 text-xs">
                    {statusBadge(ex)}
                    {ex.score && <span className="text-yellow-400 font-bold">{ex.score}/10</span>}
                    <span className="text-gray-600">#{ex.id}</span>
                    <span className="text-gray-600">{ex.domain}</span>
                    <span className="text-gray-600 truncate">{ex.source?.slice(0,40)}</span>
                    <div className="flex-1" />
                    <span className="text-gray-600">{idx+1}/{filtered.length}</span>
                  </div>

                  {/* Conversations */}
                  <div className={compareMode ? 'grid grid-cols-2 gap-4' : ''}>
                    <div className="space-y-2">
                      {compareMode && <div className="text-xs text-gray-500 font-bold mb-1">ORIGINAL</div>}
                      {ex.conversations.map((c, i) => (
                        <div key={i} className={`p-3 rounded ${roleStyle(c.from)} group relative`}>
                          <div className="flex items-center gap-2 mb-2">
                            <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${c.from === 'system' ? 'bg-gray-700' : c.from === 'human' || c.from === 'user' ? 'bg-blue-800' : 'bg-green-800'}`}>
                              {roleIcon(c.from)}
                            </span>
                            {(c.from === 'gpt' || c.from === 'assistant') && !editMode && (
                              <button onClick={() => startEdit(i, ex.conversations)} className="opacity-0 group-hover:opacity-100 text-xs text-gray-500 hover:text-blue-400 transition">edit</button>
                            )}
                          </div>
                          {editMode && editIdx === i ? (
                            <div className="space-y-2">
                              <textarea value={editText} onChange={e => setEditText(e.target.value)}
                                className="w-full h-80 bg-gray-900 text-green-200 p-3 rounded font-mono text-sm resize-y border border-blue-500 outline-none" autoFocus />
                              <div className="flex gap-2">
                                <button onClick={saveEdit} className="px-3 py-1 bg-blue-600 hover:bg-blue-500 rounded text-xs font-bold">Save</button>
                                <button onClick={() => setEditMode(false)} className="px-3 py-1 bg-gray-700 rounded text-xs">Cancel</button>
                              </div>
                            </div>
                          ) : (
                            <RichText text={c.value} editing={false} onEdit={() => {}} />
                          )}
                        </div>
                      ))}
                    </div>

                    {/* Compare panel */}
                    {compareMode && compareEx && (
                      <div className="space-y-2">
                        <div className="text-xs text-orange-400 font-bold mb-1">IMPROVED</div>
                        {compareEx.conversations.map((c, i) => (
                          <div key={i} className={`p-3 rounded ${roleStyle(c.from)} border-orange-800/30`}>
                            <div className="flex items-center gap-2 mb-2">
                              <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${c.from === 'system' ? 'bg-gray-700' : c.from === 'human' || c.from === 'user' ? 'bg-blue-800' : 'bg-orange-800'}`}>
                                {roleIcon(c.from)}
                              </span>
                              {ex.conversations[i] && c.value !== ex.conversations[i].value && (
                                <span className="text-[10px] text-orange-400 font-bold">MODIFIED</span>
                              )}
                            </div>
                            <RichText text={c.value} editing={false} onEdit={() => {}} />
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Notes */}
                  <div className="mt-2">
                    <input type="text" placeholder="Add note..." value={ex.notes || ''}
                      onChange={e => { save(ex.id, { notes: e.target.value }); ex.notes = e.target.value }}
                      className="w-full bg-gray-900 px-3 py-2 rounded text-sm border border-gray-800 focus:border-blue-500 outline-none" />
                  </div>

                  {/* Actions bar */}
                  <div className="flex items-center gap-2 mt-3 p-3 bg-gray-900/50 rounded-lg sticky bottom-4">
                    <button onClick={doApprove} className="px-5 py-2.5 bg-green-700 hover:bg-green-600 rounded-lg font-bold text-sm transition">
                      Approve (A)
                    </button>
                    <button onClick={doReject} className="px-5 py-2.5 bg-red-700 hover:bg-red-600 rounded-lg font-bold text-sm transition">
                      Reject (R)
                    </button>
                    <button onClick={() => setIdx(idx+1)} className="px-4 py-2.5 bg-gray-700 hover:bg-gray-600 rounded-lg text-sm transition">
                      Skip
                    </button>
                    <div className="flex gap-1 ml-2">
                      {[1,2,3,4,5,6,7,8,9,10].map(n => (
                        <button key={n} onClick={() => { save(ex.id, { score: n }); showToast(`Score: ${n}/10`) }}
                          className={`w-7 h-7 rounded text-xs font-bold transition ${ex.score === n ? 'bg-yellow-600 text-white' : n <= 3 ? 'bg-red-900/50 text-red-300 hover:bg-red-800' : n <= 6 ? 'bg-yellow-900/50 text-yellow-300 hover:bg-yellow-800' : 'bg-green-900/50 text-green-300 hover:bg-green-800'}`}>
                          {n}
                        </button>
                      ))}
                    </div>
                    <div className="flex-1" />
                    <a href={`/api/export/${selected}`} className="px-3 py-2 bg-purple-800 hover:bg-purple-700 rounded text-xs transition">
                      Export JSONL
                    </a>
                  </div>
                </div>
              ) : <p className="text-gray-500 text-center py-20">No examples match filter</p>}
            </div>
          </div>
        )}

        {loading && <p className="text-center py-20 text-gray-500">Loading...</p>}
        {!selected && <p className="text-center py-20 text-gray-500">Select a dataset above</p>}
      </div>
    </div>
  )
}

export default App
