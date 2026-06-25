import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import TopBar from './TopBar'

const titles: Record<string, string> = {
  '/': 'Live Feed',
  '/identity': 'Identity Explorer',
  '/profiles': 'User Profiles',
  '/ads': 'Ad Studio',
  '/analytics': 'Analytics',
}

export default function Layout() {
  const path = window.location.pathname
  const title = titles[path] || 'Dashboard'

  return (
    <div className="flex h-screen overflow-hidden bg-cdp-bg">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <TopBar title={title} />
        <main className="flex-1 overflow-y-auto bg-slate-50/50 p-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
