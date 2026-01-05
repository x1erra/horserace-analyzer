import { useState } from 'react';

export default function Results() {
    const [sortColumn, setSortColumn] = useState('date');
    const [sortDirection, setSortDirection] = useState('desc');
    const [searchQuery, setSearchQuery] = useState('');
    const [filteredResults, setFilteredResults] = useState([]);

    // Sample results data (TEMPORARY: Replace with crawled data from script, e.g., via props or state from backend API)
    const allResults = [
        { date: '2026-01-04', track: 'Gulfstream Park', raceNumber: 1, winner: 'Speed Demon', time: '1:45.89', link: 'https://equibase.com/results/1' },
        { date: '2026-01-04', track: 'Gulfstream Park', raceNumber: 2, winner: 'Thunder Bolt', time: '1:38.50', link: 'https://equibase.com/results/2' },
        { date: '2026-01-03', track: 'Aqueduct', raceNumber: 1, winner: 'Lightning Strike', time: '1:42.20', link: 'https://equibase.com/results/3' },
        { date: '2026-01-03', track: 'Santa Anita', raceNumber: 1, winner: 'Shadow Runner', time: '1:40.75', link: 'https://equibase.com/results/4' },
        { date: '2026-01-02', track: 'Gulfstream Park', raceNumber: 5, winner: 'Golden Hoof', time: '1:39.10', link: 'https://equibase.com/results/5' },
        { date: '2026-01-02', track: 'Aqueduct', raceNumber: 3, winner: 'Storm Chaser', time: '1:41.30', link: 'https://equibase.com/results/6' },
    ];

    // Filter and sort logic
    const sortedAndFilteredResults = allResults
        .filter(result => result.track.toLowerCase().includes(searchQuery.toLowerCase()) || result.winner.toLowerCase().includes(searchQuery.toLowerCase()))
        .sort((a, b) => {
            let valA = a[sortColumn];
            let valB = b[sortColumn];
            if (typeof valA === 'string') {
                valA = valA.toLowerCase();
                valB = valB.toLowerCase();
            }
            if (valA < valB) return sortDirection === 'asc' ? -1 : 1;
            if (valA > valB) return sortDirection === 'asc' ? 1 : 1;
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
                <table className="w-full text-left text-gray-300">
                    <thead className="bg-purple-900/50">
                        <tr>
                            <th className="p-4 cursor-pointer hover:bg-purple-900/70 transition duration-200" onClick={() => handleSort('date')}>
                                Date {getArrow('date')}
                            </th>
                            <th className="p-4 cursor-pointer hover:bg-purple-900/70 transition duration-200" onClick={() => handleSort('track')}>
                                Track {getArrow('track')}
                            </th>
                            <th className="p-4 cursor-pointer hover:bg-purple-900/70 transition duration-200" onClick={() => handleSort('raceNumber')}>
                                Race Number {getArrow('raceNumber')}
                            </th>
                            <th className="p-4 cursor-pointer hover:bg-purple-900/70 transition duration-200" onClick={() => handleSort('winner')}>
                                Winner {getArrow('winner')}
                            </th>
                            <th className="p-4 cursor-pointer hover:bg-purple-900/70 transition duration-200" onClick={() => handleSort('time')}>
                                Time {getArrow('time')}
                            </th>
                            <th className="p-4">Details</th>
                        </tr>
                    </thead>
                    <tbody>
                        {sortedAndFilteredResults.length === 0 ? (
                            <tr>
                                <td colSpan="6" className="p-4 text-center text-gray-400">No results available.</td>
                            </tr>
                        ) : (
                            sortedAndFilteredResults.map((result, index) => (
                                <tr key={index} className="border-t border-purple-900/50 hover:bg-purple-900/20 transition duration-200">
                                    <td className="p-4">{result.date}</td>
                                    <td className="p-4">{result.track}</td>
                                    <td className="p-4">{result.raceNumber}</td>
                                    <td className="p-4 text-purple-400">{result.winner}</td>
                                    <td className="p-4">{result.time}</td>
                                    <td className="p-4">
                                        <a href={result.link} target="_blank" rel="noopener noreferrer" className="text-purple-400 hover:text-purple-300 transition duration-200">
                                            View Details
                                        </a>
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}