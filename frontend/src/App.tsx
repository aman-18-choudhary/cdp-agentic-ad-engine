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
    <div className="flex items-center justify-center py-24">
      <div className="w-6 h-6 border-2 border-cdp-accent border-t-transparent rounded-full animate-spin" />
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
