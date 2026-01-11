import { Link } from 'react-router-dom';
import { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import RecentUploads from '../components/RecentUploads';

export default function Dashboard() {
    const [races, setRaces] = useState([]);
    const [selectedTrack, setSelectedTrack] = useState('All');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchTodaysRaces = async () => {
            try {
                setLoading(true);
                const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:5001';
                const response = await axios.get(`${baseUrl}/api/todays-races`);
                setRaces(response.data.races || []);
                setError(null);
            } catch (err) {
                console.error("Error fetching today's races:", err);
                setError("Failed to load today's races. Is the backend running?");
            } finally {
                setLoading(false);
            }
        };
        fetchTodaysRaces();
    }, []);

    if (loading) {
        return (
            <div className="text-white text-center p-20">
                <div className="inline-block animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-purple-500"></div>
                <p className="mt-4">Loading today's races...</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="text-center p-20">
                <div className="text-red-400 mb-4">{error}</div>
                <Link
                    to="/upload"
                    className="text-purple-400 hover:text-purple-300 underline"
                >
                    Upload a DRF PDF to add today's races
                </Link>
            </div>
        );
    }

    if (races.length === 0) {
        return (
            <div className="space-y-8">
                <h3 className="text-3xl font-bold text-white">
                    Today's Races
                </h3>
                <div className="bg-black rounded-xl shadow-md p-12 border border-purple-900/50 text-center">
                    <p className="text-gray-400 mb-6">
                        No races scheduled for today. Upload a DRF PDF to add today's races.
                    </p>
                    <Link
                        to="/upload"
                        className="inline-block bg-purple-600 hover:bg-purple-700 text-white px-6 py-3 rounded-md transition"
                    >
                        Upload DRF PDF
                    </Link>
                </div>

                <div className="mt-12">
                    <RecentUploads limit={3} compact={true} />
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-8">
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <h3 className="text-3xl font-bold text-white">
                    Today's Races ({races.length})
                </h3>

                <div className="flex flex-wrap gap-2">
                    <button
                        onClick={() => setSelectedTrack('All')}
                        className={`px-4 py-2 rounded-full text-sm font-medium transition ${selectedTrack === 'All'
                                ? 'bg-purple-600 text-white'
                                : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
                            }`}
                    >
                        All Tracks
                    </button>
                    {[...new Set(races.map(r => r.track_name))].sort().map(track => (
                        <button
                            key={track}
                            onClick={() => setSelectedTrack(track)}
                            className={`px-4 py-2 rounded-full text-sm font-medium transition ${selectedTrack === track
                                    ? 'bg-purple-600 text-white'
                                    : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
                                }`}
                        >
                            {track}
                        </button>
                    ))}
                    <Link
                        to="/upload"
                        className="ml-2 bg-gray-800 hover:bg-gray-700 text-purple-400 px-4 py-2 rounded-full text-sm font-medium transition flex items-center gap-2"
                    >
                        <span>+</span> Upload
                    </Link>
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {races
                    .filter(race => selectedTrack === 'All' || race.track_name === selectedTrack)
                    .sort((a, b) => {
                        if (selectedTrack === 'All') {
                            if (a.track_name !== b.track_name) {
                                return a.track_name.localeCompare(b.track_name);
                            }
                        }
                        return a.race_number - b.race_number;
                    })
                    .map((race, index) => (
                        <div
                            key={race.race_key}
                            className="bg-black rounded-xl shadow-md p-6 hover:shadow-xl transition border border-purple-900/50 opacity-0 animate-fadeIn"
                            style={{ animationDelay: `${index * 50}ms` }}
                        >
                            <h4 className="text-xl font-bold text-white mb-2">
                                Race {race.race_number} - {race.track_name}
                            </h4>
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
                            </div>

                            <Link
                                to={`/race/${race.race_key}`}
                                className="w-full block bg-purple-600 hover:bg-purple-700 text-white py-2 rounded-md transition text-center"
                            >
                                View Details
                            </Link>
                        </div>
                    ))}
            </div>

            <div className="mt-12 border-t border-gray-800 pt-8">
                <RecentUploads limit={5} compact={true} />
            </div>
        </div>
    );
}
