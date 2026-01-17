import { useParams, Link } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { ArrowLeft } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:5001';

export default function HorseProfile() {
    const { id } = useParams();
    const [horse, setHorse] = useState(null);
    const [stats, setStats] = useState(null);
    const [raceHistory, setRaceHistory] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchHorseProfile = async () => {
            setLoading(true);
            setError(null);
            try {
                const response = await fetch(`${API_BASE}/api/horse/${id}`);
                if (!response.ok) {
                    if (response.status === 404) {
                        throw new Error('Horse not found');
                    }
                    throw new Error('Failed to fetch horse profile');
                }

                const data = await response.json();
                setHorse(data.horse);
                setStats(data.stats);
                setRaceHistory(data.race_history || []);
            } catch (err) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };

        if (id) {
            fetchHorseProfile();
        }
    }, [id]);

    // Format sex display
    const formatSex = (sex) => {
        const sexMap = { 'C': 'Colt', 'F': 'Filly', 'G': 'Gelding', 'H': 'Horse', 'M': 'Mare' };
        return sexMap[sex] || sex || 'N/A';
    };

    // Format finish position display
    const formatPosition = (pos, scratched) => {
        if (scratched) return <span className="text-gray-500">SCR</span>;
        if (!pos) return <span className="text-gray-500">-</span>;
        if (pos === 1) return <span className="text-yellow-400 font-bold">1st</span>;
        if (pos === 2) return <span className="text-gray-300 font-bold">2nd</span>;
        if (pos === 3) return <span className="text-amber-600 font-bold">3rd</span>;
        return <span className="text-gray-400">{pos}th</span>;
    };

    if (loading) {
        return (
            <div className="text-center py-16">
                <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-purple-500"></div>
                <p className="text-gray-400 mt-4">Loading horse profile...</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="text-center py-16">
                <p className="text-red-400 text-xl mb-4">Error: {error}</p>
                <Link
                    to="/horses"
                    className="inline-flex items-center gap-2 text-purple-400 hover:text-purple-300 transition"
                >
                    <ArrowLeft size={18} /> Back to Horses
                </Link>
            </div>
        );
    }

    if (!horse) {
        return (
            <div className="text-center py-16">
                <p className="text-gray-400 text-xl mb-4">Horse not found</p>
                <Link
                    to="/horses"
                    className="inline-flex items-center gap-2 text-purple-400 hover:text-purple-300 transition"
                >
                    <ArrowLeft size={18} /> Back to Horses
                </Link>
            </div>
        );
    }

    return (
        <div className="space-y-8">
            {/* Back button */}
            <Link
                to="/horses"
                className="inline-flex items-center gap-2 text-purple-400 hover:text-purple-300 transition"
            >
                <ArrowLeft size={18} /> Back to Horses
            </Link>

            {/* Horse header */}
            <div className="bg-black border border-purple-900/50 rounded-xl p-6">
                <h1 className="text-4xl font-bold text-white mb-2">{horse.name}</h1>
                <p className="text-lg text-gray-400">
                    {formatSex(horse.sex)} {horse.color && `• ${horse.color}`}
                    {horse.foaling_year && ` • Foaled ${horse.foaling_year}`}
                </p>

                {/* Breeding info */}
                {(horse.sire || horse.dam) && (
                    <div className="mt-4 pt-4 border-t border-gray-800">
                        <h3 className="text-sm font-semibold text-gray-500 mb-2">BREEDING</h3>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {horse.sire && (
                                <div>
                                    <span className="text-gray-500 text-sm">Sire: </span>
                                    <span className="text-white">{horse.sire}</span>
                                </div>
                            )}
                            {horse.dam && (
                                <div>
                                    <span className="text-gray-500 text-sm">Dam: </span>
                                    <span className="text-white">{horse.dam}</span>
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </div>

            {/* Statistics */}
            {stats && (
                <div className="bg-black border border-purple-900/50 rounded-xl p-6">
                    <h2 className="text-xl font-bold text-white mb-4">Career Statistics</h2>
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                        <div className="bg-gray-900/50 rounded-lg p-4 text-center">
                            <div className="text-3xl font-bold text-purple-400">{stats.total}</div>
                            <div className="text-sm text-gray-500">Starts</div>
                        </div>
                        <div className="bg-gray-900/50 rounded-lg p-4 text-center">
                            <div className="text-3xl font-bold text-green-400">{stats.wins}</div>
                            <div className="text-sm text-gray-500">Wins</div>
                        </div>
                        <div className="bg-gray-900/50 rounded-lg p-4 text-center">
                            <div className="text-3xl font-bold text-gray-300">{stats.places}</div>
                            <div className="text-sm text-gray-500">Places</div>
                        </div>
                        <div className="bg-gray-900/50 rounded-lg p-4 text-center">
                            <div className="text-3xl font-bold text-amber-600">{stats.shows}</div>
                            <div className="text-sm text-gray-500">Shows</div>
                        </div>
                        <div className="bg-gray-900/50 rounded-lg p-4 text-center">
                            <div className="text-3xl font-bold text-yellow-400">{stats.win_percentage}%</div>
                            <div className="text-sm text-gray-500">Win Rate</div>
                        </div>
                    </div>

                    {/* Record summary */}
                    <div className="mt-4 text-center">
                        <span className="text-gray-400">Record: </span>
                        <span className="text-white font-semibold text-lg">
                            {stats.wins}-{stats.places}-{stats.shows}
                        </span>
                    </div>
                </div>
            )}

            {/* Race History */}
            <div className="bg-black border border-purple-900/50 rounded-xl p-6">
                <h2 className="text-xl font-bold text-white mb-4">
                    Race History
                    <span className="text-gray-500 text-sm font-normal ml-2">({raceHistory.length} races)</span>
                </h2>

                {raceHistory.length === 0 ? (
                    <p className="text-gray-500 text-center py-8">No race history available.</p>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="text-gray-500 border-b border-gray-800">
                                    <th className="text-left py-3 px-2">Date</th>
                                    <th className="text-left py-3 px-2">Track</th>
                                    <th className="text-left py-3 px-2">Race</th>
                                    <th className="text-left py-3 px-2">Type</th>
                                    <th className="text-left py-3 px-2">Distance</th>
                                    <th className="text-center py-3 px-2">Finish</th>
                                    <th className="text-left py-3 px-2">Odds</th>
                                    <th className="text-left py-3 px-2">Jockey</th>
                                    <th className="text-left py-3 px-2">Trainer</th>
                                    <th className="text-left py-3 px-2"></th>
                                </tr>
                            </thead>
                            <tbody>
                                {raceHistory.map((race, index) => (
                                    <tr
                                        key={`${race.race_key}-${index}`}
                                        className={`border-b border-gray-800/50 hover:bg-gray-900/30 transition ${race.scratched ? 'opacity-50' : ''}`}
                                    >
                                        <td className="py-3 px-2 text-gray-300">{race.race_date}</td>
                                        <td className="py-3 px-2 text-white font-medium">{race.track_code}</td>
                                        <td className="py-3 px-2 text-gray-300">R{race.race_number}</td>
                                        <td className="py-3 px-2 text-gray-400">{race.race_type || '-'}</td>
                                        <td className="py-3 px-2 text-gray-400">{race.distance || '-'}</td>
                                        <td className="py-3 px-2 text-center">{formatPosition(race.finish_position, race.scratched)}</td>
                                        <td className="py-3 px-2 text-gray-400">{race.final_odds || '-'}</td>
                                        <td className="py-3 px-2 text-gray-400">{race.jockey_name}</td>
                                        <td className="py-3 px-2 text-gray-400">{race.trainer_name}</td>
                                        <td className="py-3 px-2">
                                            {race.race_key && (
                                                <Link
                                                    to={`/race/${race.race_key}`}
                                                    className="text-purple-400 hover:text-purple-300 transition text-xs"
                                                >
                                                    View Race
                                                </Link>
                                            )}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    );
}
