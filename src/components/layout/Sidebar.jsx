import { NavLink } from 'react-router-dom';
import { HiOutlineChartBar, HiOutlineFlag, HiOutlineSparkles, HiOutlineDocumentText, HiOutlineUpload, HiOutlineUser, HiOutlineCurrencyDollar } from 'react-icons/hi'; // Added icons for Results and Upload
import { GiHorseHead } from 'react-icons/gi';

export default function Sidebar({ isOpen, onClose }) {
    return (
        <>
            {/* Mobile Backdrop */}
            {isOpen && (
                <div
                    className="fixed inset-0 bg-black/50 z-40 md:hidden"
                    onClick={onClose}
                />
            )}

            <aside
                className={`
                    fixed inset-y-0 left-0 z-50 w-64 bg-black text-white border-r border-purple-900/50 
                    transform transition-transform duration-300 ease-in-out
                    ${isOpen ? 'translate-x-0' : '-translate-x-full'}
                    md:translate-x-0 md:static md:h-screen overflow-y-auto
                `}
            >
                <div className="p-6 border-b border-purple-900/50 flex justify-between items-center">
                    <h1 className="text-3xl font-bold text-white flex items-center gap-2">
                        <img src="/horse_logo.png" alt="TrackData Logo" className="w-16 h-16 object-contain" />
                        TrackData
                    </h1>
                    {/* Close button for mobile */}
                    <button onClick={onClose} className="md:hidden text-gray-400 hover:text-white">
                        ✕
                    </button>
                </div>

                <nav className="p-4 space-y-1">
                    <NavLink
                        to="/"
                        onClick={onClose}
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
                        onClick={onClose}
                        className={({ isActive }) =>
                            `flex items-center gap-3 p-3 rounded-lg transition ${isActive ? 'bg-purple-800 text-white' : 'hover:bg-purple-900'
                            }`
                        }
                    >
                        <HiOutlineFlag className="w-6 h-6" />
                        Races
                    </NavLink>
                    <NavLink
                        to="/results"
                        onClick={onClose}
                        className={({ isActive }) =>
                            `flex items-center gap-3 p-3 rounded-lg transition ${isActive ? 'bg-purple-800 text-white' : 'hover:bg-purple-900'
                            }`
                        }
                    >
                        <HiOutlineDocumentText className="w-6 h-6" />
                        Results
                    </NavLink>
                    <NavLink
                        to="/claims"
                        onClick={onClose}
                        className={({ isActive }) =>
                            `flex items-center gap-3 p-3 rounded-lg transition ${isActive ? 'bg-purple-800 text-white' : 'hover:bg-purple-900'
                            }`
                        }
                    >
                        <HiOutlineUser className="w-6 h-6" />
                        Claims
                    </NavLink>
                    <NavLink
                        to="/horses"
                        onClick={onClose}
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
                        onClick={onClose}
                        className={({ isActive }) =>
                            `flex items-center gap-3 p-3 rounded-lg transition ${isActive ? 'bg-purple-800 text-white' : 'hover:bg-purple-900'
                            }`
                        }
                    >
                        <HiOutlineSparkles className="w-6 h-6" />
                        Predictions
                    </NavLink>
                    <NavLink
                        to="/betting"
                        onClick={onClose}
                        className={({ isActive }) =>
                            `flex items-center gap-3 p-3 rounded-lg transition ${isActive ? 'bg-purple-800 text-white' : 'hover:bg-purple-900'
                            }`
                        }
                    >
                        <HiOutlineCurrencyDollar className="w-6 h-6" />
                        Betting
                    </NavLink>
                    <NavLink
                        to="/upload"
                        onClick={onClose}
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
                    <p className="text-xs text-gray-400 text-center mb-4">v0.1 • 2026</p>
                    <button
                        onClick={() => {
                            localStorage.removeItem('isAppAuthenticated');
                            window.location.reload();
                        }}
                        className="w-full flex items-center gap-3 p-3 rounded-lg transition hover:bg-red-900/20 text-gray-400 hover:text-red-400 group"
                    >
                        <svg className="w-6 h-6 transition-transform group-hover:scale-110" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                        </svg>
                        <span className="font-medium">Logout</span>
                    </button>
                </div>
            </aside>
        </>
    );
}