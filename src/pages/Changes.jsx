import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { format, parseISO } from 'date-fns';
import { AlertTriangle, Info, Shuffle, ShieldAlert } from 'lucide-react';
import TrackFilter from '../components/TrackFilter';

const getPostColor = (number) => {
    const num = parseInt(number);
    if (isNaN(num)) return { bg: '#374151', text: '#FFFFFF' };

    switch (num) {
        case 1: return { bg: '#EF4444', text: '#FFFFFF' }; // Red
        case 2: return { bg: '#FFFFFF', text: '#000000' }; // White
        case 3: return { bg: '#3B82F6', text: '#FFFFFF' }; // Blue
        case 4: return { bg: '#EAB308', text: '#000000' }; // Yellow
        case 5: return { bg: '#22C55E', text: '#FFFFFF' }; // Green
        case 6: return { bg: '#000000', text: '#FACC15' }; // Black with Yellow text
        case 7: return { bg: '#F97316', text: '#000000' }; // Orange with Black text
        case 8: return { bg: '#EC4899', text: '#000000' }; // Pink with Black text
        case 9: return { bg: '#06B6D4', text: '#000000' }; // Turquoise with Black text
        case 10: return { bg: '#A855F7', text: '#FFFFFF' }; // Purple
        case 11: return { bg: '#9CA3AF', text: '#FFFFFF' }; // Grey
        case 12: return { bg: '#84CC16', text: '#000000' }; // Lime with Black text
        case 13: return { bg: '#78350F', text: '#FFFFFF' }; // Brown
        case 14: return { bg: '#831843', text: '#FFFFFF' }; // Maroon
        case 15: return { bg: '#C3B091', text: '#000000' }; // Khaki
        case 16: return { bg: '#60A5FA', text: '#FFFFFF' }; // Copen Blue
        case 17: return { bg: '#1E3A8A', text: '#FFFFFF' }; // Navy
        case 18: return { bg: '#14532D', text: '#FFFFFF' }; // Forest Green
        case 19: return { bg: '#0EA5E9', text: '#FFFFFF' }; // Moonstone
        case 20: return { bg: '#D946EF', text: '#FFFFFF' }; // Fuschia
        default: return { bg: '#374151', text: '#FFFFFF' };
    }
};

const getChangeIcon = (type) => {
    switch (type) {
        case 'Scratch': return <ShieldAlert className="w-4 h-4 text-red-500" />;
        case 'Jockey Change': return <Shuffle className="w-4 h-4 text-blue-400" />;
        case 'Equipment Change': return <Info className="w-4 h-4 text-yellow-400" />;
        default: return <Info className="w-4 h-4 text-gray-400" />;
    }
};

const getChangeColor = (type) => {
    switch (type) {
        case 'Scratch': return 'bg-red-500/10 text-red-500 border-red-500/20';
        case 'Jockey Change': return 'bg-blue-500/10 text-blue-400 border-blue-500/20';
        case 'Equipment Change': return 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20';
        default: return 'bg-gray-500/10 text-gray-400 border-gray-500/20';
    }
};

export default function Changes() {
    const [changes, setChanges] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [viewMode, setViewMode] = useState('upcoming'); // 'upcoming' or 'history'
    const [selectedTrack, setSelectedTrack] = useState('All');

    // Pagination State
    const [currentPage, setCurrentPage] = useState(1);
    const [itemsPerPage, setItemsPerPage] = useState(20);
    const [totalPages, setTotalPages] = useState(1);
    const [totalCount, setTotalCount] = useState(0);
    const [availableTracks, setAvailableTracks] = useState(['All']);

    // Fetch filter options on mount
    useEffect(() => {
        const fetchOptions = async () => {
            try {
                const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:5001';
                const response = await axios.get(`${baseUrl}/api/filter-options`);
                if (response.data && response.data.tracks) {
                    setAvailableTracks(['All', ...response.data.tracks.map(t => t.code)]);
                }
            } catch (e) { console.error(e); }
        };
        fetchOptions();
    }, []);

    // Fetch changes
    useEffect(() => {
        const fetchChanges = async (isBackground = false) => {
            try {
                if (!isBackground) setLoading(true);
                const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:5001';

                const response = await axios.get(`${baseUrl}/api/changes`, {
                    params: {
                        mode: viewMode,
                        track: selectedTrack,
                        page: currentPage,
                        limit: itemsPerPage
                    }
                });

                setChanges(response.data.changes || []);
                setTotalPages(response.data.total_pages || 1);
                setTotalCount(response.data.count || 0);
                setError(null);
            } catch (err) {
                console.error("Error fetching changes:", err);
                setError("Failed to load late changes.");
            } finally {
                setLoading(false);
            }
        };

        fetchChanges();

        // Refresh every minute - silent background refresh
        const interval = setInterval(() => fetchChanges(true), 60000);
        return () => clearInterval(interval);

    }, [viewMode, selectedTrack, currentPage, itemsPerPage]);

    // Handle filter/mode changes -> reset page
    const handleModeChange = (mode) => {
        setViewMode(mode);
        setCurrentPage(1);
    };

    const handleTrackChange = (track) => {
        setSelectedTrack(track);
        setCurrentPage(1);
    };

    const paginate = (pageNumber) => setCurrentPage(pageNumber);

    return (
        <div className="space-y-8">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h3 className="text-3xl font-bold text-white">Late Changes</h3>
                    <p className="text-sm text-gray-400">Live updates: Scratches, Jockey Changes, and more.</p>
                </div>

                <div className="flex bg-black p-1 rounded-lg border border-purple-900/50">
                    <button
                        onClick={() => handleModeChange('upcoming')}
                        className={`px-4 py-2 rounded-md text-sm font-medium transition ${viewMode === 'upcoming'
                            ? 'bg-purple-900/40 text-purple-100 border border-purple-500/40 shadow-sm'
                            : 'text-gray-400 hover:text-white hover:bg-purple-900/20'
                            }`}
                    >
                        Today's Races
                    </button>
                    <button
                        onClick={() => handleModeChange('history')}
                        className={`px-4 py-2 rounded-md text-sm font-medium transition ${viewMode === 'history'
                            ? 'bg-purple-900/40 text-purple-100 border border-purple-500/40 shadow-sm'
                            : 'text-gray-400 hover:text-white hover:bg-purple-900/20'
                            }`}
                    >
                        History
                    </button>
                </div>
            </div>

            {/* Track Filter */}
            <div className="mb-6">
                <TrackFilter
                    tracks={availableTracks.filter(t => t !== 'All')}
                    selectedTrack={selectedTrack}
                    onSelectTrack={handleTrackChange}
                />
            </div>

            {error && (
                <div className="p-4 bg-red-900/20 border border-red-500/50 rounded-lg text-red-200">
                    {error}
                </div>
            )}

            {/* Content */}
            <div className="bg-black rounded-xl shadow-md overflow-hidden border border-purple-900/50 min-h-[400px]">
                {loading ? (
                    <div className="flex flex-col items-center justify-center h-64 space-y-4">
                        <div className="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin"></div>
                        <p className="text-gray-400">Checking for updates...</p>
                    </div>
                ) : changes.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-64 text-gray-500">
                        <p className="text-lg">No late changes reported {selectedTrack !== 'All' ? `for ${selectedTrack}` : ''}.</p>
                    </div>
                ) : (
                    <>
                        <div className="overflow-x-auto">
                            <table className="w-full text-left text-gray-300">
                                <thead className="bg-purple-900/30 border-b border-purple-900/50">
                                    <tr>
                                        <th className="p-4">Date</th>
                                        <th className="p-4">Track</th>
                                        <th className="p-4">Race</th>
                                        <th className="p-4">Horse</th>
                                        <th className="p-4 text-center">Type</th>
                                        <th className="p-4">Details</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-purple-900/20">
                                    {changes.map((item) => (
                                        <tr key={item.id} className="hover:bg-purple-900/10 transition-colors group">
                                            <td className="p-4 text-gray-300 font-medium whitespace-nowrap">
                                                {item.race_date ? format(parseISO(item.race_date), 'MMM d, yyyy') : '-'}
                                            </td>
                                            <td className="p-4">
                                                <span className="inline-flex items-center justify-center px-2.5 py-1 rounded-md bg-purple-900/20 text-purple-300 text-xs font-bold border border-purple-500/30 font-mono">
                                                    {item.track_code}
                                                </span>
                                            </td>
                                            <td className="p-4 whitespace-nowrap">
                                                <Link
                                                    to={`/race/${item.track_code}-${item.race_date?.replace(/-/g, '')}-${item.race_number}`}
                                                    state={{ from: 'changes' }}
                                                    className="text-purple-400 hover:text-purple-300 hover:underline transition-colors"
                                                >
                                                    Race {item.race_number}
                                                </Link>
                                            </td>
                                            <td className="p-4">
                                                <div className="flex items-center gap-3">
                                                    {item.program_number && item.program_number !== '-' ? (
                                                        (() => {
                                                            const style = getPostColor(item.program_number);
                                                            return (
                                                                <div
                                                                    className="w-8 h-8 rounded-md flex-shrink-0 flex items-center justify-center font-bold text-sm shadow-sm leading-none"
                                                                    style={{ backgroundColor: style.bg, color: style.text }}
                                                                >
                                                                    {item.program_number}
                                                                </div>
                                                            );
                                                        })()
                                                    ) : (
                                                        <div className="w-8 h-8 rounded-md bg-gray-800 flex items-center justify-center text-gray-500 text-xs">
                                                            -
                                                        </div>
                                                    )}
                                                    <span className="text-white font-medium group-hover:text-purple-400 transition-colors">
                                                        {item.horse_name || 'Race-wide'}
                                                    </span>
                                                </div>
                                            </td>
                                            <td className="p-4 text-center">
                                                <span className={`inline-flex items-center justify-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${getChangeColor(item.change_type)}`}>
                                                    {getChangeIcon(item.change_type)}
                                                    {item.change_type}
                                                </span>
                                            </td>
                                            <td className="p-4 text-gray-400 text-sm max-w-xs break-words">
                                                {item.description || '-'}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>

                        {/* Pagination Controls - Matching Results.jsx Style */}
                        <div className="px-4 py-3 border-t border-purple-900/50 bg-black flex flex-col sm:flex-row items-center justify-between gap-4">
                            <div className="flex items-center text-sm text-gray-400">
                                <span>Show</span>
                                <select
                                    value={itemsPerPage}
                                    onChange={(e) => {
                                        setItemsPerPage(Number(e.target.value));
                                        setCurrentPage(1);
                                    }}
                                    className="mx-2 bg-black border border-purple-900/50 text-white text-xs rounded px-2 py-1 focus:outline-none focus:border-purple-500"
                                >
                                    <option value={10} className="bg-black">10</option>
                                    <option value={20} className="bg-black">20</option>
                                    <option value={30} className="bg-black">30</option>
                                    <option value={50} className="bg-black">50</option>
                                    <option value={100} className="bg-black">100</option>
                                </select>
                                <span>results per page</span>
                            </div>

                            <div className="flex items-center gap-2">
                                <button
                                    onClick={() => paginate(currentPage - 1)}
                                    disabled={currentPage === 1}
                                    className={`px-3 py-1 rounded text-sm font-medium transition ${currentPage === 1
                                        ? 'bg-purple-900/10 text-purple-800 cursor-not-allowed opacity-50'
                                        : 'bg-purple-900/30 text-purple-200 hover:bg-purple-900/50'
                                        }`}
                                >
                                    Previous
                                </button>

                                <span className="text-sm text-gray-400">
                                    Page <span className="font-medium text-white">{currentPage}</span> of <span className="font-medium text-white">{totalPages}</span>
                                </span>

                                <button
                                    onClick={() => paginate(currentPage + 1)}
                                    disabled={currentPage === totalPages}
                                    className={`px-3 py-1 rounded text-sm font-medium transition ${currentPage === totalPages
                                        ? 'bg-purple-900/10 text-purple-800 cursor-not-allowed opacity-50'
                                        : 'bg-purple-900/30 text-purple-200 hover:bg-purple-900/50'
                                        }`}
                                >
                                    Next
                                </button>
                            </div>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}
