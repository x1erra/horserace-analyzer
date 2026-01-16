import { Link } from 'react-router-dom';
import { useState, useEffect } from 'react';
import axios from 'axios';
import RaceCard from '../components/RaceCard';

export default function Races() {
    const [activeTab, setActiveTab] = useState('today'); // 'today' or 'past'
    const [selectedTrack, setSelectedTrack] = useState('All'); // Changed default to 'All'
    const [selectedDate, setSelectedDate] = useState('All Dates');
    const [allRaces, setAllRaces] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [hasSearched, setHasSearched] = useState(false);

    // Metadata for filters
    const [availableTracks, setAvailableTracks] = useState([{ name: 'All Tracks', code: 'All' }]);
    const [availableDates, setAvailableDates] = useState(['All Dates']);
    const [metaLoading, setMetaLoading] = useState(true);

    // Fetch filter metadata on mount
    useEffect(() => {
        const fetchMetadata = async () => {
            try {
                const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:5001';
                const response = await axios.get(`${baseUrl}/api/filter-options`);

                if (response.data) {
                    setAvailableTracks([{ name: 'All Tracks', code: 'All' }, ...response.data.tracks]);
                    setAvailableDates(['All Dates', ...response.data.dates]);
                }
            } catch (err) {
                console.error("Error fetching filter options:", err);
            } finally {
                setMetaLoading(false);
            }
        };
        fetchMetadata();
    }, []);

    // Reset state when tab changes
    const handleTabChange = (tab) => {
        setActiveTab(tab);
        setSelectedTrack('All');
        setSelectedDate('All Dates');
        setAllRaces([]);
        setHasSearched(false);
        setError(null);
    };

    const handleSearch = async () => {
        try {
            setLoading(true);
            setHasSearched(true);
            setError(null);

            const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:5001';
            const endpoint = activeTab === 'today'
                ? `${baseUrl}/api/todays-races`
                : `${baseUrl}/api/past-races`;

            const params = {};

            if (activeTab === 'today') {
                // Dashboard filter logic style
                if (selectedTrack !== 'All') params.track = selectedTrack;
            } else {
                // Past races logic
                params.limit = 100;
                if (selectedTrack !== 'All') params.track = selectedTrack;
                if (selectedDate !== 'All Dates') {
                    params.start_date = selectedDate;
                    params.end_date = selectedDate;
                }
            }

            // Add cache buster
            params._t = Date.now();

            const response = await axios.get(endpoint, { params });
            const raceData = response.data.races || [];
            setAllRaces(raceData);

        } catch (err) {
            console.error("Error fetching races:", err);
            setError("Failed to load race data. Is the backend running?");
        } finally {
            setLoading(false);
        }
    };

    if (metaLoading) {
        return (
            <div className="text-white text-center p-20">
                <div className="inline-block animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-purple-500"></div>
                <p className="mt-4">Loading options...</p>
            </div>
        );
    }

    return (
        <div className="space-y-8">
            <h3 className="text-3xl font-bold text-white">All Races</h3>
            <p className="text-sm text-gray-400 mb-4">Browse upcoming races and historical results.</p>

            {/* Tab selector */}
            <div className="flex gap-4 border-b border-purple-900/50">
                <button
                    onClick={() => handleTabChange('today')}
                    className={`px-6 py-3 font-medium transition ${activeTab === 'today'
                        ? 'text-purple-400 border-b-2 border-purple-400'
                        : 'text-gray-400 hover:text-white'
                        }`}
                >
                    Today's Races
                </button>
                <button
                    onClick={() => handleTabChange('past')}
                    className={`px-6 py-3 font-medium transition ${activeTab === 'past'
                        ? 'text-purple-400 border-b-2 border-purple-400'
                        : 'text-gray-400 hover:text-white'
                        }`}
                >
                    Past Races
                </button>
            </div>

            {/* Filter bar */}
            <div className="bg-black/50 p-4 rounded-xl border border-purple-900/20 flex flex-col md:flex-row gap-4 items-end">
                <div className="flex-1 w-full grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label className="block text-xs font-semibold text-gray-500 mb-1 ml-1 uppercase">Track</label>
                        <select
                            value={selectedTrack}
                            onChange={(e) => setSelectedTrack(e.target.value)}
                            className="w-full bg-black border border-gray-800 text-white px-4 py-2.5 rounded-lg focus:outline-none focus:border-purple-600 transition"
                        >
                            {availableTracks.map(track => (
                                <option key={track.code} value={track.code}>{track.name}</option>
                            ))}
                        </select>
                    </div>

                    {activeTab === 'past' && (
                        <div>
                            <label className="block text-xs font-semibold text-gray-500 mb-1 ml-1 uppercase">Date</label>
                            <select
                                value={selectedDate}
                                onChange={(e) => setSelectedDate(e.target.value)}
                                className="w-full bg-black border border-gray-800 text-white px-4 py-2.5 rounded-lg focus:outline-none focus:border-purple-600 transition"
                            >
                                {availableDates.map(date => (
                                    <option key={date} value={date}>{date}</option>
                                ))}
                            </select>
                        </div>
                    )}
                </div>

                <button
                    onClick={handleSearch}
                    disabled={loading}
                    className="w-full md:w-auto bg-black border border-purple-600 hover:bg-purple-900/20 hover:border-purple-500 disabled:opacity-50 text-white px-8 py-2.5 rounded-lg transition font-bold flex items-center justify-center gap-2 h-[42px] shadow-[0_0_15px_rgba(147,51,234,0.3)]"
                >
                    {loading ? (
                        <>
                            <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                            Loading...
                        </>
                    ) : (
                        <>
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                            </svg>
                            Search
                        </>
                    )}
                </button>
            </div>

            {error && <div className="text-red-400 text-center p-4 bg-red-900/20 rounded-lg">{error}</div>}

            {/* Results */}
            {loading ? (
                <div className="text-center p-20">
                    <div className="inline-block animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-purple-500"></div>
                    <p className="mt-4 text-gray-400">Loading races...</p>
                </div>
            ) : !hasSearched ? (
                <div className="text-center p-20 bg-black rounded-xl border border-purple-900/30 border-dashed">
                    <p className="text-gray-500">Select filters and click Search to view races</p>
                </div>
            ) : (
                <>
                    {/* Results count */}
                    <p className="text-sm text-gray-400 mb-4">
                        Found {allRaces.length} {activeTab === 'today' ? "today's" : 'past'} races
                    </p>

                    {/* Grid of race cards */}
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 animate-fadeIn">
                        {allRaces.length === 0 ? (
                            <div className="col-span-full text-center p-12 bg-black rounded-xl border border-purple-900/50">
                                <p className="text-gray-400 mb-4">
                                    {activeTab === 'today'
                                        ? "No races found matching your criteria."
                                        : "No past races found matching your criteria."}
                                </p>
                            </div>
                        ) : (
                            allRaces.map((race, index) => (
                                <RaceCard key={race.race_key || `${race.track_code}-${race.race_number}-${index}`} race={race} />
                            ))
                        )}
                    </div>
                </>
            )}
        </div>
    );
}
