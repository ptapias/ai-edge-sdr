import { useState, useRef, useEffect } from 'react'
import { BrowserRouter, Routes, Route, NavLink, Navigate, useLocation } from 'react-router-dom'
import { Search, Users, BarChart3, Settings, Link2, MessageSquare, LogOut, Upload, LayoutGrid, GitBranch, FlaskConical, FileText, ChevronDown } from 'lucide-react'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import SearchPage from './pages/SearchPage'
import LeadsPage from './pages/LeadsPage'
import DashboardPage from './pages/DashboardPage'
import SettingsPage from './pages/SettingsPage'
import AutomationPage from './pages/AutomationPage'
import InboxPage from './pages/InboxPage'
import ImportPage from './pages/ImportPage'
import PipelinePage from './pages/PipelinePage'
import SequencesPage from './pages/SequencesPage'
import ExperimentsPage from './pages/ExperimentsPage'
import DraftsPage from './pages/DraftsPage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'

const navClass = (isActive: boolean) =>
  `inline-flex items-center px-3 py-2 text-sm font-medium rounded-md ${
    isActive
      ? 'text-blue-600 bg-blue-50'
      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
  }`

function Navigation() {
  const { user, logout } = useAuth()
  const location = useLocation()
  const [leadsOpen, setLeadsOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const leadsRoutes = ['/search', '/leads', '/import']
  const isLeadsActive = leadsRoutes.some(r => location.pathname === r || location.pathname.startsWith(r + '/'))

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setLeadsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  // Close dropdown on route change
  useEffect(() => {
    setLeadsOpen(false)
  }, [location.pathname])

  return (
    <nav className="bg-white border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex">
            <div className="flex-shrink-0 flex items-center">
              <span className="text-xl font-bold text-blue-600">LinkedIn AI SDR</span>
            </div>
            <div className="hidden sm:ml-8 sm:flex sm:space-x-4 items-center">
              <NavLink to="/" className={({ isActive }) => navClass(isActive)}>
                <BarChart3 className="w-4 h-4 mr-2" />
                Dashboard
              </NavLink>

              {/* Leads dropdown */}
              <div className="relative" ref={dropdownRef}>
                <button
                  onClick={() => setLeadsOpen(!leadsOpen)}
                  className={`inline-flex items-center px-3 py-2 text-sm font-medium rounded-md ${
                    isLeadsActive
                      ? 'text-blue-600 bg-blue-50'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                  }`}
                >
                  <Users className="w-4 h-4 mr-2" />
                  Leads
                  <ChevronDown className={`w-3 h-3 ml-1 transition-transform ${leadsOpen ? 'rotate-180' : ''}`} />
                </button>
                {leadsOpen && (
                  <div className="absolute left-0 top-full mt-1 w-48 bg-white rounded-md shadow-lg border border-gray-200 py-1 z-50">
                    <NavLink
                      to="/search"
                      className={({ isActive }) =>
                        `flex items-center px-4 py-2 text-sm ${isActive ? 'text-blue-600 bg-blue-50' : 'text-gray-700 hover:bg-gray-50'}`
                      }
                    >
                      <Search className="w-4 h-4 mr-3" />
                      Buscar Leads
                    </NavLink>
                    <NavLink
                      to="/leads"
                      className={({ isActive }) =>
                        `flex items-center px-4 py-2 text-sm ${isActive ? 'text-blue-600 bg-blue-50' : 'text-gray-700 hover:bg-gray-50'}`
                      }
                    >
                      <Users className="w-4 h-4 mr-3" />
                      Mis Leads
                    </NavLink>
                    <NavLink
                      to="/import"
                      className={({ isActive }) =>
                        `flex items-center px-4 py-2 text-sm ${isActive ? 'text-blue-600 bg-blue-50' : 'text-gray-700 hover:bg-gray-50'}`
                      }
                    >
                      <Upload className="w-4 h-4 mr-3" />
                      Importar CSV
                    </NavLink>
                  </div>
                )}
              </div>

              <NavLink to="/pipeline" className={({ isActive }) => navClass(isActive)}>
                <LayoutGrid className="w-4 h-4 mr-2" />
                Pipeline
              </NavLink>
              <NavLink to="/sequences" className={({ isActive }) => navClass(isActive)}>
                <GitBranch className="w-4 h-4 mr-2" />
                Sequences
              </NavLink>
              <NavLink to="/experiments" className={({ isActive }) => navClass(isActive)}>
                <FlaskConical className="w-4 h-4 mr-2" />
                AutoOutreach
              </NavLink>
              <NavLink to="/drafts" className={({ isActive }) => navClass(isActive)}>
                <FileText className="w-4 h-4 mr-2" />
                Borradores
              </NavLink>
              <NavLink to="/inbox" className={({ isActive }) => navClass(isActive)}>
                <MessageSquare className="w-4 h-4 mr-2" />
                Inbox
              </NavLink>
              <NavLink to="/automation" className={({ isActive }) => navClass(isActive)}>
                <Link2 className="w-4 h-4 mr-2" />
                Connections
              </NavLink>
              <NavLink to="/settings" className={({ isActive }) => navClass(isActive)}>
                <Settings className="w-4 h-4 mr-2" />
                Settings
              </NavLink>
            </div>
          </div>

          {/* User menu */}
          <div className="flex items-center">
            <span className="text-sm text-gray-600 mr-4">
              {user?.full_name || user?.email}
            </span>
            <button
              onClick={() => logout()}
              className="inline-flex items-center px-3 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 hover:bg-gray-50 rounded-md"
            >
              <LogOut className="w-4 h-4 mr-2" />
              Logout
            </button>
          </div>
        </div>
      </div>
    </nav>
  )
}

function AppRoutes() {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="h-8 w-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="mt-2 text-sm text-gray-600">Loading...</p>
        </div>
      </div>
    )
  }

  return (
    <Routes>
      {/* Public routes */}
      <Route
        path="/login"
        element={isAuthenticated ? <Navigate to="/" replace /> : <LoginPage />}
      />
      <Route
        path="/register"
        element={isAuthenticated ? <Navigate to="/" replace /> : <RegisterPage />}
      />

      {/* Protected routes */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <div className="min-h-screen bg-gray-50">
              <Navigation />
              <main className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
                <DashboardPage />
              </main>
            </div>
          </ProtectedRoute>
        }
      />
      <Route
        path="/search"
        element={
          <ProtectedRoute>
            <div className="min-h-screen bg-gray-50">
              <Navigation />
              <main className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
                <SearchPage />
              </main>
            </div>
          </ProtectedRoute>
        }
      />
      <Route
        path="/leads"
        element={
          <ProtectedRoute>
            <div className="min-h-screen bg-gray-50">
              <Navigation />
              <main className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
                <LeadsPage />
              </main>
            </div>
          </ProtectedRoute>
        }
      />
      <Route
        path="/pipeline"
        element={
          <ProtectedRoute>
            <div className="min-h-screen bg-gray-50">
              <Navigation />
              <main className="max-w-full mx-auto py-6 px-4 sm:px-6 lg:px-8">
                <PipelinePage />
              </main>
            </div>
          </ProtectedRoute>
        }
      />
      <Route
        path="/sequences"
        element={
          <ProtectedRoute>
            <div className="min-h-screen bg-gray-50">
              <Navigation />
              <main className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
                <SequencesPage />
              </main>
            </div>
          </ProtectedRoute>
        }
      />
      <Route
        path="/experiments"
        element={
          <ProtectedRoute>
            <div className="min-h-screen bg-gray-50">
              <Navigation />
              <main className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
                <ExperimentsPage />
              </main>
            </div>
          </ProtectedRoute>
        }
      />
      <Route
        path="/drafts"
        element={
          <ProtectedRoute>
            <div className="min-h-screen bg-gray-50">
              <Navigation />
              <main className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
                <DraftsPage />
              </main>
            </div>
          </ProtectedRoute>
        }
      />
      <Route
        path="/import"
        element={
          <ProtectedRoute>
            <div className="min-h-screen bg-gray-50">
              <Navigation />
              <main className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
                <ImportPage />
              </main>
            </div>
          </ProtectedRoute>
        }
      />
      <Route
        path="/inbox"
        element={
          <ProtectedRoute>
            <div className="min-h-screen bg-gray-50">
              <Navigation />
              <main className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
                <InboxPage />
              </main>
            </div>
          </ProtectedRoute>
        }
      />
      <Route
        path="/automation"
        element={
          <ProtectedRoute>
            <div className="min-h-screen bg-gray-50">
              <Navigation />
              <main className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
                <AutomationPage />
              </main>
            </div>
          </ProtectedRoute>
        }
      />
      <Route
        path="/settings"
        element={
          <ProtectedRoute>
            <div className="min-h-screen bg-gray-50">
              <Navigation />
              <main className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
                <SettingsPage />
              </main>
            </div>
          </ProtectedRoute>
        }
      />

      {/* Catch all - redirect to dashboard */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App
