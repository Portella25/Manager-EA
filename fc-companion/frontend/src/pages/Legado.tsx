import { useEffect, useRef, useState, useCallback } from 'react'
import { Trophy, Swords, Users, Shield, Target, BarChart3, Star, ChevronRight, Crosshair, Upload, ZoomIn, ZoomOut, Move } from 'lucide-react'
import { useGameStore } from '../store/useGameStore'
import { uploadTrophyImage, uploadClubImage, fetchUploadsList } from '../lib/api'

type LegacyCard = {
  card_id: string
  type: string
  title: string
  value?: string
  subtitle?: string
  meta?: Record<string, unknown>
}

type ClubHistory = {
  club_name: string
  games: number
  wins: number
  draws: number
  losses: number
  aproveitamento_pct: number
}

type Trophies = {
  league: number
  domestic_cup: number
  continental: number
  total: number
}

type ImageTransform = { scale: number; x: number; y: number }

const TRANSFORM_DEFAULTS: ImageTransform = { scale: 1, x: 0, y: 0 }

function loadTransform(storageKey: string): ImageTransform {
  try {
    const raw = localStorage.getItem(`img_transform_${storageKey}`)
    if (raw) return { ...TRANSFORM_DEFAULTS, ...JSON.parse(raw) }
  } catch {}
  return { ...TRANSFORM_DEFAULTS }
}

function saveTransform(storageKey: string, t: ImageTransform) {
  try {
    localStorage.setItem(`img_transform_${storageKey}`, JSON.stringify(t))
  } catch {}
}

/**
 * Moldura com imagem redimensionável (scroll/pinch) e arrastável.
 * O ajuste fica salvo no localStorage por storageKey.
 */
function ImageFrame({
  src,
  alt,
  storageKey,
  className = '',
  placeholderIcon,
}: {
  src?: string
  alt: string
  storageKey: string
  className?: string
  placeholderIcon?: React.ReactNode
}) {
  const [transform, setTransform] = useState<ImageTransform>(() => loadTransform(storageKey))
  const [dragging, setDragging] = useState(false)
  const [adjusting, setAdjusting] = useState(false)
  const dragStart = useRef<{ mx: number; my: number; tx: number; ty: number } | null>(null)
  const lastPinchDist = useRef<number | null>(null)
  const frameRef = useRef<HTMLDivElement>(null)

  // Recarrega transform quando storageKey muda (ex: imagem nova uploadada)
  useEffect(() => {
    setTransform(loadTransform(storageKey))
  }, [storageKey])

  const applyTransform = useCallback((updater: (prev: ImageTransform) => ImageTransform) => {
    setTransform((prev) => {
      const next = updater(prev)
      saveTransform(storageKey, next)
      return next
    })
  }, [storageKey])

  // ── Scroll / wheel para zoom ──────────────────────────────────────────────
  function onWheel(e: React.WheelEvent) {
    if (!adjusting) return
    e.preventDefault()
    const delta = e.deltaY < 0 ? 0.1 : -0.1
    applyTransform((prev) => ({ ...prev, scale: Math.min(5, Math.max(0.2, prev.scale + delta)) }))
  }

  // ── Mouse drag ────────────────────────────────────────────────────────────
  function onMouseDown(e: React.MouseEvent) {
    if (!adjusting) return
    e.preventDefault()
    setDragging(true)
    dragStart.current = { mx: e.clientX, my: e.clientY, tx: transform.x, ty: transform.y }
  }

  function onMouseMove(e: React.MouseEvent) {
    if (!dragging || !dragStart.current) return
    const dx = e.clientX - dragStart.current.mx
    const dy = e.clientY - dragStart.current.my
    applyTransform((prev) => ({ ...prev, x: dragStart.current!.tx + dx, y: dragStart.current!.ty + dy }))
  }

  function onMouseUp() {
    setDragging(false)
    dragStart.current = null
  }

  // ── Touch pinch + drag ────────────────────────────────────────────────────
  function onTouchStart(e: React.TouchEvent) {
    if (!adjusting) return
    if (e.touches.length === 2) {
      const dx = e.touches[0].clientX - e.touches[1].clientX
      const dy = e.touches[0].clientY - e.touches[1].clientY
      lastPinchDist.current = Math.hypot(dx, dy)
    } else if (e.touches.length === 1) {
      dragStart.current = {
        mx: e.touches[0].clientX,
        my: e.touches[0].clientY,
        tx: transform.x,
        ty: transform.y,
      }
    }
  }

  function onTouchMove(e: React.TouchEvent) {
    if (!adjusting) return
    e.preventDefault()
    if (e.touches.length === 2 && lastPinchDist.current !== null) {
      const dx = e.touches[0].clientX - e.touches[1].clientX
      const dy = e.touches[0].clientY - e.touches[1].clientY
      const dist = Math.hypot(dx, dy)
      const ratio = dist / lastPinchDist.current
      lastPinchDist.current = dist
      applyTransform((prev) => ({ ...prev, scale: Math.min(5, Math.max(0.2, prev.scale * ratio)) }))
    } else if (e.touches.length === 1 && dragStart.current) {
      const ddx = e.touches[0].clientX - dragStart.current.mx
      const ddy = e.touches[0].clientY - dragStart.current.my
      applyTransform((prev) => ({ ...prev, x: dragStart.current!.tx + ddx, y: dragStart.current!.ty + ddy }))
    }
  }

  function onTouchEnd(e: React.TouchEvent) {
    if (e.touches.length < 2) lastPinchDist.current = null
    if (e.touches.length === 0) dragStart.current = null
  }

  function resetTransform() {
    const t = TRANSFORM_DEFAULTS
    setTransform(t)
    saveTransform(storageKey, t)
  }

  if (!src) {
    return (
      <div className={`flex items-center justify-center bg-black/20 ${className}`}>
        {placeholderIcon}
      </div>
    )
  }

  return (
    <div className={`relative group/frame ${className}`}>
      {/* Moldura com overflow hidden */}
      <div
        ref={frameRef}
        className={`w-full h-full overflow-hidden rounded-inherit ${adjusting ? (dragging ? 'cursor-grabbing' : 'cursor-grab') : 'cursor-default'}`}
        onWheel={onWheel}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onMouseLeave={onMouseUp}
        onTouchStart={onTouchStart}
        onTouchMove={onTouchMove}
        onTouchEnd={onTouchEnd}
        style={{ touchAction: adjusting ? 'none' : 'auto' }}
      >
        <img
          src={src}
          alt={alt}
          draggable={false}
          className="w-full h-full object-contain select-none pointer-events-none"
          style={{
            transform: `translate(${transform.x}px, ${transform.y}px) scale(${transform.scale})`,
            transformOrigin: 'center center',
            transition: dragging ? 'none' : 'transform 0.05s',
          }}
        />
      </div>

      {/* Barra de controles — aparece ao hover */}
      <div className="absolute bottom-1 left-1/2 -translate-x-1/2 flex items-center gap-1 opacity-0 group-hover/frame:opacity-100 transition-opacity z-10">
        <button
          type="button"
          title={adjusting ? 'Finalizar ajuste' : 'Ajustar imagem'}
          onClick={() => setAdjusting((v) => !v)}
          className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wide shadow ${adjusting ? 'bg-semantic-gold text-black' : 'bg-black/70 text-white hover:bg-white/20'}`}
        >
          <Move className="w-3 h-3" />
          {adjusting ? 'ok' : 'ajustar'}
        </button>
        {adjusting && (
          <>
            <button
              type="button"
              title="Zoom +"
              onClick={() => applyTransform((p) => ({ ...p, scale: Math.min(5, p.scale + 0.15) }))}
              className="p-1 rounded-full bg-black/70 text-white hover:bg-white/20"
            >
              <ZoomIn className="w-3 h-3" />
            </button>
            <button
              type="button"
              title="Zoom -"
              onClick={() => applyTransform((p) => ({ ...p, scale: Math.max(0.2, p.scale - 0.15) }))}
              className="p-1 rounded-full bg-black/70 text-white hover:bg-white/20"
            >
              <ZoomOut className="w-3 h-3" />
            </button>
            <button
              type="button"
              title="Resetar"
              onClick={resetTransform}
              className="px-2 py-0.5 rounded-full bg-black/70 text-white hover:bg-white/20 text-[10px] font-bold uppercase"
            >
              reset
            </button>
          </>
        )}
      </div>
    </div>
  )
}

function formatOccuredAt(meta?: Record<string, unknown>) {
  const raw = (meta?.date_raw as unknown) || (meta?.occurred_at as unknown)
  if (!raw) return null
  const s = String(raw)
  return s.length > 10 ? s.slice(0, 10) : s
}

function StatBox({ label, value, sub, accent }: { label: string; value: string | number; sub?: string; accent?: string }) {
  return (
    <div className="text-center">
      <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary mb-1">{label}</p>
      <p className={`text-2xl font-condensed font-bold leading-none ${accent || 'text-white'}`}>{value}</p>
      {sub && <p className="text-[10px] text-text-secondary mt-1">{sub}</p>}
    </div>
  )
}

function MoraleBar({ label, value, max = 100 }: { label: string; value: number | null; max?: number }) {
  const pct = value != null ? Math.min(100, Math.max(0, (value / max) * 100)) : 0
  const color = pct >= 70 ? 'bg-semantic-green' : pct >= 40 ? 'bg-semantic-gold' : 'bg-semantic-red'
  return (
    <div>
      <div className="flex justify-between items-center mb-1">
        <p className="text-xs text-text-secondary">{label}</p>
        <p className="text-xs font-bold text-white">{value != null ? `${Math.round(pct)}%` : '--'}</p>
      </div>
      <div className="w-full h-1.5 rounded-full bg-white/10">
        <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

function UploadImageButton({
  onUploaded,
  accept = 'image/*',
  children,
  className = '',
}: {
  onUploaded: (file: File) => Promise<void>
  accept?: string
  children: React.ReactNode
  className?: string
}) {
  const ref = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)

  async function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      await onUploaded(file)
    } finally {
      setUploading(false)
      if (ref.current) ref.current.value = ''
    }
  }

  return (
    <>
      <input ref={ref} type="file" accept={accept} className="hidden" onChange={handleChange} />
      <button
        type="button"
        disabled={uploading}
        onClick={() => ref.current?.click()}
        className={className}
      >
        {uploading ? <span className="opacity-60">...</span> : children}
      </button>
    </>
  )
}

function TrophyCard({
  trophyKey,
  label,
  index,
  imageUrl,
  onImageUploaded,
}: {
  trophyKey: string
  label: string
  index: number
  imageUrl?: string
  onImageUploaded: (key: string, url: string) => void
}) {
  async function handleUpload(file: File) {
    const result = await uploadTrophyImage(trophyKey, file)
    onImageUploaded(trophyKey, result.url)
  }

  return (
    <div className="card-base p-4 text-center border-semantic-gold/20 bg-gradient-to-b from-semantic-gold/5 to-transparent relative group">
      <div className="w-24 h-24 mx-auto mb-2 rounded-xl overflow-hidden bg-black/20">
        <ImageFrame
          src={imageUrl}
          alt={label}
          storageKey={`trophy_${trophyKey}`}
          className="w-full h-full"
          placeholderIcon={<Trophy className="w-10 h-10 text-semantic-gold/50" />}
        />
      </div>
      <p className="text-sm font-bold text-white">{label}</p>
      <p className="text-[10px] text-text-secondary mt-1">#{index + 1}</p>
      {/* Botão de upload — só aparece quando não está em modo ajuste */}
      <UploadImageButton
        onUploaded={handleUpload}
        className="absolute top-2 right-2 p-1.5 rounded-full bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity hover:bg-white/20 cursor-pointer z-20"
      >
        <Upload className="w-3.5 h-3.5 text-white" />
      </UploadImageButton>
    </div>
  )
}

function TrophyShelf({
  trophies,
  imagesMap,
  onImageUploaded,
}: {
  trophies: Trophies
  imagesMap: Record<string, string>
  onImageUploaded: (key: string, url: string) => void
}) {
  type TrophyItem = { label: string; count: number; prefix: string }
  const items: TrophyItem[] = []
  if (trophies.league > 0) items.push({ label: 'Liga', count: trophies.league, prefix: 'league' })
  if (trophies.domestic_cup > 0) items.push({ label: 'Copa Nacional', count: trophies.domestic_cup, prefix: 'domestic_cup' })
  if (trophies.continental > 0) items.push({ label: 'Continental', count: trophies.continental, prefix: 'continental' })

  if (items.length === 0) {
    return (
      <div className="card-base p-6 text-center border-dashed border-white/20">
        <Trophy className="w-12 h-12 text-text-secondary/30 mx-auto mb-3" />
        <p className="text-sm text-text-secondary">Nenhum troféu conquistado ainda.</p>
        <p className="text-xs text-text-secondary/60 mt-1">Continue vencendo para preencher a sala de troféus.</p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
      {items.flatMap((item) =>
        Array.from({ length: item.count }).map((_, i) => {
          const key = `${item.prefix}_${i + 1}`
          return (
            <TrophyCard
              key={key}
              trophyKey={key}
              label={item.label}
              index={i}
              imageUrl={imagesMap[key]}
              onImageUploaded={onImageUploaded}
            />
          )
        })
      )}
    </div>
  )
}

function safeKey(name: string): string {
  return name.replace(/[^\w\-.]/g, '_').slice(0, 120)
}

function buildImageMap(urls: string[]): Record<string, string> {
  const map: Record<string, string> = {}
  for (const url of urls) {
    const filename = url.split('/').pop() || ''
    // remove extensão: domestic_cup_1.png → domestic_cup_1
    const key = filename.replace(/\.[^.]+$/, '')
    map[key] = url
  }
  return map
}

export function Legado() {
  const { data, loading } = useGameStore()
  const [selectedCard, setSelectedCard] = useState<LegacyCard | null>(null)
  const [trophyImages, setTrophyImages] = useState<Record<string, string>>({})
  const [clubImages, setClubImages] = useState<Record<string, string>>({})

  useEffect(() => {
    fetchUploadsList().then((res) => {
      setTrophyImages(buildImageMap(res.trophies))
      setClubImages(buildImageMap(res.clubs))
    }).catch(() => {})
  }, [])

  function handleTrophyImageUploaded(key: string, url: string) {
    // Extrai só o filename sem extensão para usar como chave no mapa
    const filename = url.split('/').pop() || ''
    const mapKey = filename.replace(/\.[^.]+$/, '')
    setTrophyImages((prev) => ({ ...prev, [mapKey]: url + `?t=${Date.now()}` }))
  }

  function handleClubImageUploaded(clubName: string, url: string) {
    const filename = url.split('/').pop() || ''
    const mapKey = filename.replace(/\.[^.]+$/, '')
    setClubImages((prev) => ({ ...prev, [mapKey]: url + `?t=${Date.now()}` }))
  }

  const legacyHub = data?.legacy_hub as any || {}
  const aproveitamento = legacyHub?.aproveitamento || {}
  const managerProfile = legacyHub?.manager_profile || {}
  const clubsHistory: ClubHistory[] = Array.isArray(legacyHub?.clubs_history) ? legacyHub.clubs_history : []
  const currentClubStats = legacyHub?.current_club_stats || null
  const morale = legacyHub?.manager_morale || {}
  const records = legacyHub?.records || {}
  const streaks = legacyHub?.streaks || {}
  const legacyCards: LegacyCard[] = Array.isArray(legacyHub?.cards) ? legacyHub.cards : []
  const trophies: Trophies = managerProfile.trophies || { league: 0, domestic_cup: 0, continental: 0, total: 0 }

  if (loading && !data) {
    return <div className="text-center text-text-secondary mt-10">Carregando legado...</div>
  }

  const totalGames = managerProfile.total_games || aproveitamento.games || 0
  const totalWins = managerProfile.total_wins || aproveitamento.wins || 0
  const totalDraws = managerProfile.total_draws || aproveitamento.draws || 0
  const totalLosses = managerProfile.total_losses || aproveitamento.losses || 0
  const pct = managerProfile.aproveitamento_pct || aproveitamento.pct || 0
  const seasons = managerProfile.seasons || 1
  const clubsCount = managerProfile.clubs_managed_count || 1
  const currentClub = managerProfile.current_club || 'Clube'
  const favoriteFormation = managerProfile.favorite_formation || '--'
  const goalsFor = managerProfile.goals_for || 0
  const goalsAgainst = managerProfile.goals_against || 0
  const biggestBuy = managerProfile.biggest_buy || null
  const biggestSell = managerProfile.biggest_sell || null

  const longestStreak = streaks?.longest_win_streak?.count || 0
  const currentStreak = streaks?.current_win_streak?.count || 0
  const biggestWin = records?.biggest_win
  const worstLoss = records?.worst_loss

  return (
    <div className="space-y-6 pb-6">

      <div className="flex justify-between items-center">
        <h2 className="font-condensed font-bold text-2xl text-white uppercase">Hall da Fama</h2>
        {trophies.total > 0 && (
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-semantic-gold/15 border border-semantic-gold/25">
            <Trophy className="w-3.5 h-3.5 text-semantic-gold" />
            <span className="text-xs font-bold text-semantic-gold">{trophies.total}</span>
          </div>
        )}
      </div>

      {/* PERFIL DO TREINADOR */}
      <section className="card-base p-5 bg-gradient-to-br from-semantic-gold/10 to-transparent border-semantic-gold/25">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-12 h-12 rounded-xl bg-semantic-gold/20 border border-semantic-gold/30 flex items-center justify-center">
            <Shield className="w-6 h-6 text-semantic-gold" />
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-[0.2em] text-semantic-gold font-bold">Treinador</p>
            <h3 className="font-condensed font-bold text-xl text-white uppercase">{currentClub}</h3>
          </div>
        </div>

        <div className="grid grid-cols-4 gap-4 mt-4">
          <StatBox label="Temporadas" value={seasons} />
          <StatBox label="Jogos" value={totalGames} />
          <StatBox label="Clubes" value={clubsCount} />
          <StatBox label="Aproveit." value={`${pct.toFixed(1)}%`} accent="text-semantic-gold" />
        </div>

        <div className="grid grid-cols-3 gap-3 mt-4 pt-4 border-t border-white/10">
          <div className="text-center">
            <p className="text-xl font-condensed font-bold text-semantic-green">{totalWins}</p>
            <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">Vitórias</p>
          </div>
          <div className="text-center">
            <p className="text-xl font-condensed font-bold text-semantic-gold">{totalDraws}</p>
            <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">Empates</p>
          </div>
          <div className="text-center">
            <p className="text-xl font-condensed font-bold text-semantic-red">{totalLosses}</p>
            <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">Derrotas</p>
          </div>
        </div>

        {(goalsFor > 0 && goalsFor < 10000) && (
          <div className="flex justify-center gap-8 mt-3 pt-3 border-t border-white/5">
            <div className="text-center">
              <p className="text-sm font-condensed font-bold text-white">{goalsFor}</p>
              <p className="text-[9px] text-text-secondary uppercase">Gols Pró</p>
            </div>
            <div className="text-center">
              <p className="text-sm font-condensed font-bold text-white">{goalsAgainst}</p>
              <p className="text-[9px] text-text-secondary uppercase">Gols Contra</p>
            </div>
            <div className="text-center">
              <p className={`text-sm font-condensed font-bold ${goalsFor - goalsAgainst >= 0 ? 'text-semantic-green' : 'text-semantic-red'}`}>
                {goalsFor - goalsAgainst >= 0 ? '+' : ''}{goalsFor - goalsAgainst}
              </p>
              <p className="text-[9px] text-text-secondary uppercase">Saldo</p>
            </div>
          </div>
        )}
      </section>

      {/* TÁTICA E IDENTIDADE */}
      <section className="card-base p-5">
        <div className="flex items-center gap-2 mb-4">
          <Crosshair className="w-5 h-5 text-semantic-gold" />
          <h3 className="font-condensed font-bold text-lg text-white uppercase">Identidade Tática</h3>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary mb-1">Formação favorita</p>
            <p className="text-lg font-condensed font-bold text-white">{favoriteFormation}</p>
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary mb-1">Troféus</p>
            <p className="text-lg font-condensed font-bold text-semantic-gold">{trophies.total}</p>
          </div>
        </div>
        {(biggestBuy || biggestSell) && (
          <div className="grid grid-cols-2 gap-4 mt-4 pt-3 border-t border-white/10">
            {biggestBuy && (
              <div>
                <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary mb-1">Maior contratação</p>
                <p className="text-sm font-bold text-white">{biggestBuy}</p>
              </div>
            )}
            {biggestSell && (
              <div>
                <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary mb-1">Maior venda</p>
                <p className="text-sm font-bold text-white">{biggestSell}</p>
              </div>
            )}
          </div>
        )}
      </section>

      {/* SALA DE TROFÉUS */}
      <section className="space-y-3">
        <div className="flex items-center gap-2">
          <Trophy className="w-5 h-5 text-semantic-gold" />
          <h3 className="font-condensed font-bold text-lg text-white uppercase">Sala de Troféus</h3>
        </div>
        <TrophyShelf
          trophies={trophies}
          imagesMap={trophyImages}
          onImageUploaded={handleTrophyImageUploaded}
        />
      </section>

      {/* CLUBE ATUAL */}
      {currentClubStats && (
        <section className="card-base p-5">
          <div className="flex items-center gap-2 mb-4">
            <Target className="w-5 h-5 text-semantic-gold" />
            <h3 className="font-condensed font-bold text-lg text-white uppercase">No {currentClub}</h3>
          </div>
          <div className="grid grid-cols-4 gap-3">
            <StatBox label="Jogos" value={currentClubStats.games || 0} />
            <StatBox label="Vitórias" value={currentClubStats.wins || 0} />
            <StatBox label="Empates" value={currentClubStats.draws || 0} />
            <StatBox label="Derrotas" value={currentClubStats.losses || 0} />
          </div>
          <div className="mt-4 pt-3 border-t border-white/10 flex items-center justify-between">
            <p className="text-xs text-text-secondary">Aproveitamento no clube</p>
            <p className="text-lg font-condensed font-bold text-white">
              {typeof currentClubStats.pct === 'number' ? `${currentClubStats.pct.toFixed(1)}%` : '--'}
            </p>
          </div>
        </section>
      )}

      {/* RECORDES */}
      <section className="space-y-3">
        <div className="flex items-center gap-2">
          <Swords className="w-5 h-5 text-semantic-gold" />
          <h3 className="font-condensed font-bold text-lg text-white uppercase">Recordes</h3>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="card-base p-4">
            <p className="text-[10px] uppercase tracking-[0.2em] text-semantic-green font-bold mb-2">Maior Vitória</p>
            {biggestWin ? (
              <>
                <p className="text-2xl font-condensed font-bold text-white">{biggestWin.scoreline}</p>
                <p className="text-xs text-text-secondary mt-1">vs {biggestWin.opponent_name || '--'}</p>
                {biggestWin.competition_name && (
                  <p className="text-[10px] text-text-secondary/60 mt-1">{biggestWin.competition_name}</p>
                )}
              </>
            ) : (
              <p className="text-sm text-text-secondary">--</p>
            )}
          </div>
          <div className="card-base p-4">
            <p className="text-[10px] uppercase tracking-[0.2em] text-semantic-red font-bold mb-2">Pior Derrota</p>
            {worstLoss ? (
              <>
                <p className="text-2xl font-condensed font-bold text-white">{worstLoss.scoreline}</p>
                <p className="text-xs text-text-secondary mt-1">vs {worstLoss.opponent_name || '--'}</p>
                {worstLoss.competition_name && (
                  <p className="text-[10px] text-text-secondary/60 mt-1">{worstLoss.competition_name}</p>
                )}
              </>
            ) : (
              <p className="text-sm text-text-secondary">--</p>
            )}
          </div>
          <div className="card-base p-4">
            <p className="text-[10px] uppercase tracking-[0.2em] text-semantic-gold font-bold mb-2">Maior Sequência</p>
            <p className="text-2xl font-condensed font-bold text-white">{longestStreak}</p>
            <p className="text-xs text-text-secondary mt-1">vitórias seguidas</p>
          </div>
          <div className="card-base p-4">
            <p className="text-[10px] uppercase tracking-[0.2em] text-cyan-400 font-bold mb-2">Sequência Atual</p>
            <p className="text-2xl font-condensed font-bold text-white">{currentStreak}</p>
            <p className="text-xs text-text-secondary mt-1">vitórias seguidas</p>
          </div>
        </div>
      </section>

      {/* MORAL DO TREINADOR */}
      <section className="card-base p-5">
        <div className="flex items-center gap-2 mb-4">
          <BarChart3 className="w-5 h-5 text-semantic-gold" />
          <h3 className="font-condensed font-bold text-lg text-white uppercase">Moral e Ambiente</h3>
        </div>
        <div className="space-y-3">
          <MoraleBar label="Coesão do elenco" value={morale.cohesion} />
          <MoraleBar label="Estabilidade tática" value={morale.tactical_stability} />
          <div className="flex justify-between items-center pt-2 border-t border-white/10">
            <p className="text-xs text-text-secondary">Jogadores com moral baixa</p>
            <p className={`text-sm font-bold ${morale.low_morale_count > 2 ? 'text-semantic-red' : morale.low_morale_count > 0 ? 'text-semantic-gold' : 'text-semantic-green'}`}>
              {morale.low_morale_count ?? '--'}
            </p>
          </div>
        </div>
      </section>

      {/* CLUBES QUE PASSOU */}
      {clubsHistory.length > 0 && (
        <section className="space-y-3">
          <div className="flex items-center gap-2">
            <Users className="w-5 h-5 text-semantic-gold" />
            <h3 className="font-condensed font-bold text-lg text-white uppercase">Clubes da Carreira</h3>
          </div>
          <div className="space-y-2">
            {clubsHistory.map((club) => {
              const clubKey = club.club_name.replace(/[^\w\-.]/g, '_').slice(0, 120)
              const clubImageUrl = clubImages[clubKey]
              return (
                <div key={club.club_name} className={`card-base p-4 flex items-center justify-between ${club.club_name === currentClub ? 'border-semantic-gold/30' : ''}`}>
                  <div className="flex items-center gap-3">
                    <div className="relative flex-shrink-0 group/club">
                      <div className="w-10 h-10 rounded-lg bg-white/5 border border-white/10 overflow-hidden">
                        <ImageFrame
                          src={clubImageUrl}
                          alt={club.club_name}
                          storageKey={`club_${clubKey}`}
                          className="w-full h-full"
                          placeholderIcon={<Shield className="w-4 h-4 text-text-secondary" />}
                        />
                      </div>
                      <UploadImageButton
                        onUploaded={async (file) => {
                          const result = await uploadClubImage(club.club_name, file)
                          handleClubImageUploaded(club.club_name, result.url)
                        }}
                        className="absolute -top-1 -right-1 p-0.5 rounded-full bg-black/80 opacity-0 group-hover/club:opacity-100 transition-opacity hover:bg-white/20 cursor-pointer z-20"
                      >
                        <Upload className="w-2.5 h-2.5 text-white" />
                      </UploadImageButton>
                    </div>
                    <div>
                      <p className="text-sm font-bold text-white">{club.club_name}</p>
                      <p className="text-[10px] text-text-secondary">{club.games} jogos · {club.wins}V {club.draws}E {club.losses}D</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-condensed font-bold text-white">{club.aproveitamento_pct.toFixed(1)}%</p>
                    {club.club_name === currentClub && (
                      <p className="text-[9px] uppercase tracking-wide text-semantic-gold">Atual</p>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </section>
      )}

      {/* MARCOS ADICIONAIS */}
      {legacyCards.length > 0 && (
        <section className="space-y-3">
          <div className="flex items-center gap-2">
            <Star className="w-5 h-5 text-semantic-gold" />
            <h3 className="font-condensed font-bold text-lg text-white uppercase">Marcos da Carreira</h3>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {legacyCards.map((card) => (
              <button
                key={card.card_id}
                type="button"
                onClick={() => setSelectedCard(card)}
                className="card-base p-4 text-left w-full hover:bg-white/5 transition"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">{card.type}</p>
                    <h4 className="text-sm font-bold text-white mt-1">{card.title}</h4>
                    <p className="text-lg font-condensed font-bold text-white mt-1">{card.value || '--'}</p>
                    {card.subtitle && <p className="text-xs text-text-secondary mt-1">{card.subtitle}</p>}
                  </div>
                  <ChevronRight className="w-4 h-4 text-text-secondary" />
                </div>
              </button>
            ))}
          </div>
        </section>
      )}

      {/* MODAL DE DETALHE */}
      {selectedCard && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-end sm:items-center justify-center p-4" role="dialog" aria-modal="true">
          <div className="w-full sm:max-w-lg rounded-2xl border border-white/10 bg-[#0a140d] p-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-[10px] uppercase tracking-[0.2em] text-text-secondary">{selectedCard.type}</p>
                <h4 className="text-lg font-bold text-white mt-2">{selectedCard.title}</h4>
              </div>
              <button type="button" onClick={() => setSelectedCard(null)} className="text-xs font-bold text-text-secondary uppercase tracking-wide">Fechar</button>
            </div>
            <div className="mt-4 rounded-xl border border-white/10 bg-black/20 p-4">
              <p className="text-3xl font-condensed font-bold text-white">{selectedCard.value || '--'}</p>
              {selectedCard.subtitle && <p className="text-sm text-text-secondary mt-2 leading-relaxed">{selectedCard.subtitle}</p>}
              {(selectedCard?.meta?.competition_name || selectedCard?.meta?.date_raw) && (
                <p className="text-[11px] uppercase tracking-[0.2em] text-text-secondary mt-3">
                  {[selectedCard?.meta?.competition_name, formatOccuredAt(selectedCard.meta)].filter(Boolean).join(' · ')}
                </p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
