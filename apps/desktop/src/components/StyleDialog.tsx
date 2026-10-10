import { useState } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import clsx from 'clsx'
import { PRESET_STYLES, getPrefs, setPrefs, usePrefs, type CustomStyle } from '../lib/prefs'
import { FIELD } from '../lib/ui'
import { Btn, Dialog, DialogActions } from './Dialog'
import { t } from '../lib/i18n'

/** 风格（照 Claude 的 Styles）：预设只读，自定义可增删改；当前风格写进交给核心的“用户设置” */
export function StyleDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <Dialog open={open} onClose={onClose} title={t('风格')} width={620} testId="style-dialog">
      {open && <StyleBody onClose={onClose} />}
    </Dialog>
  )
}

function StyleBody({ onClose }: { onClose: () => void }) {
  const prefs = usePrefs()
  const [sel, setSel] = useState<string>(prefs.style)
  const custom = prefs.customStyles.find((c) => c.id === sel)
  const preset = PRESET_STYLES.find((p) => p.id === sel)
  const [draft, setDraft] = useState<CustomStyle | null>(custom ?? null)

  const pick = (id: string) => {
    setSel(id)
    setDraft(getPrefs().customStyles.find((c) => c.id === id) ?? null)
  }
  const create = () => {
    const c: CustomStyle = { id: `c${Date.now().toString(36)}`, name: t('我的风格'), prompt: '' }
    setPrefs({ customStyles: [...getPrefs().customStyles, c] })
    pick(c.id)
    setDraft(c)
  }
  const save = () => {
    if (!draft) return
    setPrefs({
      customStyles: getPrefs().customStyles.map((c) => (c.id === draft.id ? { ...draft, name: draft.name.trim() || t('我的风格') } : c)),
      style: draft.id,
    })
    onClose()
  }
  const remove = () => {
    if (!draft) return
    const rest = getPrefs().customStyles.filter((c) => c.id !== draft.id)
    setPrefs({ customStyles: rest, style: getPrefs().style === draft.id ? 'standard' : getPrefs().style })
    pick('standard')
  }
  const list = [...PRESET_STYLES.map((p) => ({ id: p.id, name: p.name })), ...prefs.customStyles.map((c) => ({ id: c.id, name: c.name }))]

  return (
    <div className="flex min-h-[300px] gap-4">
      <div className="w-[170px] shrink-0 space-y-0.5 border-r border-border-soft pr-3">
        {list.map((s) => (
          <button
            key={s.id}
            type="button"
            onClick={() => pick(s.id)}
            data-testid={`style-row-${s.id}`}
            className={clsx(
              'block w-full truncate rounded-lg px-2.5 py-1.5 text-left text-[13px] transition-colors duration-200',
              sel === s.id ? 'bg-panel-raised text-ink' : 'text-ink-soft hover:bg-panel-raised/60',
            )}
          >
            {s.name}
          </button>
        ))}
        <button
          type="button"
          onClick={create}
          data-testid="style-new"
          className="mt-2 flex w-full items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[13px] text-amber transition-colors hover:bg-panel-raised/60"
        >
          <Plus size={13} /> {t('新建风格')}
        </button>
      </div>
      <div className="flex min-w-0 flex-1 flex-col">
        {draft ? (
          <>
            <label className="text-[12px] text-sepia-muted" htmlFor="style-name">
              {t('名称')}
            </label>
            <input
              id="style-name"
              data-testid="style-name"
              value={draft.name}
              maxLength={30}
              onChange={(e) => setDraft({ ...draft, name: e.target.value })}
              className={clsx(FIELD, 'mt-1')}
            />
            <label className="mt-3 text-[12px] text-sepia-muted" htmlFor="style-prompt">
              {t('怎么回答')}
            </label>
            <textarea
              id="style-prompt"
              data-testid="style-prompt"
              value={draft.prompt}
              maxLength={2000}
              rows={6}
              placeholder={t('例如：先给结论，再列三条要点；少用形容词。')}
              onChange={(e) => setDraft({ ...draft, prompt: e.target.value })}
              className={clsx(FIELD, 'mt-1 flex-1 resize-none leading-relaxed')}
            />
            <DialogActions>
              <Btn kind="danger" onClick={remove} testId="style-delete">
                <span className="inline-flex items-center gap-1">
                  <Trash2 size={12} /> {t('删除')}
                </span>
              </Btn>
              <span className="flex-1" />
              <Btn onClick={onClose}>{t('取消')}</Btn>
              <Btn kind="solid" onClick={save} testId="style-save" disabled={!draft.prompt.trim()}>
                {t('保存并使用')}
              </Btn>
            </DialogActions>
          </>
        ) : (
          <>
            <p className="font-serif text-[16px] text-ink">{preset?.name}</p>
            <p className="mt-2 text-[13px] leading-relaxed text-ink-soft">{preset?.prompt || t('默认的回答方式。')}</p>
            <DialogActions>
              <Btn onClick={onClose}>{t('取消')}</Btn>
              <Btn
                kind="solid"
                testId="style-use"
                onClick={() => {
                  setPrefs({ style: sel })
                  onClose()
                }}
              >
                {t('使用')}
              </Btn>
            </DialogActions>
          </>
        )}
      </div>
    </div>
  )
}
