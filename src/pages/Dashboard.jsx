import { Link } from 'react-router-dom';
import { useState, useEffect } from 'react';
import axios from 'axios';

export default function Dashboard() {
    const [races, setRaces] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchTodaysRaces = async () => {
            try {
                setLoading(true);
                const response = await axios.get('http://localhost:5001/api/todays-races');
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
            </div>
        );
    }

    return (
        <div className="space-y-8">
            <div className="flex justify-between items-center">
                <h3 className="text-3xl font-bold text-white">
                    Today's Races ({races.length})
                </h3>
                <Link
                    to="/upload"
                    className="bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded-md transition text-sm"
                >
                    Upload More
                </Link>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {races.map((race, index) => (
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
        </div>
    );
}
