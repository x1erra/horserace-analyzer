import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
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

export default function Claims() {
    const [claims, setClaims] = useState([]);
    const [filteredClaims, setFilteredClaims] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [selectedTrack, setSelectedTrack] = useState('All Tracks');
    const [selectedDate, setSelectedDate] = useState('All Dates');
    const [sortConfig, setSortConfig] = useState({ key: 'race_date', direction: 'desc' });

    // Pagination State
    const [currentPage, setCurrentPage] = useState(1);
    const [itemsPerPage, setItemsPerPage] = useState(30);

    // Reset to first page when filters change
    useEffect(() => {
        setCurrentPage(1);
    }, [selectedTrack, selectedDate, sortConfig]);

    const fetchClaims = useCallback(async (isAutoRefresh = false) => {
        try {
            // Strict check to ensure MouseEvents from button clicks don't trigger "auto-refresh" mode
            const showLoading = isAutoRefresh !== true;

            if (showLoading) setLoading(true);
            const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:5001';
            const response = await axios.get(`${baseUrl}/api/claims?limit=200`);

            if (response.data && response.data.claims) {
                setClaims(response.data.claims);
            }
            setError(null);
        } catch (err) {
            console.error("Error fetching claims:", err);
            setError("Failed to load claims data.");
        } finally {
            if (isAutoRefresh !== true) setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchClaims();

        // Auto-refresh every 2 minutes (120000 ms)
        const intervalId = setInterval(() => {
            fetchClaims(true);
        }, 120000);

        return () => clearInterval(intervalId);
    }, [fetchClaims]);

    // Filter and Sort logic
    useEffect(() => {
        let filtered = [...claims];

        // 1. Filter
        if (selectedTrack !== 'All Tracks') {
            filtered = filtered.filter(claim =>
                claim.track_name === selectedTrack || claim.track_code === selectedTrack
            );
        }

        if (selectedDate !== 'All Dates') {
            filtered = filtered.filter(claim => claim.race_date === selectedDate);
        }

        // 2. Sort
        if (sortConfig.key) {
            filtered.sort((a, b) => {
                let aValue = a[sortConfig.key];
                let bValue = b[sortConfig.key];

                // Handle special cases
                if (sortConfig.key === 'claim_price' || sortConfig.key === 'race_number') {
                    aValue = Number(aValue || 0);
                    bValue = Number(bValue || 0);
                } else if (sortConfig.key === 'new_owner') {
                    aValue = (a.new_owner_name || '').toLowerCase();
                    bValue = (b.new_owner_name || '').toLowerCase();
                } else if (sortConfig.key === 'new_trainer') {
                    aValue = (a.new_trainer_name || '').toLowerCase();
                    bValue = (b.new_trainer_name || '').toLowerCase();
                } else if (sortConfig.key === 'created_at') {
                    // String date comparison works for ISO dates
                    aValue = (aValue || '').toString();
                    bValue = (bValue || '').toString();
                } else {
                    // Strings (date, track, horse)
                    aValue = (aValue || '').toString().toLowerCase();
                    bValue = (bValue || '').toString().toLowerCase();
                }

                if (aValue < bValue) {
                    return sortConfig.direction === 'asc' ? -1 : 1;
                }
                if (aValue > bValue) {
                    return sortConfig.direction === 'asc' ? 1 : -1;
                }

                // Secondary sort: Track Name (Alphabetic) - Only if primary sort is Date
                if (sortConfig.key === 'race_date') {
                    const trackA = (a.track_name || a.track_code || '').toLowerCase();
                    const trackB = (b.track_name || b.track_code || '').toLowerCase();
                    if (trackA < trackB) return -1;
                    if (trackA > trackB) return 1;
                }

                // Tertiary sort: Race Number (Always Ascending)
                return Number(a.race_number) - Number(b.race_number);
            });
        }

        setFilteredClaims(filtered);
    }, [selectedTrack, selectedDate, claims, sortConfig]);

    const handleSort = (key) => {
        let direction = 'asc';
        if (sortConfig.key === key && sortConfig.direction === 'asc') {
            direction = 'desc';
        }
        setSortConfig({ key, direction });
    };

    // Calculate Pagination
    const indexOfLastItem = currentPage * itemsPerPage;
    const indexOfFirstItem = indexOfLastItem - itemsPerPage;
    const currentItems = filteredClaims.slice(indexOfFirstItem, indexOfLastItem);
    const totalPages = Math.ceil(filteredClaims.length / itemsPerPage);

    // Change page
    const paginate = (pageNumber) => setCurrentPage(pageNumber);

    // Unique tracks and dates for filters
    const tracks = ['All Tracks', ...new Set(claims.map(c => c.track_name || c.track_code).filter(Boolean))].sort();
    const dates = ['All Dates', ...new Set(claims.map(c => c.race_date).filter(Boolean))].sort().reverse();

    // Initial loading state only (if no data yet)
    if (loading && claims.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center min-h-[400px] text-white">
                <div className="relative">
                    <div className="w-16 h-16 rounded-full border-4 border-purple-900/20 border-t-purple-500 animate-spin"></div>
                    <div className="absolute inset-0 flex items-center justify-center">
                        <div className="w-8 h-8 rounded-full bg-purple-500/10 blur-xl animate-pulse"></div>
                    </div>
                </div>
                <p className="mt-6 text-gray-400 font-medium animate-pulse tracking-wide uppercase text-xs">Initializing Claims...</p>
            </div>
        );
    }

    if (error) return <div className="text-red-400 text-center p-20">{error}</div>;

    return (
        <div className="space-y-8">
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                <div>
                    <h3 className="text-3xl font-bold text-white">Claims</h3>
                    <p className="text-sm text-gray-400 mb-4 sm:mb-0">Review horses claimed in recent races.</p>
                </div>

                <button
                    onClick={() => fetchClaims()}
                    disabled={loading}
                    className="w-full sm:w-auto flex items-center justify-center gap-2 bg-purple-900/30 hover:bg-purple-900/50 text-purple-200 px-4 py-2 rounded-lg border border-purple-500/30 transition-all disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium group"
                >
                    <svg
                        className={`w-4 h-4 ${loading ? 'animate-spin' : 'group-hover:rotate-180 transition-transform duration-500'}`}
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                    >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    {loading ? 'Refreshing...' : 'Refresh'}
                </button>
            </div>



            {/* Filter bar */}
            <div className="flex flex-col gap-4 mb-8">
                <TrackFilter
                    tracks={tracks.filter(t => t !== 'All Tracks').map(t => t)}
                    selectedTrack={selectedTrack === 'All Tracks' ? 'All' : selectedTrack}
                    onSelectTrack={(t) => setSelectedTrack(t === 'All' ? 'All Tracks' : t)}
                />

                <div className="flex items-center gap-2">
                    <span className="text-gray-400 text-sm">Filter by Date:</span>
                    <select
                        value={selectedDate}
                        onChange={(e) => setSelectedDate(e.target.value)}
                        className="bg-black border border-purple-900/30 text-white px-4 py-2 rounded-md focus:outline-none focus:border-purple-600 transition appearance-none"
                    >
                        {dates.map(date => (
                            <option key={date} value={date}>{date}</option>
                        ))}
                    </select>
                </div>
            </div>

            {/* Claims count */}
            <p className="text-sm text-gray-400">
                Showing {filteredClaims.length} claims
                {selectedTrack !== 'All Tracks' && ` from ${selectedTrack}`}
                {selectedDate !== 'All Dates' && ` on ${selectedDate}`}
            </p>

            {/* Claims Table */}
            <div className="bg-black rounded-xl shadow-md overflow-hidden border border-purple-900/50">
                {/* Desktop Table View */}
                <div className="hidden md:block overflow-x-auto">
                    <table className="w-full text-left text-gray-300">
                        <thead className="bg-purple-900/30 border-b border-purple-900/50">
                            <tr>
                                <th
                                    className="p-4 cursor-pointer hover:bg-purple-900/50 transition select-none"
                                    onClick={() => handleSort('race_date')}
                                >
                                    Date {sortConfig.key === 'race_date' && (sortConfig.direction === 'asc' ? '▲' : '▼')}
                                </th>
                                <th
                                    className="p-4 cursor-pointer hover:bg-purple-900/50 transition select-none"
                                    onClick={() => handleSort('track_name')}
                                >
                                    Track {sortConfig.key === 'track_name' && (sortConfig.direction === 'asc' ? '▲' : '▼')}
                                </th>
                                <th
                                    className="p-4 cursor-pointer hover:bg-purple-900/50 transition select-none"
                                    onClick={() => handleSort('race_number')}
                                >
                                    Race {sortConfig.key === 'race_number' && (sortConfig.direction === 'asc' ? '▲' : '▼')}
                                </th>
                                <th
                                    className="p-4 cursor-pointer hover:bg-purple-900/50 transition select-none"
                                    onClick={() => handleSort('horse_name')}
                                >
                                    Horse {sortConfig.key === 'horse_name' && (sortConfig.direction === 'asc' ? '▲' : '▼')}
                                </th>
                                <th
                                    className="p-4 cursor-pointer hover:bg-purple-900/50 transition select-none"
                                    onClick={() => handleSort('new_owner')}
                                >
                                    New Owner / Trainer {sortConfig.key === 'new_owner' && (sortConfig.direction === 'asc' ? '▲' : '▼')}
                                </th>
                                <th
                                    className="p-4 text-right cursor-pointer hover:bg-purple-900/50 transition select-none"
                                    onClick={() => handleSort('claim_price')}
                                >
                                    Price {sortConfig.key === 'claim_price' && (sortConfig.direction === 'asc' ? '▲' : '▼')}
                                </th>
                                <th className="p-4 text-center">Action</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-purple-900/20 relative">
                            {currentItems.length === 0 ? (
                                <tr>
                                    <td colSpan="7" className="p-12 text-center text-gray-500">
                                        {loading ? (
                                            <div className="flex flex-col items-center gap-3">
                                                <div className="w-8 h-8 border-2 border-purple-500/20 border-t-purple-500 rounded-full animate-spin"></div>
                                                <span>Fetching claims...</span>
                                            </div>
                                        ) : (
                                            "No claims found matching your filters."
                                        )}
                                    </td>
                                </tr>
                            ) : (
                                currentItems.map((claim, index) => {
                                    const horseStyle = claim.program_number ? getPostColor(claim.program_number) : null;
                                    return (
                                        <tr
                                            key={claim.id || index}
                                            className="hover:bg-purple-900/10 transition group"
                                        >
                                            <td className="p-4 text-gray-300 font-medium whitespace-nowrap">{claim.race_date}</td>
                                            <td className="p-4">
                                                <span className="inline-flex items-center justify-center px-2.5 py-1 rounded-md bg-purple-900/20 text-purple-300 text-xs font-bold border border-purple-500/30 font-mono">
                                                    {claim.track_code || claim.track_name}
                                                </span>
                                            </td>
                                            <td className="p-4 whitespace-nowrap">
                                                <Link
                                                    to={`/race/${claim.race_key}`}
                                                    className="text-purple-400 hover:text-purple-300 hover:underline transition-colors"
                                                >
                                                    Race {claim.race_number}
                                                </Link>
                                            </td>
                                            <td className="p-4">
                                                <div className="flex items-center gap-3">
                                                    {horseStyle ? (
                                                        <div
                                                            className="w-8 h-8 rounded-md flex-shrink-0 flex items-center justify-center font-bold text-sm shadow-sm leading-none"
                                                            style={{ backgroundColor: horseStyle.bg, color: horseStyle.text }}
                                                        >
                                                            {claim.program_number}
                                                        </div>
                                                    ) : (
                                                        <div className="w-8 h-8 rounded-md bg-gray-800 flex items-center justify-center text-gray-500 text-xs">
                                                            -
                                                        </div>
                                                    )}
                                                    <span className="text-white font-medium group-hover:text-purple-400 transition-colors">
                                                        {claim.horse_name}
                                                    </span>
                                                </div>
                                            </td>
                                            <td className="p-4">
                                                <div className="text-sm">
                                                    <span className="text-gray-500">Owner:</span> {claim.new_owner || 'N/A'}<br />
                                                    <span className="text-gray-500">Trainer:</span> {claim.new_trainer || 'N/A'}
                                                </div>
                                            </td>
                                            <td className="p-4 text-right font-mono text-green-400">
                                                {claim.claim_price ? `$${claim.claim_price.toLocaleString()}` : '-'}
                                            </td>
                                            <td className="p-4 text-center">
                                                <Link
                                                    to={`/race/${claim.race_key}`}
                                                    className="text-purple-400 hover:text-purple-300 hover:underline text-sm font-medium"
                                                >
                                                    View Race
                                                </Link>
                                            </td>
                                        </tr>
                                    );
                                })
                            )}
                        </tbody>
                    </table>
                </div>

                {/* Mobile Card View */}
                <div className="md:hidden">
                    {currentItems.length === 0 ? (
                        <div className="p-12 text-center text-gray-500">
                            {loading ? (
                                <div className="flex flex-col items-center gap-3">
                                    <div className="w-8 h-8 border-2 border-purple-500/20 border-t-purple-500 rounded-full animate-spin"></div>
                                    <span>Fetching claims...</span>
                                </div>
                            ) : (
                                "No claims found matching your filters."
                            )}
                        </div>
                    ) : (
                        <div className="divide-y divide-purple-900/20">
                            {currentItems.map((claim, index) => (
                                <div key={claim.id || index} className="p-4 space-y-3 hover:bg-purple-900/5 transition">
                                    <div className="flex justify-between items-start">
                                        <div>
                                            <div className="font-bold text-white text-lg">{claim.horse_name}</div>
                                            <div className="text-xs text-purple-300 mt-0.5">{claim.track_name} • {claim.race_date}</div>
                                        </div>
                                        <div className="text-green-400 font-mono font-bold text-lg">
                                            {claim.claim_price ? `$${claim.claim_price.toLocaleString()}` : '-'}
                                        </div>
                                    </div>

                                    <div className="grid grid-cols-2 gap-2 text-sm bg-purple-900/10 p-3 rounded-lg border border-purple-900/20">
                                        <div>
                                            <span className="text-gray-500 text-xs uppercase block">New Trainer</span>
                                            <span className="text-gray-300">{claim.new_trainer || 'N/A'}</span>
                                        </div>
                                        <div>
                                            <span className="text-gray-500 text-xs uppercase block">New Owner</span>
                                            <span className="text-gray-300 truncate block">{claim.new_owner || 'N/A'}</span>
                                        </div>
                                    </div>

                                    <div className="flex justify-between items-center pt-1">
                                        <span className="text-xs text-gray-500 font-mono bg-gray-900 px-2 py-1 rounded">Race {claim.race_number}</span>
                                        <Link
                                            to={`/race/${claim.race_key}`}
                                            className="text-purple-400 hover:text-white text-sm font-medium flex items-center gap-1"
                                        >
                                            View Race
                                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                            </svg>
                                        </Link>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {/* Pagination Controls */}
                {filteredClaims.length > 0 && (
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
                )}
            </div>
        </div>
    );
}
