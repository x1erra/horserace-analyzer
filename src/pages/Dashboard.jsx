import { Link } from 'react-router-dom';
import { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import RecentUploads from '../components/RecentUploads';
import RaceCard from '../components/RaceCard';
import { HiStar, HiOutlineStar } from 'react-icons/hi';

// Helper component for Countdown
const Countdown = ({ targetIso, originalTime }) => {
    const [timeLeft, setTimeLeft] = useState('');
    const [isUrgent, setIsUrgent] = useState(false);

    useEffect(() => {
        if (!targetIso) return;

        const calculateTime = () => {
            const now = new Date();
            const target = new Date(targetIso);
            const diff = target - now;

            if (diff <= 0) {
                // Post time has passed
                setTimeLeft('Post Time');
                setIsUrgent(true);
                return;
            }

            // Calculate hours, minutes, seconds
            const hours = Math.floor(diff / (1000 * 60 * 60));
            const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
            const seconds = Math.floor((diff % (1000 * 60)) / 1000);

            if (hours > 0) {
                setTimeLeft(`${hours}h ${minutes}m`);
                setIsUrgent(false);
            } else {
                // Less than an hour, show MM:SS
                setTimeLeft(`${minutes}m ${seconds}s`);
                // Urgent if less than 5 mins
                setIsUrgent(minutes < 5);
            }
        };

        calculateTime();
        const timer = setInterval(calculateTime, 1000);

        return () => clearInterval(timer);
    }, [targetIso]);

    if (!targetIso) return <span className="text-white font-medium">-</span>;

    return (
        <span className={`font-mono text-xs ${isUrgent ? 'text-red-400 animate-pulse' : 'text-green-400'}`}>
            {timeLeft}
        </span>
    );
};

// Track Card Component
const TrackCard = ({ track, isFavorite, onToggleFavorite, onClick }) => (
    <div
        className="bg-black border border-purple-900/30 rounded-xl p-5 hover:border-purple-500/50 transition cursor-pointer h-full flex flex-col justify-between group relative overflow-hidden"
        onClick={onClick}
    >
        <div>
            <div className="flex justify-between items-start mb-4">
                <h5 className="font-bold text-white text-lg">{track.track_name}</h5>
                <div className="flex items-center gap-2">
                    <span className="bg-purple-900/30 text-purple-300 text-xs px-2 py-1 rounded-full font-mono">
                        {track.track_code}
                    </span>
                    {/* Favorite Toggle */}
                    <button
                        onClick={onToggleFavorite}
                        className={`p-1.5 rounded-full transition-all duration-200 ${isFavorite
                            ? 'text-yellow-500 bg-yellow-500/10'
                            : 'text-gray-400 opacity-30 hover:opacity-100 hover:text-yellow-500'
                            }`}
                        title={isFavorite ? "Remove from Favorites" : "Add to Favorites"}
                    >
                        {isFavorite ? <HiStar className="w-5 h-5" /> : <HiOutlineStar className="w-5 h-5" />}
                    </button>
                </div>
            </div>
            <div className="space-y-2">
                <div className="flex justify-between text-sm">
                    <span className="text-gray-400">Total Races</span>
                    <span className="text-white font-medium">{track.total}</span>
                </div>
                <div className="w-full bg-gray-800 h-1.5 rounded-full overflow-hidden">
                    <div
                        className="bg-green-500 h-full"
                        style={{ width: `${(track.completed / track.total) * 100}%` }}
                    ></div>
                </div>
                <div className="flex justify-between text-xs text-gray-500 pt-1">
                    <span>{track.completed} Completed</span>
                    <span>{track.upcoming} Upcoming</span>
                </div>
            </div>
        </div>

        {/* Additional Info: Next / Last */}
        <div className="grid grid-cols-2 gap-4 mt-6 pt-4 border-t border-gray-800">
            <div>
                <span className="text-[10px] text-gray-500 uppercase tracking-widest block mb-1">Last Winner</span>
                {track.last_race_winner ? (
                    <div className="truncate" title={track.last_race_winner}>
                        <span className="text-sm font-bold text-white block truncate">{track.last_race_winner}</span>
                        <span className="text-[10px] text-purple-400">Race {track.last_race_number}</span>
                    </div>
                ) : (
                    <span className="text-gray-600 text-xs italic">-</span>
                )}
            </div>
            <div>
                <span className="text-[10px] text-gray-500 uppercase tracking-widest block mb-1">Next Post</span>
                {track.next_race_iso ? (
                    <div className="flex flex-col">
                        <span className="text-sm font-bold text-white">
                            {new Date(track.next_race_iso).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}
                        </span>
                        <Countdown targetIso={track.next_race_iso} originalTime={track.next_race_time} />
                    </div>
                ) : (
                    <span className="text-gray-400 text-sm">-</span>
                )}
            </div>
        </div>
    </div>
);

export default function Dashboard() {
    const [viewMode, setViewMode] = useState('overview'); // 'overview' | 'results'
    const [todaySummary, setTodaySummary] = useState([]);
    const [races, setRaces] = useState([]);
    const [favoriteTracks, setFavoriteTracks] = useState([]);

    // Filters
    const [selectedTrack, setSelectedTrack] = useState('All');
    const [selectedStatus, setSelectedStatus] = useState('All'); // 'All' | 'Upcoming' | 'Completed'

    const [loading, setLoading] = useState(false);
    const [metaLoading, setMetaLoading] = useState(true);
    const [error, setError] = useState(null);

    // Fetch summary on mount
    useEffect(() => {
        // Load favorites from localStorage
        const savedFavorites = JSON.parse(localStorage.getItem('favorite_tracks')) || [];
        setFavoriteTracks(savedFavorites);

        const fetchSummary = async () => {
            try {
                const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:5001';
                const response = await axios.get(`${baseUrl}/api/filter-options`);
                if (response.data) {
                    setTodaySummary(response.data.today_summary || []);
                }
            } catch (err) {
                console.error("Error fetching summary:", err);
            } finally {
                setMetaLoading(false);
            }
        };
        fetchSummary();
    }, []);

    const handleLoadRaces = async (trackOverride = null, statusOverride = null) => {
        try {
            setLoading(true);
            setError(null);

            const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:5001';
            const params = {};

            // Use override if provided, otherwise use state
            const trackToUse = trackOverride !== null ? trackOverride : selectedTrack;
            const statusToUse = statusOverride !== null ? statusOverride : selectedStatus;

            if (trackToUse !== 'All') params.track = trackToUse;
            if (statusToUse !== 'All') params.status = statusToUse;

            // Add cache buster
            params._t = Date.now();

            const response = await axios.get(`${baseUrl}/api/todays-races`, { params });
            setRaces(response.data.races || []);
            setViewMode('results');
        } catch (err) {
            console.error("Error loading races:", err);
            setError("Failed to load races.");
        } finally {
            setLoading(false);
        }
    };

    const toggleFavorite = (trackName, e) => {
        if (e) e.stopPropagation();

        const isFav = favoriteTracks.includes(trackName);
        let updated;
        if (isFav) {
            updated = favoriteTracks.filter(name => name !== trackName);
        } else {
            updated = [...favoriteTracks, trackName];
        }

        setFavoriteTracks(updated);
        localStorage.setItem('favorite_tracks', JSON.stringify(updated));
    };

    // Separate tracks into favorites and others
    const { favoritedTracks, remainingTracks } = useMemo(() => {
        const favs = [];
        const others = [];

        todaySummary.forEach(track => {
            if (favoriteTracks.includes(track.track_name)) {
                favs.push(track);
            } else {
                others.push(track);
            }
        });

        return { favoritedTracks: favs, remainingTracks: others };
    }, [todaySummary, favoriteTracks]);

    // Calculate totals for overview
    const totalRacesToday = todaySummary.reduce((sum, item) => sum + item.total, 0);

    return (
        <div className="space-y-8">
            {/* Header Area */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h3 className="text-3xl font-bold text-white">Dashboard</h3>
                    <p className="text-gray-400">
                        {new Date().toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
                    </p>
                </div>
                <Link
                    to="/upload"
                    className="bg-black border border-purple-600 hover:bg-purple-900/20 hover:border-purple-500 text-white px-5 py-2.5 rounded-lg transition text-sm font-medium flex items-center gap-2 shadow-[0_0_15px_rgba(147,51,234,0.3)]"
                >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                    Upload PDF
                </Link>
            </div>

            {/* Filter Bar */}
            <div className="bg-black/50 p-4 rounded-xl border border-purple-900/20 flex flex-col md:flex-row gap-4 items-end">
                <div className="w-full md:w-auto flex-1 grid grid-cols-2 gap-4">
                    <div>
                        <label className="block text-xs font-semibold text-gray-500 mb-1 ml-1 uppercase tracking-wider">Track</label>
                        <select
                            value={selectedTrack}
                            onChange={(e) => setSelectedTrack(e.target.value)}
                            className="w-full bg-black border border-gray-800 text-white px-4 py-2.5 rounded-lg focus:outline-none focus:border-purple-600 focus:ring-1 focus:ring-purple-600 transition appearance-none"
                        >
                            <option value="All">All Tracks ({todaySummary.length})</option>
                            {todaySummary.map(item => (
                                <option key={item.track_code} value={item.track_name}>
                                    {item.track_name} ({item.total})
                                </option>
                            ))}
                        </select>
                    </div>
                    <div>
                        <label className="block text-xs font-semibold text-gray-500 mb-1 ml-1 uppercase tracking-wider">Status</label>
                        <select
                            value={selectedStatus}
                            onChange={(e) => setSelectedStatus(e.target.value)}
                            className="w-full bg-black border border-gray-800 text-white px-4 py-2.5 rounded-lg focus:outline-none focus:border-purple-600 focus:ring-1 focus:ring-purple-600 transition appearance-none"
                        >
                            <option value="All">All Races</option>
                            <option value="Upcoming">Upcoming Only</option>
                            <option value="Completed">Completed Only</option>
                        </select>
                    </div>
                </div>
                <button
                    onClick={() => handleLoadRaces()}
                    disabled={loading}
                    className="w-full md:w-auto bg-black border border-purple-600 hover:bg-purple-900/20 hover:border-purple-500 disabled:opacity-50 text-white px-8 py-2.5 rounded-lg transition font-bold shadow-[0_0_15px_rgba(147,51,234,0.3)] flex items-center justify-center gap-2 h-[42px]"
                >
                    {loading ? (
                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                    ) : (
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                        </svg>
                    )}
                    Load Races
                </button>
            </div>

            {/* Content Area */}
            {metaLoading ? (
                <div className="py-20 text-center">
                    <div className="inline-block animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-purple-500"></div>
                </div>
            ) : viewMode === 'overview' ? (
                /* Overview Mode */
                <div className="space-y-10 animate-fadeIn">
                    {/* Favorite Tracks Section */}
                    {favoritedTracks.length > 0 && (
                        <div className="space-y-4">
                            <div className="flex items-center gap-2 text-purple-300">
                                <HiStar className="w-5 h-5" />
                                <h4 className="font-semibold text-lg">Favorite Tracks</h4>
                            </div>
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                                {favoritedTracks.map(track => (
                                    <TrackCard
                                        key={track.track_code}
                                        track={track}
                                        isFavorite={true}
                                        onToggleFavorite={(e) => toggleFavorite(track.track_name, e)}
                                        onClick={() => {
                                            setSelectedTrack(track.track_name);
                                            handleLoadRaces(track.track_name);
                                        }}
                                    />
                                ))}
                            </div>
                        </div>
                    )}

                    <div className="space-y-4">
                        <div className="flex items-center gap-2 text-purple-300">
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                            </svg>
                            <h4 className="font-semibold text-lg">Daily Overview</h4>
                        </div>

                        {todaySummary.length === 0 ? (
                            <div className="bg-black/30 border border-purple-900/20 rounded-xl p-12 text-center">
                                <p className="text-gray-400 mb-6">No races scheduled for today yet.</p>
                                <Link to="/upload" className="text-purple-400 hover:text-white underline">Upload a DRF PDF</Link>
                            </div>
                        ) : (
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                                {remainingTracks.map(track => (
                                    <TrackCard
                                        key={track.track_code}
                                        track={track}
                                        isFavorite={false}
                                        onToggleFavorite={(e) => toggleFavorite(track.track_name, e)}
                                        onClick={() => {
                                            setSelectedTrack(track.track_name);
                                            handleLoadRaces(track.track_name);
                                        }}
                                    />
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            ) : (
                /* Results Mode */
                <div className="bg-black/20 rounded-xl min-h-[400px]">
                    <div className="flex justify-between items-center mb-6">
                        <h4 className="text-xl font-bold text-white">
                            Race Results <span className="text-gray-500 ml-2 text-sm font-normal">({races.length} found)</span>
                        </h4>
                        <button
                            onClick={() => setViewMode('overview')}
                            className="text-sm text-purple-400 hover:text-white flex items-center gap-1"
                        >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                            </svg>
                            Back to Overview
                        </button>
                    </div>

                    {loading ? (
                        <div className="text-center py-20">
                            <div className="inline-block animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-purple-500"></div>
                            <p className="mt-4 text-gray-400">Loading races...</p>
                        </div>
                    ) : races.length === 0 ? (
                        <div className="text-center py-20 bg-black rounded-xl border border-purple-900/20 border-dashed">
                            <p className="text-gray-400">No races found matching your filters.</p>
                            <button onClick={() => setViewMode('overview')} className="text-purple-500 mt-2 hover:underline">Clear filters</button>
                        </div>
                    ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 animate-fadeIn">
                            {races.map((race, index) => (
                                <RaceCard
                                    key={race.race_key || `${race.track_code}-${race.race_number}-${index}`}
                                    race={race}
                                />
                            ))}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
