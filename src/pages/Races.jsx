import { Link } from 'react-router-dom';
import { useState, useEffect } from 'react';
import axios from 'axios';

export default function Races() {
    const [activeTab, setActiveTab] = useState('past'); // 'today' or 'past'
    const [selectedTrack, setSelectedTrack] = useState('All Tracks');
    const [selectedDate, setSelectedDate] = useState('All Dates');
    const [allRaces, setAllRaces] = useState([]);
    const [filteredRaces, setFilteredRaces] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // Fetch races based on active tab
    useEffect(() => {
        const fetchRaces = async () => {
            try {
                setLoading(true);
                const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:5001';
                const endpoint = activeTab === 'today'
                    ? `${baseUrl}/api/todays-races`
                    : `${baseUrl}/api/past-races?limit=100`;

                const response = await axios.get(endpoint);
                const raceData = response.data.races || [];
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
    }, [activeTab]);

    // Filter logic
    useEffect(() => {
        let filtered = allRaces;

        if (selectedTrack !== 'All Tracks') {
            filtered = filtered.filter(race =>
                race.track_name === selectedTrack || race.track_code === selectedTrack
            );
        }

        if (selectedDate !== 'All Dates') {
            filtered = filtered.filter(race => race.race_date === selectedDate);
        }

        setFilteredRaces(filtered);
    }, [selectedTrack, selectedDate, allRaces]);

    // Unique tracks and dates for filters
    const tracks = ['All Tracks', ...new Set(allRaces.map(r => r.track_name || r.track_code).filter(Boolean))].sort();
    const dates = ['All Dates', ...new Set(allRaces.map(r => r.race_date).filter(Boolean))].sort().reverse();

    if (loading) {
        return (
            <div className="text-white text-center p-20">
                <div className="inline-block animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-purple-500"></div>
                <p className="mt-4">Loading races...</p>
            </div>
        );
    }

    if (error) return <div className="text-red-400 text-center p-20">{error}</div>;

    return (
        <div className="space-y-8">
            <h3 className="text-3xl font-bold text-white">All Races</h3>
            <p className="text-sm text-gray-400 mb-4">Browse upcoming races and historical results.</p>

            {/* Tab selector */}
            <div className="flex gap-4 border-b border-purple-900/50">
                <button
                    onClick={() => {
                        setActiveTab('today');
                        setSelectedTrack('All Tracks');
                        setSelectedDate('All Dates');
                    }}
                    className={`px-6 py-3 font-medium transition ${activeTab === 'today'
                        ? 'text-purple-400 border-b-2 border-purple-400'
                        : 'text-gray-400 hover:text-white'
                        }`}
                >
                    Today's Races
                </button>
                <button
                    onClick={() => {
                        setActiveTab('past');
                        setSelectedTrack('All Tracks');
                        setSelectedDate('All Dates');
                    }}
                    className={`px-6 py-3 font-medium transition ${activeTab === 'past'
                        ? 'text-purple-400 border-b-2 border-purple-400'
                        : 'text-gray-400 hover:text-white'
                        }`}
                >
                    Past Races
                </button>
            </div>

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
                {activeTab === 'past' && (
                    <select
                        value={selectedDate}
                        onChange={(e) => setSelectedDate(e.target.value)}
                        className="w-full md:w-auto bg-black border border-purple-900/50 text-white px-4 py-3 rounded-md focus:outline-none focus:border-purple-600 transition"
                    >
                        {dates.map(date => (
                            <option key={date} value={date}>{date}</option>
                        ))}
                    </select>
                )}
            </div>

            {/* Results count */}
            <p className="text-sm text-gray-400">
                Showing {filteredRaces.length} {activeTab === 'today' ? "today's" : 'past'} races
                {selectedTrack !== 'All Tracks' && ` from ${selectedTrack}`}
                {selectedDate !== 'All Dates' && ` on ${selectedDate}`}
            </p>

            {/* Grid of race cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {filteredRaces.length === 0 ? (
                    <div className="col-span-full text-center p-12 bg-black rounded-xl border border-purple-900/50">
                        <p className="text-gray-400 mb-4">
                            {activeTab === 'today'
                                ? "No races scheduled for today. Upload a DRF PDF to add races."
                                : "No races match your filters."}
                        </p>
                        {activeTab === 'today' && (
                            <Link
                                to="/upload"
                                className="inline-block bg-purple-600 hover:bg-purple-700 text-white px-6 py-3 rounded-md transition"
                            >
                                Upload DRF PDF
                            </Link>
                        )}
                    </div>
                ) : (
                    filteredRaces.map((race, index) => (
                        <div
                            key={race.race_key || `${race.track_code}-${race.race_number}-${index}`}
                            className="bg-black rounded-xl shadow-md p-6 hover:shadow-xl transition border border-purple-900/50 opacity-0 animate-fadeIn h-full flex flex-col"
                            style={{ animationDelay: `${index % 12 * 50}ms` }}
                        >
                            <div className="flex justify-between items-start mb-2">
                                <h4 className="text-xl font-bold text-white">
                                    Race {race.race_number} - {race.track_name || race.track_code}
                                </h4>
                                {race.race_status && (
                                    <span className={`text-xs px-2 py-1 rounded ${race.race_status === 'completed'
                                        ? 'bg-green-900/30 text-green-400'
                                        : race.race_status === 'upcoming'
                                            ? 'bg-blue-900/30 text-blue-400'
                                            : 'bg-gray-900/30 text-gray-400'
                                        }`}>
                                        {race.race_status === 'completed' ? 'Complete' :
                                            race.race_status === 'upcoming' ? 'Upcoming' : 'Past'}
                                    </span>
                                )}
                            </div>

                            <p className="text-sm text-gray-400 mb-4">
                                {race.race_date} • {race.post_time || 'TBD'}
                            </p>

                            <div className="space-y-2 mb-4">
                                {race.race_type && (
                                    <p className="text-sm text-purple-300">
                                        {race.race_type} • {race.surface}
                                    </p>
                                )}
                                {race.distance && (
                                    <p className="text-sm text-gray-400">
                                        {race.distance}
                                    </p>
                                )}
                                {race.purse && (
                                    <p className="text-sm text-green-400">
                                        Purse: {race.purse}
                                    </p>
                                )}
                                <p className="text-sm text-gray-400">
                                    {race.entry_count} entries
                                </p>
                                {race.data_source && (
                                    <p className="text-xs text-gray-500">
                                        Source: {race.data_source === 'drf' ? 'DRF Upload' : 'Equibase'}
                                    </p>
                                )}
                            </div>

                            <Link
                                to={`/race/${race.race_key}`}
                                className="w-full block bg-purple-600 hover:bg-purple-700 text-white py-2 rounded-md transition text-center mt-auto"
                            >
                                {activeTab === 'today' ? 'View Details' : 'View Results'}
                            </Link>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}
