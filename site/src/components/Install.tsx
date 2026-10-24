import { useRef, useState } from 'react'
import { shellPath } from '@/lib/shell'

// The install dialog, already open: where to clone, and the three commands built from it,
// copied in one press.
export function Install() {
  const [folder, setFolder] = useState('~/code/Engram')
  const where = shellPath(folder.trim() || '~/code/Engram')
  const [copied, setCopied] = useState<'no' | 'yes' | 'failed'>('no')
  const commandsRef = useRef<HTMLElement>(null)
  const commands = [
    `git clone https://github.com/aimsotrash/Engram ${where} && cd ${where}`,
    'python3.12 -m venv .venv && .venv/bin/pip install -r engram_mcp/requirements.txt',
    // -s user: the commands run inside the clone, so the default scope would mean only that folder.
    'claude mcp add engram -s user -e PYTHONPATH="$PWD" -- "$PWD/.venv/bin/python" -P -m engram_mcp',
  ].join(' &&\n') // the first failure stops the rest, so a broken server is never registered

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(commands)
      setCopied('yes')
      setTimeout(() => setCopied('no'), 2000)
    } catch {
      // No clipboard access (an insecure page, or the browser refused): select the commands instead.
      const range = document.createRange()
      if (commandsRef.current) range.selectNodeContents(commandsRef.current)
      getSelection()?.removeAllRanges()
      getSelection()?.addRange(range)
      setCopied('failed')
    }
  }

  return (
    <div data-ui role="group" aria-labelledby="install-title"
         className={"w-[min(100%,440px)] rounded-xl bg-white p-6 text-[14px] text-[#111] shadow-[0_24px_60px_-20px_rgba(0,0,0,0.45)] dark:bg-[#1a1a1a] dark:text-[#ededed]" /* taste-skill-ignore: a real dialog casts its shadow */}>
      <h3 id="install-title" className="text-[17px] font-semibold tracking-normal">Add Engram to Claude Code</h3>
      <label htmlFor="install-folder" className="mt-5 block font-medium">Where to clone it</label>
      <input id="install-folder" value={folder} onChange={(e) => setFolder(e.target.value)}
             spellCheck={false}
             className="mt-2 h-10 w-full rounded-md border border-[#d9d9d9] bg-white px-3 text-[14px] outline-none focus:border-[#1a4be0] focus:ring-2 focus:ring-[#1a4be0]/25 dark:border-[#333] dark:bg-[#111]" />
      <pre className="mt-5 whitespace-pre-wrap rounded-md bg-[#f4f4f4] p-3 text-[13px] leading-relaxed [overflow-wrap:anywhere] dark:bg-[#111]"><code ref={commandsRef}>{commands}</code></pre>
      <button onClick={copy}
              className="mt-5 h-11 w-full rounded-md bg-[#1a4be0] font-medium text-white transition-transform hover:bg-[#1640c4] active:scale-[0.99]">
        {copied === 'yes' ? 'Copied' : 'Copy the commands'}
      </button>
      <p className="mt-3 text-[13px] text-[#6b6b6b] dark:text-[#a8a8a8]" aria-live="polite">
        {copied === 'yes' ? 'Paste them into a terminal. The first remember or recall downloads a 90 MB model.'
          : copied === 'failed' ? 'The commands are selected: press Ctrl+C, or ⌘C on a Mac, to copy them.'
          : 'Needs Python 3.12 and Claude Code, on Linux or an Apple silicon Mac (macOS 14+).'}
      </p>
    </div>
  )
}
