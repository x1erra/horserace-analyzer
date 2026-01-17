import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Sidebar from './components/layout/Sidebar.jsx';
import Header from './components/layout/Header.jsx';
import Dashboard from './pages/Dashboard.jsx';
import RaceDetails from './pages/RaceDetails.jsx';
import Races from './pages/Races.jsx';
import Horses from './pages/Horses.jsx';
import Predictions from './pages/Predictions.jsx';
import Betting from './pages/Betting.jsx';
import Results from './pages/Results.jsx'; // Added for Results page
import Upload from './pages/Upload.jsx'; // Added for Upload page
import Claims from './pages/Claims.jsx'; // Added for Claims page
import { useState } from 'react';
import PasswordGate from './components/auth/PasswordGate.jsx';
import PullToRefresh from './components/layout/PullToRefresh.jsx';

function App() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  return (
    <Router>
      <PasswordGate>
        <div className="min-h-screen bg-black flex flex-col md:flex-row">
          {/* Sidebar - responsive behavior handled internally */}
          <Sidebar isOpen={isSidebarOpen} onClose={() => setIsSidebarOpen(false)} />

          {/* Main Content */}
          <div className="flex-1">
            <PullToRefresh>
              <Header onToggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)} />
              <main className="p-8 bg-black">
                <Routes>
                  <Route path="/" element={<Dashboard />} />
                  <Route path="/races" element={<Races />} />
                  <Route path="/horses" element={<Horses />} />
                  <Route path="/predictions" element={<Predictions />} />
                  <Route path="/betting" element={<Betting />} />
                  <Route path="/race/:id" element={<RaceDetails />} />
                  <Route path="/results" element={<Results />} /> {/* New route */}
                  <Route path="/claims" element={<Claims />} /> {/* New route */}
                  <Route path="/upload" element={<Upload />} /> {/* New route */}
                </Routes>
              </main>
            </PullToRefresh>
          </div>
        </div>
      </PasswordGate>
    </Router>
  );
}

export default App;