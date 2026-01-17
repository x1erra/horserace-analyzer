
import { useState, useEffect } from 'react';
import axios from 'axios';
import { format, parseISO } from 'date-fns';
import { AlertTriangle } from 'lucide-react';

const getPostColor = (number) => {
    const num = parseInt(number);
    if (isNaN(num)) return { bg: '#374151', text: '#FFFFFF' };

    switch (num) {
        case 1: return { bg: '#EF4444', text: '#FFFFFF' }; // Red
        case 2: return { bg: '#FFFFFF', text: '#000000' }; // White
        case 3: return { bg: '#3B82F6', text: '#FFFFFF' }; // Blue
        case 4: return { bg: '#EAB308', text: '#000000' }; // Yellow
        case 5: return { bg: '#22C55E', text: '#FFFFFF' }; // Green
        case 6: return { bg: '#000000', text: '#FACC15' }; // Black with Yellow text
        case 7: return { bg: '#F97316', text: '#000000' }; // Orange with Black text
        case 8: return { bg: '#EC4899', text: '#000000' }; // Pink with Black text
        case 9: return { bg: '#06B6D4', text: '#000000' }; // Turquoise with Black text
        case 10: return { bg: '#A855F7', text: '#FFFFFF' }; // Purple
        case 11: return { bg: '#9CA3AF', text: '#FFFFFF' }; // Grey
        case 12: return { bg: '#84CC16', text: '#000000' }; // Lime with Black text
        case 13: return { bg: '#78350F', text: '#FFFFFF' }; // Brown
        case 14: return { bg: '#831843', text: '#FFFFFF' }; // Maroon
        case 15: return { bg: '#C3B091', text: '#000000' }; // Khaki (Corrected)
        case 16: return { bg: '#60A5FA', text: '#FFFFFF' }; // Copen Blue
        case 17: return { bg: '#1E3A8A', text: '#FFFFFF' }; // Navy
        case 18: return { bg: '#14532D', text: '#FFFFFF' }; // Forest Green
        case 19: return { bg: '#0EA5E9', text: '#FFFFFF' }; // Moonstone
        case 20: return { bg: '#D946EF', text: '#FFFFFF' }; // Fuschia
        default: return { bg: '#374151', text: '#FFFFFF' };
    }
};

export default function Scratches() {
    const [loading, setLoading] = useState(true);
    const [scratches, setScratches] = useState([]);
    const [error, setError] = useState(null);
    const [viewMode, setViewMode] = useState('upcoming'); // 'upcoming' or 'all'

    const fetchScratches = async () => {
        try {
            setLoading(true);
            setError(null);

            const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:5001';
            const endpoint = `${baseUrl}/api/scratches`;

            const params = {
                view: viewMode,
                _t: Date.now() // cache buster
            };

            const response = await axios.get(endpoint, { params });

            // Backend already returns sorted list
            setScratches(response.data.scratches || []);

        } catch (e) {
            console.error("Error fetching scratches:", e);
            setError("Failed to load scratches. Is the backend running?");
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
                            ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30'
                            : 'text-gray-400 hover:text-white border border-transparent'
                            }`}
                    >
                        Upcoming
                    </button>
                    <button
                        onClick={() => setViewMode('all')}
                        className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${viewMode === 'all'
                            ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30'
                            : 'text-gray-400 hover:text-white border border-transparent'
                            }`}
                    >
                        All History
                    </button>
                </div>
            </div>

            {/* Content */}
            <div className="bg-black rounded-xl border border-purple-900/20 overflow-hidden shadow-xl">
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
                                <tr className="border-b border-purple-900/30 bg-purple-900/20 text-purple-300 text-sm uppercase tracking-wider">
                                    <th className="p-4">Date</th>
                                    <th className="p-4">Track</th>
                                    <th className="p-4">Race</th>
                                    <th className="p-4">Horse</th>
                                    <th className="p-4">Trainer</th>
                                    <th className="p-4">Status</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-purple-900/30">
                                {scratches.map((item) => (
                                    <tr key={item.id} className="hover:bg-purple-900/10 transition-colors group">
                                        <td className="p-4 text-gray-300 font-medium">
                                            {item.race_date ? format(parseISO(item.race_date), 'MMM d, yyyy') : '-'}
                                        </td>
                                        <td className="p-4">
                                            <span className="inline-flex items-center justify-center px-2.5 py-1 rounded-md bg-gray-800 text-gray-300 text-xs font-bold border border-gray-700">
                                                {item.track_code}
                                            </span>
                                        </td>
                                        <td className="p-4 text-gray-300">
                                            Race {item.race_number}
                                        </td>
                                        <td className="p-4">
                                            <div className="flex items-center gap-3">
                                                {(() => {
                                                    const style = getPostColor(item.program_number);
                                                    return (
                                                        <div
                                                            className="w-8 h-8 rounded-md flex items-center justify-center font-bold text-sm shadow-sm leading-none"
                                                            style={{ backgroundColor: style.bg, color: style.text }}
                                                        >
                                                            {item.program_number}
                                                        </div>
                                                    );
                                                })()}
                                                <span className="text-white font-medium group-hover:text-purple-400 transition-colors">
                                                    {item.horse_name || 'Unknown'}
                                                </span>
                                            </div>
                                        </td>
                                        <td className="p-4 text-gray-400">
                                            {item.trainer_name || '-'}
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
