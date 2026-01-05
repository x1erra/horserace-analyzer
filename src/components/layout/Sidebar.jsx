import { NavLink } from 'react-router-dom';
import { HiOutlineChartBar, HiOutlineFlag, HiOutlineSparkles, HiOutlineDocumentText, HiOutlineUpload } from 'react-icons/hi'; // Added icons for Results and Upload
import { GiHorseHead } from 'react-icons/gi';

export default function Sidebar() {
    return (
        <aside className="w-64 bg-black text-white fixed inset-y-0 left-0 overflow-y-auto border-r border-purple-900/50">
            <div className="p-6 border-b border-purple-900/50">
                <h1 className="text-3xl font-bold text-white flex items-center gap-2">
                    <GiHorseHead className="w-8 h-8 text-purple-400" />
                    Race Analyzer
                </h1>
            </div>

            <nav className="p-4 space-y-1">
                <NavLink
                    to="/"
                    className={({ isActive }) =>
                        `flex items-center gap-3 p-3 rounded-lg transition ${isActive ? 'bg-purple-800 text-white' : 'hover:bg-purple-900'
                        }`
                    }
                >
                    <HiOutlineChartBar className="w-6 h-6" />
                    Dashboard
                </NavLink>
                <NavLink
                    to="/races"
                    className={({ isActive }) =>
                        `flex items-center gap-3 p-3 rounded-lg transition ${isActive ? 'bg-purple-800 text-white' : 'hover:bg-purple-900'
                        }`
                    }
                >
                    <HiOutlineFlag className="w-6 h-6" />
                    Races
                </NavLink>
                <NavLink
                    to="/horses"
                    className={({ isActive }) =>
                        `flex items-center gap-3 p-3 rounded-lg transition ${isActive ? 'bg-purple-800 text-white' : 'hover:bg-purple-900'
                        }`
                    }
                >
                    <GiHorseHead className="w-6 h-6" />
                    Horses
                </NavLink>
                <NavLink
                    to="/predictions"
                    className={({ isActive }) =>
                        `flex items-center gap-3 p-3 rounded-lg transition ${isActive ? 'bg-purple-800 text-white' : 'hover:bg-purple-900'
                        }`
                    }
                >
                    <HiOutlineSparkles className="w-6 h-6" />
                    Predictions
                </NavLink>
                <NavLink
                    to="/results"
                    className={({ isActive }) =>
                        `flex items-center gap-3 p-3 rounded-lg transition ${isActive ? 'bg-purple-800 text-white' : 'hover:bg-purple-900'
                        }`
                    }
                >
                    <HiOutlineDocumentText className="w-6 h-6" />
                    Results
                </NavLink>
                <NavLink
                    to="/upload"
                    className={({ isActive }) =>
                        `flex items-center gap-3 p-3 rounded-lg transition ${isActive ? 'bg-purple-800 text-white' : 'hover:bg-purple-900'
                        }`
                    }
                >
                    <HiOutlineUpload className="w-6 h-6" />
                    Upload
                </NavLink>
            </nav>

            <div className="p-4 mt-auto border-t border-purple-900/50">
                <p className="text-xs text-gray-400 text-center">v0.1 • 2026</p>
            </div>
        </aside>
    );
}