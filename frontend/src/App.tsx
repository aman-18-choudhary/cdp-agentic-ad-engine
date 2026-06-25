import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from '@/components/layout/Layout'

const LiveFeed = lazy(() => import('@/pages/LiveFeed'))
const IdentityExplorer = lazy(() => import('@/pages/IdentityExplorer'))
const UserProfiles = lazy(() => import('@/pages/UserProfiles'))
const AdStudio = lazy(() => import('@/pages/AdStudio'))
const Analytics = lazy(() => import('@/pages/Analytics'))

function PageLoader() {
  return (
    <div className="space-y-4 p-8">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="bg-white border border-cdp-border rounded-xl p-5 shadow-card animate-pulse">
            <div className="h-3 w-16 bg-slate-200 rounded mb-3" />
            <div className="h-6 w-24 bg-slate-200 rounded" />
          </div>
        ))}
      </div>
      <div className="bg-white border border-cdp-border rounded-xl p-6 shadow-card animate-pulse">
        <div className="h-3 w-32 bg-slate-200 rounded mb-4" />
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="flex gap-4">
              <div className="h-4 w-16 bg-slate-200 rounded" />
              <div className="h-4 w-12 bg-slate-200 rounded" />
              <div className="h-4 w-12 bg-slate-200 rounded" />
              <div className="h-4 w-20 bg-slate-200 rounded" />
              <div className="h-4 flex-1 bg-slate-200 rounded" />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<LiveFeed />} />
          <Route path="/identity" element={<IdentityExplorer />} />
          <Route path="/profiles" element={<UserProfiles />} />
          <Route path="/ads" element={<AdStudio />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </Suspense>
  )
}
