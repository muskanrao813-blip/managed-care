import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import { Activity, Users, LayoutDashboard } from 'lucide-react';
import PMSimulator from './pages/PMSimulator';
import PatientApp from './pages/PatientApp';
import AgentView from './pages/AgentView';

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen flex flex-col">
        <nav className="bg-blue-900 text-white px-6 py-3 flex items-center gap-8 shadow-lg">
          <div className="font-bold text-lg tracking-tight flex items-center gap-2">
            <Activity size={20} />
            <span>Managed Care Platform</span>
          </div>
          <div className="flex gap-1 ml-auto">
            <NavLink
              to="/pm-simulator"
              className={({ isActive }) =>
                `flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive ? 'bg-blue-700' : 'hover:bg-blue-800'
                }`
              }
            >
              <LayoutDashboard size={16} />
              PM Simulator
            </NavLink>
            <NavLink
              to="/patient-app"
              className={({ isActive }) =>
                `flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive ? 'bg-blue-700' : 'hover:bg-blue-800'
                }`
              }
            >
              <Activity size={16} />
              Patient App
            </NavLink>
            <NavLink
              to="/agent-view"
              className={({ isActive }) =>
                `flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive ? 'bg-blue-700' : 'hover:bg-blue-800'
                }`
              }
            >
              <Users size={16} />
              Agent View
            </NavLink>
          </div>
        </nav>

        <main className="flex-1">
          <Routes>
            <Route path="/" element={<PMSimulator />} />
            <Route path="/pm-simulator" element={<PMSimulator />} />
            <Route path="/patient-app" element={<PatientApp />} />
            <Route path="/agent-view" element={<AgentView />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
