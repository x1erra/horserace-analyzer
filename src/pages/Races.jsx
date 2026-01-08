import { Link } from 'react-router-dom';
import { useState, useEffect } from 'react';
import axios from 'axios';

export default function Races() {
    const [selectedTrack, setSelectedTrack] = useState('All Tracks');
    const [selectedDate, setSelectedDate] = useState('All Dates');
    const [allRaces, setAllRaces] = useState([]);
    const [filteredRaces, setFilteredRaces] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // Fetch live data from backend
    useEffect(() => {
        const fetchRaces = async () => {
            try {
                setLoading(true);
                const response = await axios.get('http://localhost:5001/api/race-data');
                // Support both {races: []} and {data: {races: []}} formats
                const raceData = response.data.races || response.data.data?.races || [];
                setAllRaces(raceData);
                setError(null);
            } catch (err) {
                console.error("Error fetching races:", err);
                setError("Failed to load race data. Is the backend running?");
            } finally {
                setLoading(false);
            }
        };
        fetchRaces();
    }, []);

    // Filter logic
    useEffect(() => {
        let filtered = allRaces;

        if (selectedTrack !== 'All Tracks') {
            filtered = filtered.filter(race => race.track === selectedTrack);
        }

        if (selectedDate !== 'All Dates') {
            filtered = filtered.filter(race => race.date === selectedDate);
        }

        setFilteredRaces(filtered);
    }, [selectedTrack, selectedDate, allRaces]);

    // Unique tracks and dates for filters
    const tracks = ['All Tracks', ...new Set(allRaces.map(r => r.track).filter(Boolean))].sort();
    const dates = ['All Dates', ...new Set(allRaces.map(r => r.date).filter(Boolean))].sort();

    if (loading) return <div className="text-white text-center p-20">Loading real records...</div>;
    if (error) return <div className="text-red-400 text-center p-20">{error}</div>;

    return (
        <div className="space-y-8">
            <h3 className="text-3xl font-bold text-white">All Races</h3>
            <p className="text-sm text-gray-400 mb-4">Browse and filter live data from Equibase and DRF.</p>

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

            {/* Grid of race cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {filteredRaces.length === 0 ? (
                    <p className="text-gray-400 col-span-full text-center">No races match your filters.</p>
                ) : (
                    filteredRaces.map((race, index) => (
                        <div
                            key={`${race.id}-${index}`}
                            className="bg-black rounded-xl shadow-md p-6 hover:shadow-xl transition border border-purple-900/50 opacity-0 animate-fadeIn"
                            style={{ animationDelay: `${index % 10 * 50}ms` }}
                        >
                            <h4 className="text-xl font-bold text-white mb-2">
                                {race.name}
                            </h4>
                            <p className="text-sm text-gray-400 mb-4">{race.date} • {race.time || 'N/A'}</p>
                            <div className="text-xl font-bold text-purple-400 mb-4 leading-tight">
                                Winner: {race.topPick || 'TBD'}
                            </div>
                            <p className="text-lg text-purple-300 mb-6">
                                {race.track}
                            </p>
                            <Link
                                to={`/race/${race.id}`}
                                className="w-full block bg-purple-600 hover:bg-purple-700 text-white py-2 rounded-md transition text-center"
                            >
                                Analyze
                            </Link>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}