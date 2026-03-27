interface SectionHeaderProps {
  title: string
  subtitle?: string
  actionLabel?: string
  onAction?: () => void
}

export function SectionHeader({ title, subtitle, actionLabel, onAction }: SectionHeaderProps) {
  return (
    <div className="flex justify-between items-start gap-3">
      <div>
        <h3 className="font-condensed font-bold text-white uppercase tracking-wide">{title}</h3>
        {subtitle ? <p className="text-xs text-text-secondary mt-1">{subtitle}</p> : null}
      </div>
      {actionLabel && onAction ? (
        <button onClick={onAction} className="text-semantic-gold text-xs font-bold hover:underline whitespace-nowrap">
          {actionLabel}
        </button>
      ) : null}
    </div>
  )
}
