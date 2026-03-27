interface SignalRadarCardProps {
  label: string
  value: number | string
  subtitle?: string
  tone?: 'positive' | 'warning' | 'danger' | 'neutral'
}

function toneClasses(tone: SignalRadarCardProps['tone']) {
  if (tone === 'positive') return 'text-semantic-green border-semantic-green/20 bg-semantic-green/10'
  if (tone === 'warning') return 'text-semantic-gold border-semantic-gold/20 bg-semantic-gold/10'
  if (tone === 'danger') return 'text-semantic-red border-semantic-red/20 bg-semantic-red/10'
  return 'text-white border-white/10 bg-white/5'
}

export function SignalRadarCard({ label, value, subtitle, tone = 'neutral' }: SignalRadarCardProps) {
  return (
    <div className={`rounded-2xl border p-4 ${toneClasses(tone)}`}>
      <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary mb-2">{label}</p>
      <p className="text-2xl font-condensed font-bold">{value}</p>
      {subtitle ? <p className="text-xs text-text-secondary mt-2">{subtitle}</p> : null}
    </div>
  )
}
