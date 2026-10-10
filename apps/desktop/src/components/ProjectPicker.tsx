import { Check, ChevronLeft, FolderMinus } from 'lucide-react'
import { MenuDivider, MenuItem } from './Popover'
import { t } from '../lib/i18n'

/** “加入项目”子菜单：标题下拉与侧栏菜单共用 */
export function ProjectPicker({
  menu,
  onBack,
  onDone,
}: {
  menu: { projects: { id: string; name: string }[]; projectId: string | null; onProject: (id: string | null) => void }
  onBack: () => void
  onDone: () => void
}) {
  return (
    <div data-testid="project-picker">
      <button type="button" className="menu-item text-sepia" onClick={onBack}>
        <ChevronLeft size={14} strokeWidth={1.6} />
        <span>{t('加入项目')}</span>
      </button>
      <MenuDivider />
      {menu.projects.length === 0 && <p className="px-3 py-2 text-[12px] text-sepia-muted">{t('还没有项目：在侧栏“项目”里新建')}</p>}
      {menu.projects.map((p) => (
        <button
          key={p.id}
          type="button"
          role="menuitemradio"
          aria-checked={menu.projectId === p.id}
          data-testid="project-option"
          className="menu-item"
          onClick={() => {
            menu.onProject(p.id)
            onDone()
          }}
        >
          <span className="w-[14px]">{menu.projectId === p.id && <Check size={13} strokeWidth={2} className="text-amber" />}</span>
          <span className="truncate">{p.name}</span>
        </button>
      ))}
      {menu.projectId && (
        <>
          <MenuDivider />
          <MenuItem icon={FolderMinus} label={t('移出项目')} onClick={() => (menu.onProject(null), onDone())} />
        </>
      )}
    </div>
  )
}

