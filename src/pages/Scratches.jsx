
import { useState, useEffect } from 'react';
import { supabase } from '../supabaseClient';
import { format } from 'date-fns';
import { RefreshCw, Filter, Calendar, AlertTriangle } from 'lucide-react';

export default function Scratches() {
    const [loading, setLoading] = useState(true);
    const [scratches, setScratches] = useState([]);
    const [error, setError] = useState(null);
    const [viewMode, setViewMode] = useState('upcoming'); // 'upcoming' or 'all'

    const fetchScratches = async () => {
        try {
            setLoading(true);
            setError(null);

            // Base query: get scratches
            // We need to join r
            let query = supabase
                .from('hranalyzer_race_entries')
                .select(`
          id,
          program_number,
          horse_id,
          scratched,
          updated_at,
          hranalyzer_horses (
            horse_name
          ),
          hranalyzer_races (
            id,
            track_code,
            race_date,
            race_number,
            post_time,
            race_status
          ),
          hranalyzer_trainers (
            trainer_name
          )
        `)
                .eq('scratched', true)
                .order('updated_at', { ascending: false });

            const { data, error: err } = await query;

            if (err) throw err;

            // Filter locally for 'upcoming' if needed, or refine query
            // Upcoming = race_date >= today
            const today = new Date().toISOString().split('T')[0];

            let filtered = data.filter(item => item.hranalyzer_races); // ensure race exists

            if (viewMode === 'upcoming') {
                filtered = filtered.filter(item => item.hranalyzer_races.race_date >= today);
            }

            // Sort: Date Desc, Track, Race #
            filtered.sort((a, b) => {
                const raceA = a.hranalyzer_races;
                const raceB = b.hranalyzer_races;
                if (raceA.race_date !== raceB.race_date)
                    return raceB.race_date.localeCompare(raceA.race_date); // Newest first
                if (raceA.track_code !== raceB.track_code)
                    return raceA.track_code.localeCompare(raceB.track_code);
                return raceA.race_number - raceB.race_number;
            });

            setScratches(filtered);

        } catch (e) {
            console.error("Error fetching scratches:", e);
            setError("Failed to load scratches.");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchScratches();
    }, [viewMode]);

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h1 className="text-3xl font-bold text-white flex items-center gap-3">
                        <AlertTriangle className="w-8 h-8 text-yellow-500" />
                        Scratched Horses
                    </h1>
                    <p className="text-gray-400 mt-1">
                        Real-time updates on scratched horses
                    </p>
                </div>

                <div className="flex items-center gap-3 bg-gray-900 p-1 rounded-lg border border-gray-800">
                    <button
                        onClick={() => setViewMode('upcoming')}
                        className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${viewMode === 'upcoming'
                                ? 'bg-yellow-500/20 text-yellow-500'
                                : 'text-gray-400 hover:text-white'
                            }`}
                    >
                        Upcoming
                    </button>
                    <button
                        onClick={() => setViewMode('all')}
                        className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${viewMode === 'all'
                                ? 'bg-yellow-500/20 text-yellow-500'
                                : 'text-gray-400 hover:text-white'
                            }`}
                    >
                        All History
                    </button>
                </div>
            </div>

            {/* Content */}
            <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden shadow-xl">
                {loading ? (
                    <div className="p-12 text-center text-gray-500 animate-pulse">
                        Loading scratch data...
                    </div>
                ) : error ? (
                    <div className="p-12 text-center text-red-400">
                        {error}
                    </div>
                ) : scratches.length === 0 ? (
                    <div className="p-12 text-center text-gray-500">
                        No scratches found for this period.
                    </div>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full text-left border-collapse">
                            <thead>
                                <tr className="border-b border-gray-800 bg-gray-900/50 text-gray-400 text-sm uppercase tracking-wider">
                                    <th className="p-4">Date</th>
                                    <th className="p-4">Track</th>
                                    <th className="p-4">Race</th>
                                    <th className="p-4">Horse</th>
                                    <th className="p-4">Trainer</th>
                                    <th className="p-4">Status</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-800">
                                {scratches.map((item) => (
                                    <tr key={item.id} className="hover:bg-gray-800/50 transition-colors group">
                                        <td className="p-4 text-gray-300 font-medium">
                                            {format(new Date(item.hranalyzer_races.race_date), 'MMM d, yyyy')}
                                        </td>
                                        <td className="p-4">
                                            <span className="inline-flex items-center justify-center px-2.5 py-1 rounded-md bg-gray-800 text-gray-300 text-xs font-bold border border-gray-700">
                                                {item.hranalyzer_races.track_code}
                                            </span>
                                        </td>
                                        <td className="p-4 text-gray-300">
                                            Top Race {item.hranalyzer_races.race_number}
                                        </td>
                                        <td className="p-4">
                                            <div className="flex items-center gap-3">
                                                <div className="w-8 h-8 rounded-full bg-red-500/20 flex items-center justify-center text-red-500 font-bold text-sm border border-red-500/30">
                                                    {item.program_number}
                                                </div>
                                                <span className="text-white font-medium group-hover:text-yellow-400 transition-colors">
                                                    {item.hranalyzer_horses?.horse_name || 'Unknown'}
                                                </span>
                                            </div>
                                        </td>
                                        <td className="p-4 text-gray-400">
                                            {item.hranalyzer_trainers?.trainer_name || '-'}
                                        </td>
                                        <td className="p-4">
                                            <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-red-500/10 text-red-500 border border-red-500/20">
                                                Scratched
                                            </span>
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
