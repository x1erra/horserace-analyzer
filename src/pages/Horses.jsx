import { Link } from 'react-router-dom';
import { useState, useEffect, useCallback } from 'react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:5001';

export default function Horses() {
    const [searchQuery, setSearchQuery] = useState('');
    const [horses, setHorses] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [page, setPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    const [debouncedSearch, setDebouncedSearch] = useState('');

    // Debounce search
    useEffect(() => {
        const timer = setTimeout(() => {
            setDebouncedSearch(searchQuery);
            setPage(1); // Reset to first page on search
        }, 300);
        return () => clearTimeout(timer);
    }, [searchQuery]);

    // Fetch horses from API
    const fetchHorses = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const params = new URLSearchParams({
                page: page.toString(),
                limit: '24'
            });
            if (debouncedSearch) {
                params.set('search', debouncedSearch);
            }

            const response = await fetch(`${API_BASE}/api/horses?${params}`);
            if (!response.ok) throw new Error('Failed to fetch horses');

            const data = await response.json();
            setHorses(data.horses || []);
            setTotalPages(data.total_pages || 1);
        } catch (err) {
            setError(err.message);
            setHorses([]);
        } finally {
            setLoading(false);
        }
    }, [page, debouncedSearch]);

    useEffect(() => {
        fetchHorses();
    }, [fetchHorses]);

    // Format sex display
    const formatSex = (sex) => {
        const sexMap = { 'C': 'Colt', 'F': 'Filly', 'G': 'Gelding', 'H': 'Horse', 'M': 'Mare' };
        return sexMap[sex] || sex || 'N/A';
    };

    return (
        <div className="space-y-8">
            <h3 className="text-3xl font-bold text-white">Horse Profiles</h3>
            <p className="text-sm text-gray-400 mb-4">Search and view detailed stats for horses in our database.</p>

            {/* Search bar */}
            <input
                type="text"
                placeholder="Search horses by name..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-black border border-purple-900/50 text-white px-4 py-3 rounded-md focus:outline-none focus:border-purple-600 transition"
            />

            {/* Loading state */}
            {loading && (
                <div className="text-center py-12">
                    <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-purple-500"></div>
                    <p className="text-gray-400 mt-4">Loading horses...</p>
                </div>
            )}

            {/* Error state */}
            {error && !loading && (
                <div className="text-center py-12">
                    <p className="text-red-400">Error: {error}</p>
                    <button
                        onClick={fetchHorses}
                        className="mt-4 px-4 py-2 bg-purple-900/40 text-purple-100 border border-purple-500/40 rounded hover:bg-purple-800/50 transition"
                    >
                        Retry
                    </button>
                </div>
            )}

            {/* No results */}
            {!loading && !error && horses.length === 0 && (
                <p className="text-gray-400 text-center py-12">
                    {debouncedSearch ? 'No horses match your search.' : 'No horses found in database.'}
                </p>
            )}

            {/* Grid of horse cards */}
            {!loading && !error && horses.length > 0 && (
                <>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {horses.map((horse, index) => (
                            <div
                                key={horse.id}
                                className="bg-black rounded-xl shadow-md p-6 hover:shadow-xl transition border border-purple-900/50 opacity-0 animate-fadeIn flex flex-col h-full"
                                style={{ animationDelay: `${index * 30}ms` }}
                            >
                                <h4 className="text-xl font-bold text-white mb-2">{horse.name}</h4>
                                <p className="text-sm text-gray-400 mb-3">
                                    {formatSex(horse.sex)} {horse.color && `• ${horse.color}`}
                                </p>
                                {horse.sire && (
                                    <p className="text-xs text-gray-500 mb-1">
                                        <span className="text-gray-600">Sire:</span> {horse.sire}
                                    </p>
                                )}
                                {horse.dam && (
                                    <p className="text-xs text-gray-500 mb-3">
                                        <span className="text-gray-600">Dam:</span> {horse.dam}
                                    </p>
                                )}

                                {/* Stats */}
                                <div className="grid grid-cols-3 gap-2 mb-4 text-center">
                                    <div className="bg-gray-900/50 rounded p-2">
                                        <div className="text-lg font-bold text-purple-400">{horse.total_races}</div>
                                        <div className="text-xs text-gray-500">Starts</div>
                                    </div>
                                    <div className="bg-gray-900/50 rounded p-2">
                                        <div className="text-lg font-bold text-green-400">{horse.wins}</div>
                                        <div className="text-xs text-gray-500">Wins</div>
                                    </div>
                                    <div className="bg-gray-900/50 rounded p-2">
                                        <div className="text-lg font-bold text-yellow-400">{horse.win_percentage}%</div>
                                        <div className="text-xs text-gray-500">Win %</div>
                                    </div>
                                </div>

                                {/* Record */}
                                <p className="text-sm text-gray-400 mb-4">
                                    Record: {horse.wins}-{horse.places}-{horse.shows}
                                </p>

                                {/* Last race info */}
                                {horse.last_race_date && (
                                    <p className="text-xs text-gray-500 mb-4">
                                        Last race: {horse.last_race_date} @ {horse.last_track}
                                    </p>
                                )}

                                <Link
                                    to={`/horse/${horse.id}`}
                                    className="mt-auto w-full block bg-black border border-purple-900/50 hover:bg-purple-900/20 hover:border-purple-500/50 text-purple-300 hover:text-white py-2 rounded-md transition text-center shadow-[0_0_10px_rgba(147,51,234,0.1)]"
                                >
                                    View Profile
                                </Link>
                            </div>
                        ))}
                    </div>

                    {/* Improved Pagination */}
                    {totalPages > 1 && (
                        <div className="flex flex-col sm:flex-row justify-center items-center gap-4 mt-8">
                            {/* Page navigation buttons */}
                            <div className="flex items-center gap-2">
                                <button
                                    onClick={() => setPage(1)}
                                    disabled={page === 1}
                                    className="px-3 py-2 bg-purple-900/30 text-purple-300 rounded disabled:opacity-50 disabled:cursor-not-allowed hover:bg-purple-900/50 transition text-sm"
                                    title="First page"
                                >
                                    ««
                                </button>
                                <button
                                    onClick={() => setPage(p => Math.max(1, p - 1))}
                                    disabled={page === 1}
                                    className="px-3 py-2 bg-purple-900/30 text-purple-300 rounded disabled:opacity-50 disabled:cursor-not-allowed hover:bg-purple-900/50 transition text-sm"
                                >
                                    Prev
                                </button>

                                {/* Page number buttons - show nearby pages */}
                                <div className="hidden sm:flex items-center gap-1">
                                    {[...Array(Math.min(5, totalPages))].map((_, i) => {
                                        let pageNum;
                                        if (totalPages <= 5) {
                                            pageNum = i + 1;
                                        } else if (page <= 3) {
                                            pageNum = i + 1;
                                        } else if (page >= totalPages - 2) {
                                            pageNum = totalPages - 4 + i;
                                        } else {
                                            pageNum = page - 2 + i;
                                        }
                                        return (
                                            <button
                                                key={pageNum}
                                                onClick={() => setPage(pageNum)}
                                                className={`w-10 py-2 rounded text-sm transition ${page === pageNum
                                                    ? 'bg-purple-900/50 text-purple-100 border border-purple-500/40'
                                                    : 'bg-purple-900/30 text-purple-300 hover:bg-purple-900/50'
                                                    }`}
                                            >
                                                {pageNum}
                                            </button>
                                        );
                                    })}
                                </div>

                                <button
                                    onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                                    disabled={page === totalPages}
                                    className="px-3 py-2 bg-purple-900/30 text-purple-300 rounded disabled:opacity-50 disabled:cursor-not-allowed hover:bg-purple-900/50 transition text-sm"
                                >
                                    Next
                                </button>
                                <button
                                    onClick={() => setPage(totalPages)}
                                    disabled={page === totalPages}
                                    className="px-3 py-2 bg-purple-900/30 text-purple-300 rounded disabled:opacity-50 disabled:cursor-not-allowed hover:bg-purple-900/50 transition text-sm"
                                    title="Last page"
                                >
                                    »»
                                </button>
                            </div>

                            {/* Page jump input */}
                            <div className="flex items-center gap-2">
                                <span className="text-gray-400 text-sm">Go to:</span>
                                <input
                                    type="number"
                                    min={1}
                                    max={totalPages}
                                    value={page}
                                    onChange={(e) => {
                                        const val = parseInt(e.target.value);
                                        if (val >= 1 && val <= totalPages) {
                                            setPage(val);
                                        }
                                    }}
                                    className="w-16 px-2 py-1 bg-black border border-purple-900/50 text-white rounded text-center text-sm focus:outline-none focus:border-purple-600"
                                />
                                <span className="text-gray-500 text-sm">of {totalPages}</span>
                            </div>
                        </div>
                    )}
                </>
            )
            }
        </div >
    );
}