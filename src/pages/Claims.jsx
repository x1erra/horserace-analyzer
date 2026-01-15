import { useState, useEffect } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';

export default function Claims() {
    const [claims, setClaims] = useState([]);
    const [filteredClaims, setFilteredClaims] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [selectedTrack, setSelectedTrack] = useState('All Tracks');
    const [selectedDate, setSelectedDate] = useState('All Dates');
    const [sortConfig, setSortConfig] = useState({ key: 'race_date', direction: 'desc' });

    useEffect(() => {
        const fetchClaims = async () => {
            try {
                setLoading(true);
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
                setLoading(false);
            }
        };

        fetchClaims();
    }, []);

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

    // Unique tracks and dates for filters
    const tracks = ['All Tracks', ...new Set(claims.map(c => c.track_name || c.track_code).filter(Boolean))].sort();
    const dates = ['All Dates', ...new Set(claims.map(c => c.race_date).filter(Boolean))].sort().reverse();

    if (loading) {
        return (
            <div className="text-white text-center p-20">
                <div className="inline-block animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-purple-500"></div>
                <p className="mt-4">Loading claims...</p>
            </div>
        );
    }

    if (error) return <div className="text-red-400 text-center p-20">{error}</div>;

    // Pagination State
    const [currentPage, setCurrentPage] = useState(1);
    const [itemsPerPage, setItemsPerPage] = useState(30);

    // Reset to first page when filters change
    useEffect(() => {
        setCurrentPage(1);
    }, [selectedTrack, selectedDate, sortConfig]);

    // Calculate Pagination
    const indexOfLastItem = currentPage * itemsPerPage;
    const indexOfFirstItem = indexOfLastItem - itemsPerPage;
    const currentItems = filteredClaims.slice(indexOfFirstItem, indexOfLastItem);
    const totalPages = Math.ceil(filteredClaims.length / itemsPerPage);

    // Change page
    const paginate = (pageNumber) => setCurrentPage(pageNumber);

    return (
        <div className="space-y-8">
            <h3 className="text-3xl font-bold text-white">Claims</h3>
            <p className="text-sm text-gray-400 mb-4">Review horses claimed in recent races.</p>

            {/* Filter bar */}
            <div className="flex flex-col md:flex-row gap-4 mb-8">
                <select
                    value={selectedTrack}
                    onChange={(e) => setSelectedTrack(e.target.value)}
                    className="w-full md:w-auto bg-black border border-purple-900/50 text-white px-4 py-3 rounded-md focus:outline-none focus:border-purple-600 transition"
                >
                    {tracks.map(track => (
                        <option key={track} value={track}>{track}</option>
                    ))}
                </select>
                <select
                    value={selectedDate}
                    onChange={(e) => setSelectedDate(e.target.value)}
                    className="w-full md:w-auto bg-black border border-purple-900/50 text-white px-4 py-3 rounded-md focus:outline-none focus:border-purple-600 transition"
                >
                    {dates.map(date => (
                        <option key={date} value={date}>{date}</option>
                    ))}
                </select>
            </div>

            {/* Claims count */}
            <p className="text-sm text-gray-400">
                Showing {filteredClaims.length} claims
                {selectedTrack !== 'All Tracks' && ` from ${selectedTrack}`}
                {selectedDate !== 'All Dates' && ` on ${selectedDate}`}
            </p>

            {/* Claims Table */}
            <div className="bg-black rounded-xl shadow-md overflow-hidden border border-purple-900/50">
                <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                        <thead>
                            <tr className="bg-gray-900/50 border-b border-purple-900/30 text-gray-400 text-sm uppercase">
                                <th
                                    className="p-4 font-semibold cursor-pointer hover:text-purple-400 transition select-none"
                                    onClick={() => handleSort('race_date')}
                                >
                                    Date {sortConfig.key === 'race_date' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                                </th>
                                <th
                                    className="p-4 font-semibold cursor-pointer hover:text-purple-400 transition select-none"
                                    onClick={() => handleSort('track_name')}
                                >
                                    Track {sortConfig.key === 'track_name' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                                </th>
                                <th
                                    className="p-4 font-semibold cursor-pointer hover:text-purple-400 transition select-none"
                                    onClick={() => handleSort('race_number')}
                                >
                                    Race {sortConfig.key === 'race_number' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                                </th>
                                <th
                                    className="p-4 font-semibold cursor-pointer hover:text-purple-400 transition select-none"
                                    onClick={() => handleSort('horse_name')}
                                >
                                    Horse {sortConfig.key === 'horse_name' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                                </th>
                                <th
                                    className="p-4 font-semibold cursor-pointer hover:text-purple-400 transition select-none"
                                    onClick={() => handleSort('new_owner')}
                                >
                                    New Owner / Trainer {sortConfig.key === 'new_owner' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                                </th>
                                <th
                                    className="p-4 font-semibold text-right cursor-pointer hover:text-purple-400 transition select-none"
                                    onClick={() => handleSort('claim_price')}
                                >
                                    Price {sortConfig.key === 'claim_price' && (sortConfig.direction === 'asc' ? '↑' : '↓')}
                                </th>
                                <th className="p-4 font-semibold text-center">Action</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-purple-900/20">
                            {loading ? (
                                <tr>
                                    <td colSpan="7" className="p-8 text-center text-gray-500">
                                        <div className="inline-block animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-purple-500 mb-2"></div>
                                        <p>Loading claims...</p>
                                    </td>
                                </tr>
                            ) : currentItems.length === 0 ? (
                                <tr>
                                    <td colSpan="7" className="p-8 text-center text-gray-500">
                                        No claims found matching your filters.
                                    </td>
                                </tr>
                            ) : (
                                currentItems.map((claim, index) => (
                                    <tr
                                        key={claim.id || index}
                                        className="hover:bg-purple-900/10 transition text-gray-300"
                                    >
                                        <td className="p-4 whitespace-nowrap">{claim.race_date}</td>
                                        <td className="p-4 whitespace-nowrap">{claim.track_name}</td>
                                        <td className="p-4 whitespace-nowrap">Race {claim.race_number}</td>
                                        <td className="p-4 font-medium text-white">{claim.horse_name}</td>
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
                                                className="text-purple-400 hover:text-purple-300 text-sm font-medium"
                                            >
                                                View Race
                                            </Link>
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
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
                                className="mx-2 bg-purple-900/20 border border-purple-900/50 text-white text-xs rounded px-2 py-1 focus:outline-none focus:border-purple-500"
                            >
                                <option value={10}>10</option>
                                <option value={20}>20</option>
                                <option value={30}>30</option>
                                <option value={50}>50</option>
                                <option value={100}>100</option>
                            </select>
                            <span>results per page</span>
                        </div>

                        <div className="flex items-center gap-2">
                            <button
                                onClick={() => paginate(currentPage - 1)}
                                disabled={currentPage === 1}
                                className={`px-3 py-1 rounded text-sm font-medium transition ${currentPage === 1
                                        ? 'bg-gray-800 text-gray-600 cursor-not-allowed'
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
                                        ? 'bg-gray-800 text-gray-600 cursor-not-allowed'
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
