import { BrowserRouter, Routes, Route, NavLink, Navigate } from 'react-router-dom'
import { Search, Users, BarChart3, Settings, Link2, MessageSquare, LogOut, Upload, LayoutGrid } from 'lucide-react'
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
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'

function Navigation() {
  const { user, logout } = useAuth()

  return (
    <nav className="bg-white border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex">
            <div className="flex-shrink-0 flex items-center">
              <span className="text-xl font-bold text-blue-600">LinkedIn AI SDR</span>
            </div>
            <div className="hidden sm:ml-8 sm:flex sm:space-x-4">
              <NavLink
                to="/"
                className={({ isActive }) =>
                  `inline-flex items-center px-3 py-2 text-sm font-medium rounded-md ${
                    isActive
                      ? 'text-blue-600 bg-blue-50'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                  }`
                }
              >
                <BarChart3 className="w-4 h-4 mr-2" />
                Dashboard
              </NavLink>
              <NavLink
                to="/search"
                className={({ isActive }) =>
                  `inline-flex items-center px-3 py-2 text-sm font-medium rounded-md ${
                    isActive
                      ? 'text-blue-600 bg-blue-50'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                  }`
                }
              >
                <Search className="w-4 h-4 mr-2" />
                Search Leads
              </NavLink>
              <NavLink
                to="/leads"
                className={({ isActive }) =>
                  `inline-flex items-center px-3 py-2 text-sm font-medium rounded-md ${
                    isActive
                      ? 'text-blue-600 bg-blue-50'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                  }`
                }
              >
                <Users className="w-4 h-4 mr-2" />
                Leads
              </NavLink>
              <NavLink
                to="/pipeline"
                className={({ isActive }) =>
                  `inline-flex items-center px-3 py-2 text-sm font-medium rounded-md ${
                    isActive
                      ? 'text-blue-600 bg-blue-50'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                  }`
                }
              >
                <LayoutGrid className="w-4 h-4 mr-2" />
                Pipeline
              </NavLink>
              <NavLink
                to="/import"
                className={({ isActive }) =>
                  `inline-flex items-center px-3 py-2 text-sm font-medium rounded-md ${
                    isActive
                      ? 'text-blue-600 bg-blue-50'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                  }`
                }
              >
                <Upload className="w-4 h-4 mr-2" />
                Import
              </NavLink>
              <NavLink
                to="/inbox"
                className={({ isActive }) =>
                  `inline-flex items-center px-3 py-2 text-sm font-medium rounded-md ${
                    isActive
                      ? 'text-blue-600 bg-blue-50'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                  }`
                }
              >
                <MessageSquare className="w-4 h-4 mr-2" />
                Inbox
              </NavLink>
              <NavLink
                to="/automation"
                className={({ isActive }) =>
                  `inline-flex items-center px-3 py-2 text-sm font-medium rounded-md ${
                    isActive
                      ? 'text-blue-600 bg-blue-50'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                  }`
                }
              >
                <Link2 className="w-4 h-4 mr-2" />
                Connections
              </NavLink>
              <NavLink
                to="/settings"
                className={({ isActive }) =>
                  `inline-flex items-center px-3 py-2 text-sm font-medium rounded-md ${
                    isActive
                      ? 'text-blue-600 bg-blue-50'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                  }`
                }
              >
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
