import { NavLink } from 'react-router-dom'
import { Home, Users, Briefcase, BookOpen, ArrowRightLeft, MessageSquare, Wallet } from 'lucide-react'
import { cn } from '../lib/utils'

const navItems = [
  { path: '/', label: 'HOME', icon: Home },
  { path: '/plantel', label: 'PLANTEL', icon: Users },
  { path: '/mercado', label: 'MERCADO', icon: ArrowRightLeft },
  { path: '/social', label: 'SOCIAL', icon: MessageSquare },
  { path: '/financas', label: 'FINANÇAS', icon: Wallet },
  { path: '/carreira', label: 'CARREIRA', icon: Briefcase },
  { path: '/legado', label: 'LEGADO', icon: BookOpen },
]

export function BottomNav() {
  return (
    <nav className="fixed bottom-0 left-0 right-0 bg-[#0a140d]/95 backdrop-blur-md border-t border-white/10 pb-safe z-50">
      <div className="flex justify-around items-center h-16 px-2">
        {navItems.map(({ path, label, icon: Icon }) => (
          <NavLink
            key={path}
            to={path}
            className={({ isActive }) =>
              cn(
                "flex flex-col items-center justify-center w-full h-full space-y-1 transition-colors",
                isActive ? "text-semantic-gold" : "text-text-secondary hover:text-white"
              )
            }
          >
            {({ isActive }) => (
              <>
                <Icon className={cn("w-6 h-6", isActive ? "animate-pulse" : "")} />
                <span className="text-[10px] font-condensed font-bold tracking-wider">
                  {label}
                </span>
                {isActive && (
                  <div className="absolute top-0 w-8 h-[2px] bg-semantic-gold rounded-b-full" />
                )}
              </>
            )}
          </NavLink>
        ))}
      </div>
    </nav>
  )
}
