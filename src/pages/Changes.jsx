
import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { format, parseISO } from 'date-fns';
import { AlertTriangle, Info, Shuffle, ShieldAlert } from 'lucide-react';

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
        case 15: return { bg: '#C3B091', text: '#000000' }; // Khaki (Corrected)
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
    const [loading, setLoading] = useState(true);
    const [changes, setChanges] = useState([]);
    const [error, setError] = useState(null);
    const [viewMode, setViewMode] = useState('upcoming'); // 'upcoming' or 'all'
    const [page, setPage] = useState(1);
    const [limit, setLimit] = useState(20);
    const [totalPages, setTotalPages] = useState(1);

    const fetchChanges = async () => {
        try {
            setLoading(true);
            setError(null);

            const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:5001';
            const endpoint = `${baseUrl}/api/changes`;

            const params = {
                view: viewMode,
                page: page,
                limit: limit,
                _t: Date.now() // cache buster
            };

            const response = await axios.get(endpoint, { params });

            // Backend returns list and count
            setChanges(response.data.changes || []);
            const totalCount = response.data.count || 0;
            setTotalPages(Math.ceil(totalCount / limit) || 1);

        } catch (e) {
            console.error("Error fetching changes:", e);
            setError("Failed to load changes. Is the backend running?");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        setPage(1); // Reset to page 1 when view mode changes
    }, [viewMode]);

    useEffect(() => {
        fetchChanges();
    }, [viewMode, page, limit]);

    const handleNextPage = () => {
        if (page < totalPages) setPage(p => p + 1);
    };

    const handlePrevPage = () => {
        if (page > 1) setPage(p => p - 1);
    };

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h1 className="text-3xl font-bold text-white flex items-center gap-3">
                        <AlertTriangle className="w-8 h-8 text-yellow-500" />
                        Late Changes
                    </h1>
                    <p className="text-gray-400 mt-1">
                        Real-time updates (Scratches, Jockey Changes, etc.)
                    </p>
                </div>

                <div className="flex items-center gap-3 bg-black p-1 rounded-lg border border-purple-900/30">
                    <button
                        onClick={() => setViewMode('upcoming')}
                        className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${viewMode === 'upcoming'
                            ? 'bg-purple-900/40 text-purple-100 border border-purple-500/30 shadow-[0_0_10px_rgba(147,51,234,0.2)]'
                            : 'text-gray-400 hover:text-white hover:bg-purple-900/20'
                            }`}
                    >
                        Upcoming
                    </button>
                    <button
                        onClick={() => setViewMode('all')}
                        className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${viewMode === 'all'
                            ? 'bg-purple-900/40 text-purple-100 border border-purple-500/30 shadow-[0_0_10px_rgba(147,51,234,0.2)]'
                            : 'text-gray-400 hover:text-white hover:bg-purple-900/20'
                            }`}
                    >
                        All History
                    </button>
                </div>
            </div>

            {/* Content */}
            <div className="bg-black rounded-xl border border-purple-900/20 overflow-hidden shadow-xl">
                {loading ? (
                    <div className="p-12 text-center text-gray-500 animate-pulse">
                        Loading updates...
                    </div>
                ) : error ? (
                    <div className="p-12 text-center text-red-400">
                        {error}
                    </div>
                ) : changes.length === 0 ? (
                    <div className="p-12 text-center text-gray-500">
                        No changes found for this period.
                    </div>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full text-left border-collapse">
                            <thead>
                                <tr className="border-b border-purple-900/30 bg-purple-900/20 text-purple-300 text-sm uppercase tracking-wider">
                                    <th className="p-4">Date</th>
                                    <th className="p-4">Track</th>
                                    <th className="p-4">Race</th>
                                    <th className="p-4">Horse</th>
                                    <th className="p-4">Type</th>
                                    <th className="p-4">Details</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-purple-900/30">
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
                                        <td className="p-4">
                                            <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${getChangeColor(item.change_type)}`}>
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
                )}
            </div>

            {/* Pagination Controls */}
            {!loading && !error && changes.length > 0 && (
                <div className="px-4 py-3 border-t border-purple-900/50 bg-black flex flex-col sm:flex-row items-center justify-between gap-4 rounded-b-xl">
                    <div className="flex items-center text-sm text-gray-400">
                        <span>Show</span>
                        <select
                            value={limit}
                            onChange={(e) => {
                                setLimit(Number(e.target.value));
                                setPage(1);
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
                            onClick={handlePrevPage}
                            disabled={page === 1}
                            className={`px-3 py-1 rounded text-sm font-medium transition ${page === 1
                                ? 'bg-purple-900/10 text-purple-800 cursor-not-allowed opacity-50'
                                : 'bg-purple-900/30 text-purple-200 hover:bg-purple-900/50'
                                }`}
                        >
                            Previous
                        </button>

                        <span className="text-sm text-gray-400">
                            Page <span className="font-medium text-white">{page}</span> of <span className="font-medium text-white">{totalPages}</span>
                        </span>

                        <button
                            onClick={handleNextPage}
                            disabled={page >= totalPages}
                            className={`px-3 py-1 rounded text-sm font-medium transition ${page >= totalPages
                                ? 'bg-purple-900/10 text-purple-800 cursor-not-allowed opacity-50'
                                : 'bg-purple-900/30 text-purple-200 hover:bg-purple-900/50'
                                }`}
                        >
                            Next
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
