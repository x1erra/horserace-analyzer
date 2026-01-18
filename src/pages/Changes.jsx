import { useState, useEffect } from 'react';
import axios from 'axios';
import TrackFilter from '../components/TrackFilter';
import { ShieldAlert, Shuffle, Info } from 'lucide-react';

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
        const fetchChanges = async () => {
            try {
                setLoading(true);
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

        // Refresh every minute
        const interval = setInterval(fetchChanges, 60000);
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

    // Format time helper
    const formatTime = (isoString) => {
        if (!isoString) return '-';
        return new Date(isoString).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    };

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
                                ? 'bg-purple-600 text-white shadow-lg'
                                : 'text-gray-400 hover:text-white hover:bg-purple-900/20'
                            }`}
                    >
                        Upcoming
                    </button>
                    <button
                        onClick={() => handleModeChange('history')}
                        className={`px-4 py-2 rounded-md text-sm font-medium transition ${viewMode === 'history'
                                ? 'bg-purple-600 text-white shadow-lg'
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
                                        <th className="p-4">Time</th>
                                        <th className="p-4">Track</th>
                                        <th className="p-4">Race</th>
                                        <th className="p-4">Horse</th>
                                        <th className="p-4">Type</th>
                                        <th className="p-4">Details</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-purple-900/20">
                                    {changes.map((item) => (
                                        <tr key={item.id} className="hover:bg-purple-900/10 transition-colors group">
                                            <td className="p-4 text-purple-400 font-mono text-sm">
                                                {formatTime(item.change_time)}
                                            </td>
                                            <td className="p-4 font-bold text-white">{item.track_code}</td>
                                            <td className="p-4">
                                                <span className="bg-purple-900/40 px-2 py-1 rounded text-xs font-mono text-purple-300 border border-purple-500/20">
                                                    R{item.race_number}
                                                </span>
                                            </td>
                                            <td className="p-4">
                                                <span className="text-white font-medium group-hover:text-purple-400 transition-colors">
                                                    {item.horse_name || 'Race-wide'}
                                                </span>
                                                {item.program_number && (
                                                    <span className="ml-2 text-xs text-gray-500">#{item.program_number}</span>
                                                )}
                                            </td>
                                            <td className="p-4">
                                                <span className={`px-2 py-1 rounded text-xs font-bold uppercase tracking-wider ${item.change_type === 'Scratch' ? 'bg-red-900/40 text-red-400 border border-red-500/30' :
                                                        item.change_type === 'Jockey Change' ? 'bg-blue-900/40 text-blue-400 border border-blue-500/30' :
                                                            item.change_type === 'Race Cancelled' ? 'bg-red-950/60 text-red-500 border border-red-600/50 animate-pulse' :
                                                                'bg-gray-800 text-gray-400'
                                                    }`}>
                                                    {item.change_type}
                                                </span>
                                            </td>
                                            <td className="p-4 text-gray-400 text-sm max-w-xs truncate" title={item.description}>
                                                {item.description}
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
