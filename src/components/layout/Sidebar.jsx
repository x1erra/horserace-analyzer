import { NavLink } from 'react-router-dom';
import { HiOutlineChartBar, HiOutlineFlag, HiOutlineSparkles, HiOutlineDocumentText, HiOutlineUpload, HiOutlineUser } from 'react-icons/hi'; // Added icons for Results and Upload
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
                        <img src="/horse_logo.png" alt="TrackData Logo" className="w-10 h-10 object-contain" />
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
                        to="/horses"
                        onClick={onClose}
                        className={({ isActive }) =>
                            `flex items-center gap-3 p-3 rounded-lg transition ${isActive ? 'bg-purple-800 text-white' : 'hover:bg-purple-900'
                            }`
                        }
                    >
                        <HiOutlineFlag className="w-6 h-6" />
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
                    <p className="text-xs text-gray-400 text-center">v0.1 • 2026</p>
                </div>
            </aside>
        </>
    );
}