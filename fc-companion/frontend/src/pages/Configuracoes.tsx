import { useRef } from 'react'
import { useAppStore } from '../store'
import { Upload, Trash2, Bell } from 'lucide-react'

export function Configuracoes() {
  const { 
    customBackground, 
    setCustomBackground,
    notificationsEnabled,
    setNotificationsEnabled
  } = useAppStore()
  
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      const reader = new FileReader()
      reader.onloadend = () => {
        setCustomBackground(reader.result as string)
      }
      reader.readAsDataURL(file)
    }
  }

  const handleRemoveBackground = () => {
    setCustomBackground(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="font-condensed font-bold text-2xl text-white uppercase mb-6">Configurações</h2>

      <section className="card-base p-4">
        <h3 className="font-bold text-white mb-4 flex items-center">
          <Upload className="w-5 h-5 mr-2 text-semantic-gold" />
          Fundo Personalizado
        </h3>
        
        <p className="text-sm text-text-secondary mb-4">
          Faça upload de uma imagem do seu time ou estádio para personalizar o fundo do app.
        </p>

        <div className="space-y-4">
          {customBackground && (
            <div className="relative w-full h-32 rounded-lg overflow-hidden border border-white/10">
              <img 
                src={customBackground} 
                alt="Fundo atual" 
                className="w-full h-full object-cover"
              />
              <button 
                onClick={handleRemoveBackground}
                className="absolute top-2 right-2 p-2 bg-semantic-red/80 hover:bg-semantic-red text-white rounded-full transition-colors"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          )}

          <input 
            type="file" 
            accept="image/*" 
            onChange={handleImageUpload}
            ref={fileInputRef}
            className="hidden" 
          />
          
          <button 
            onClick={() => fileInputRef.current?.click()}
            className="w-full py-3 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg text-sm font-bold text-white transition-colors"
          >
            {customBackground ? 'Trocar Imagem' : 'Escolher Imagem'}
          </button>
        </div>
      </section>

      <section className="card-base p-4">
        <h3 className="font-bold text-white mb-4 flex items-center">
          <Bell className="w-5 h-5 mr-2 text-semantic-gold" />
          Notificações
        </h3>
        
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-bold text-white">Alertas em tempo real</p>
            <p className="text-xs text-text-secondary">Seja avisado sobre eventos importantes</p>
          </div>
          
          <button 
            onClick={() => setNotificationsEnabled(!notificationsEnabled)}
            className={`w-12 h-6 rounded-full transition-colors relative ${notificationsEnabled ? 'bg-semantic-green' : 'bg-white/20'}`}
          >
            <div className={`w-5 h-5 bg-white rounded-full absolute top-0.5 transition-transform ${notificationsEnabled ? 'left-6' : 'left-0.5'}`} />
          </button>
        </div>
      </section>
    </div>
  )
}
