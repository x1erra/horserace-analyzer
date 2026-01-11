import { Link } from 'react-router-dom';
import { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import RecentUploads from '../components/RecentUploads';

export default function Dashboard() {
    const [races, setRaces] = useState([]);
    const [selectedTrack, setSelectedTrack] = useState('All');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [hasLoaded, setHasLoaded] = useState(false);

    const [availableTracks, setAvailableTracks] = useState(['All']);
    const [metaLoading, setMetaLoading] = useState(true);

    // Fetch today's tracks metadata on mount
    useEffect(() => {
        const fetchMetadata = async () => {
            try {
                const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:5001';
                const response = await axios.get(`${baseUrl}/api/filter-options`);

                if (response.data) {
                    setAvailableTracks(['All', ...response.data.today_tracks]);
                }
            } catch (err) {
                console.error("Error fetching filter options:", err);
            } finally {
                setMetaLoading(false);
            }
        };
        fetchMetadata();
    }, []);

    const handleLoadData = async () => {
        try {
            setLoading(true);
            setHasLoaded(true);
            setError(null);

            const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:5001';
            const params = {};
            if (selectedTrack !== 'All') {
                params.track = selectedTrack;
            }

            const response = await axios.get(`${baseUrl}/api/todays-races`, { params });
            setRaces(response.data.races || []);
        } catch (err) {
            console.error("Error fetching today's races:", err);
            setError("Failed to load today's races. Is the backend running?");
        } finally {
            setLoading(false);
        }
    };

    if (metaLoading) {
        return (
            <div className="text-white text-center p-20">
                <div className="inline-block animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-purple-500"></div>
                <p className="mt-4">Loading dashboard...</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="text-center p-20">
                <div className="text-red-400 mb-4">{error}</div>
                <button
                    onClick={handleLoadData}
                    className="text-purple-400 hover:text-purple-300 underline"
                >
                    Try Again
                </button>
            </div>
        );
    }

    return (
        <div className="space-y-8">
            <div className="space-y-6">
                <div className="flex justify-between items-center">
                    <h3 className="text-3xl font-bold text-white">
                        Today's Races {hasLoaded && `(${races.length})`}
                    </h3>
                    <Link
                        to="/upload"
                        className="bg-purple-600 hover:bg-purple-700 text-white px-5 py-2.5 rounded-lg transition text-sm font-medium flex items-center gap-2 shadow-lg shadow-purple-900/20"
                    >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                        </svg>
                        Upload PDF
                    </Link>
                </div>

                <div className="flex flex-col md:flex-row gap-4 items-end bg-black p-4 rounded-xl border border-purple-900/30">
                    <div className="flex-1 w-full space-y-2">
                        <label className="text-gray-400 text-sm ml-1">Filter by Track:</label>
                        <div className="flex flex-wrap gap-2">
                            {availableTracks.map(track => (
                                <button
                                    key={track}
                                    onClick={() => setSelectedTrack(track)}
                                    className={`px-4 py-2 rounded-full text-sm font-medium transition border ${selectedTrack === track
                                        ? 'bg-purple-600 text-white border-purple-600'
                                        : 'bg-transparent text-gray-400 border-gray-800 hover:border-gray-600 hover:text-gray-200'
                                        }`}
                                >
                                    {track}
                                </button>
                            ))}
                        </div>
                    </div>

                    <button
                        onClick={handleLoadData}
                        disabled={loading}
                        className="bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white px-6 py-2.5 rounded-lg transition font-bold flex items-center gap-2 shadow-lg h-10 mb-1 whitespace-nowrap"
                    >
                        {loading ? (
                            <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                        ) : (
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                            </svg>
                        )}
                        {hasLoaded ? 'Refresh Data' : 'Load Races'}
                    </button>
                </div>
            </div>

            {!hasLoaded ? (
                <div className="text-center p-20 bg-black rounded-xl border border-purple-900/30 border-dashed">
                    <p className="text-gray-500 mb-4">Click "Load Races" to view today's schedule</p>
                </div>
            ) : races.length === 0 ? (
                <div className="bg-black rounded-xl shadow-md p-12 border border-purple-900/50 text-center">
                    <p className="text-gray-400 mb-6">
                        No races found for today with selected filters.
                    </p>
                    <Link
                        to="/upload"
                        className="text-purple-400 hover:text-purple-300 underline"
                    >
                        Upload a DRF PDF to add today's races
                    </Link>
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {races
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
            )}

            <div className="mt-12 border-t border-gray-800 pt-8">
                <RecentUploads limit={5} compact={true} />
            </div>
        </div>
    );
}
