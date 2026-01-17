import { useState, useEffect } from 'react';
import axios from 'axios';
import TrackFilter from '../components/TrackFilter';

export default function Results() {
    const [allResults, setAllResults] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [sortColumn, setSortColumn] = useState('race_date');
    const [sortDirection, setSortDirection] = useState('desc');
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedTrack, setSelectedTrack] = useState('All');

    // Derived tracks list from all results
    const tracks = ['All', ...new Set(allResults.map(r => r.track_name).filter(Boolean))].sort();

    // Pagination State
    const [currentPage, setCurrentPage] = useState(1);
    const [itemsPerPage, setItemsPerPage] = useState(30);

    // Reset to first page when search changes
    useEffect(() => {
        setCurrentPage(1);
    }, [searchQuery]);

    useEffect(() => {
        const fetchResults = async () => {
            try {
                setLoading(true);
                const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:5001';
                const response = await axios.get(`${baseUrl}/api/past-races`);
                setAllResults(response.data.races || []);
                setError(null);
            } catch (err) {
                console.error("Error fetching results:", err);
                setError("Failed to load race results. Is the backend running?");
            } finally {
                setLoading(false);
            }
        };
        fetchResults();
    }, []);

    // Filter and sort logic
    const sortedAndFilteredResults = allResults
        .filter(result =>
            (selectedTrack === 'All' || result.track_name === selectedTrack) &&
            ((result.track_name || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
                (result.winner || '').toLowerCase().includes(searchQuery.toLowerCase()))
        )
        .sort((a, b) => {
            let valA = a[sortColumn];
            let valB = b[sortColumn];

            if (valA === undefined || valA === null) valA = '';
            if (valB === undefined || valB === null) valB = '';

            // Numeric check for race_number
            if (sortColumn === 'race_number') {
                valA = Number(valA);
                valB = Number(valB);
            } else if (typeof valA === 'string') {
                valA = valA.toLowerCase();
                valB = valB.toLowerCase();
            }

            if (valA < valB) return sortDirection === 'asc' ? -1 : 1;
            if (valA > valB) return sortDirection === 'asc' ? 1 : -1;

            // Secondary sort: Track Name (Alphabetic) - Only if primary sort is Date
            if (sortColumn === 'race_date') {
                const trackA = (a.track_name || '').toLowerCase();
                const trackB = (b.track_name || '').toLowerCase();
                if (trackA < trackB) return -1;
                if (trackA > trackB) return 1;
            }

            // Tertiary sort: Race Number (Always Ascending)
            return Number(a.race_number || 0) - Number(b.race_number || 0);
        });

    // Handle column sort click
    const handleSort = (column) => {
        if (sortColumn === column) {
            setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
        } else {
            setSortColumn(column);
            setSortDirection('desc');
        }
    };

    // Get arrow for a column
    const getArrow = (column) => sortColumn === column ? (sortDirection === 'asc' ? '▲' : '▼') : null;

    // Calculate Pagination
    const indexOfLastItem = currentPage * itemsPerPage;
    const indexOfFirstItem = indexOfLastItem - itemsPerPage;
    const currentItems = sortedAndFilteredResults.slice(indexOfFirstItem, indexOfLastItem);
    const totalPages = Math.ceil(sortedAndFilteredResults.length / itemsPerPage);

    // Change page
    const paginate = (pageNumber) => setCurrentPage(pageNumber);

    if (loading) {
        return (
            <div className="text-white text-center p-20">
                <div className="inline-block animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-purple-500"></div>
                <p className="mt-4">Loading race results...</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="text-center p-20">
                <div className="text-red-400 mb-4 font-medium">{error}</div>
            </div>
        );
    }

    return (
        <div className="space-y-8">
            <h3 className="text-3xl font-bold text-white">Race Results</h3>
            <p className="text-sm text-gray-400 mb-4">View and search past race results. Data updated daily via crawl.</p>

            {/* Track Filter */}
            <div className="mb-6">
                <TrackFilter
                    tracks={tracks.filter(t => t !== 'All').map(t => t)}
                    selectedTrack={selectedTrack}
                    onSelectTrack={setSelectedTrack}
                />
            </div>

            {/* Search Bar */}
            <input
                type="text"
                placeholder="Search by winner..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-black border border-purple-900/50 text-white px-4 py-3 rounded-md focus:outline-none focus:border-purple-600 transition duration-200 opacity-0 animate-fadeIn" style={{ animationDelay: '50ms' }}
            />

            {/* Results Table */}
            <div className="bg-black rounded-xl shadow-md overflow-hidden border border-purple-900/50 opacity-0 animate-fadeIn" style={{ animationDelay: '100ms' }}>
                {/* Desktop Table View */}
                <div className="hidden md:block overflow-x-auto">
                    <table className="w-full text-left text-gray-300">
                        <thead className="bg-purple-900/30 border-b border-purple-900/50">
                            <tr>
                                <th className="p-4 cursor-pointer hover:bg-purple-900/50 transition duration-200" onClick={() => handleSort('race_date')}>
                                    Date {getArrow('race_date')}
                                </th>
                                <th className="p-4 cursor-pointer hover:bg-purple-900/50 transition duration-200" onClick={() => handleSort('track_name')}>
                                    Track {getArrow('track_name')}
                                </th>
                                <th className="p-4 cursor-pointer hover:bg-purple-900/50 transition duration-200" onClick={() => handleSort('race_number')}>
                                    Race {getArrow('race_number')}
                                </th>
                                <th className="p-4 cursor-pointer hover:bg-purple-900/50 transition duration-200" onClick={() => handleSort('winner')}>
                                    Winner {getArrow('winner')}
                                </th>
                                <th className="p-4">Details</th>
                            </tr>
                        </thead>
                        <tbody>
                            {currentItems.length === 0 ? (
                                <tr>
                                    <td colSpan="7" className="p-8 text-center text-gray-500 italic">No race results found.</td>
                                </tr>
                            ) : (
                                currentItems.map((result, index) => (
                                    <tr key={result.race_key || index} className="border-t border-purple-900/20 hover:bg-purple-900/10 transition duration-200">
                                        <td className="p-4">{result.race_date}</td>
                                        <td className="p-4">{result.track_name}</td>
                                        <td className="p-4">{result.race_number}</td>
                                        <td className="p-4 text-purple-400 font-medium">{result.winner || 'N/A'}</td>
                                        <td className="p-4">
                                            {result.link && result.link !== '#' ? (
                                                <a href={result.link} target="_blank" rel="noopener noreferrer" className="text-purple-500 hover:text-purple-400 transition duration-200 flex items-center gap-1">
                                                    Chart
                                                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                                                    </svg>
                                                </a>
                                            ) : (
                                                <span className="text-gray-600">N/A</span>
                                            )}
                                        </td>
                                    </tr>
                                ))
                            )}
                        </tbody>
                    </table>
                </div>

                {/* Mobile Card View */}
                <div className="md:hidden">
                    {currentItems.length === 0 ? (
                        <div className="p-8 text-center text-gray-500 italic">No race results found.</div>
                    ) : (
                        <div className="divide-y divide-purple-900/20">
                            {currentItems.map((result, index) => (
                                <div key={result.race_key || index} className="p-4 space-y-3 hover:bg-purple-900/5 transition">
                                    <div className="flex justify-between items-start">
                                        <div>
                                            <div className="font-bold text-white text-lg">{result.track_name}</div>
                                            <div className="text-xs text-gray-400 mt-0.5">{result.race_date}</div>
                                        </div>
                                        <div className="bg-purple-900/30 text-purple-300 text-xs font-mono px-2 py-1 rounded">
                                            Race {result.race_number}
                                        </div>
                                    </div>

                                    <div className="flex justify-between items-center bg-purple-900/10 p-3 rounded-lg border border-purple-900/20">
                                        <div>
                                            <span className="text-gray-500 text-xs uppercase block">Winner</span>
                                            <span className="text-purple-300 font-bold">{result.winner || 'N/A'}</span>
                                        </div>
                                        {result.link && result.link !== '#' && (
                                            <a href={result.link} target="_blank" rel="noopener noreferrer" className="bg-purple-900/40 text-purple-100 border border-purple-500/30 hover:bg-purple-800/50 hover:border-purple-500/50 text-xs font-bold px-3 py-1.5 rounded-lg transition flex items-center gap-1 shadow-[0_0_10px_rgba(147,51,234,0.1)]">
                                                Chart
                                                <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                                                </svg>
                                            </a>
                                        )}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

                {/* Pagination Controls */}
                {sortedAndFilteredResults.length > 0 && (
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
