import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import { Search, Users, BarChart3, Settings, Zap, MessageSquare } from 'lucide-react'
import SearchPage from './pages/SearchPage'
import LeadsPage from './pages/LeadsPage'
import DashboardPage from './pages/DashboardPage'
import SettingsPage from './pages/SettingsPage'
import AutomationPage from './pages/AutomationPage'
import InboxPage from './pages/InboxPage'

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-50">
        {/* Navigation */}
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
                    <Zap className="w-4 h-4 mr-2" />
                    Automation
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
            </div>
          </div>
        </nav>

        {/* Main content */}
        <main className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/leads" element={<LeadsPage />} />
            <Route path="/inbox" element={<InboxPage />} />
            <Route path="/automation" element={<AutomationPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

export default App
