import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Sidebar from './components/layout/Sidebar.jsx';
import Header from './components/layout/Header.jsx';
import Dashboard from './pages/Dashboard.jsx';
import RaceDetails from './pages/RaceDetails.jsx';
import Races from './pages/Races.jsx';
import Horses from './pages/Horses.jsx';
import Predictions from './pages/Predictions.jsx';
import { useState } from 'react';

function App() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  return (
    <Router>
      <div className="min-h-screen bg-black flex flex-col md:flex-row">
        {/* Sidebar - hidden on mobile, fixed on desktop */}
        <div className={`${isSidebarOpen ? 'block' : 'hidden'} md:block`}>
          <Sidebar />
        </div>

        {/* Main Content */}
        <div className="flex-1 md:ml-64">
          <Header onToggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)} />
          <main className="p-8 bg-black">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/race/:id" element={<RaceDetails />} />
              <Route path="/races" element={<Races />} />
              <Route path="/horses" element={<Horses />} />
              <Route path="/predictions" element={<Predictions />} />
            </Routes>
          </main>
        </div>
      </div>
    </Router>
  );
}

export default App;