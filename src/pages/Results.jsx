import { useState, useEffect } from 'react';
import axios from 'axios';

export default function Results() {
    const [allResults, setAllResults] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [sortColumn, setSortColumn] = useState('race_date');
    const [sortDirection, setSortDirection] = useState('desc');
    const [searchQuery, setSearchQuery] = useState('');

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
            (result.track_name || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
            (result.winner || '').toLowerCase().includes(searchQuery.toLowerCase())
        )
        .sort((a, b) => {
            let valA = a[sortColumn];
            let valB = b[sortColumn];

            if (valA === undefined || valA === null) valA = '';
            if (valB === undefined || valB === null) valB = '';

            if (typeof valA === 'string') {
                valA = valA.toLowerCase();
                valB = valB.toLowerCase();
            }
            if (valA < valB) return sortDirection === 'asc' ? -1 : 1;
            if (valA > valB) return sortDirection === 'asc' ? 1 : -1;
            return 0;
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

            {/* Search Bar */}
            <input
                type="text"
                placeholder="Search by track or winner..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-black border border-purple-900/50 text-white px-4 py-3 rounded-md focus:outline-none focus:border-purple-600 transition duration-200 opacity-0 animate-fadeIn" style={{ animationDelay: '50ms' }}
            />

            {/* Results Table */}
            <div className="bg-black rounded-xl shadow-md overflow-hidden border border-purple-900/50 opacity-0 animate-fadeIn" style={{ animationDelay: '100ms' }}>
                <div className="overflow-x-auto">
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
                                <th className="p-4 cursor-pointer hover:bg-purple-900/50 transition duration-200" onClick={() => handleSort('time')}>
                                    Time {getArrow('time')}
                                </th>
                                <th className="p-4">Details</th>
                            </tr>
                        </thead>
                        <tbody>
                            {sortedAndFilteredResults.length === 0 ? (
                                <tr>
                                    <td colSpan="6" className="p-8 text-center text-gray-500 italic">No race results found.</td>
                                </tr>
                            ) : (
                                sortedAndFilteredResults.map((result, index) => (
                                    <tr key={result.race_key || index} className="border-t border-purple-900/20 hover:bg-purple-900/10 transition duration-200">
                                        <td className="p-4">{result.race_date}</td>
                                        <td className="p-4">{result.track_name}</td>
                                        <td className="p-4">{result.race_number}</td>
                                        <td className="p-4 text-purple-400 font-medium">{result.winner || 'N/A'}</td>
                                        <td className="p-4 font-mono text-sm">{result.time || 'N/A'}</td>
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
            </div>
        </div>
    );
}
