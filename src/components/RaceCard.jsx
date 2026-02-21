import { Link } from 'react-router-dom';

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

export default function RaceCard({ race, linkTo, minimal = false }) {
    // Determine link if not provided
    const detailsLink = linkTo || `/race/${race.race_key}`;

    return (
        <Link
            to={detailsLink}
            className="group bg-black rounded-xl shadow-md p-6 hover:shadow-xl hover:border-purple-500 transition border border-purple-900/50 flex flex-col h-full relative overflow-hidden"
        >
            {/* Hover Effect Gradient */}
            <div className="absolute inset-0 bg-gradient-to-t from-purple-900/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none" />

            {/* Header Section - Fixed Height for alignment */}
            <div className="flex justify-between items-start mb-4 h-[52px]">
                <h4 className="text-xl font-bold text-white group-hover:text-purple-400 transition line-clamp-2">
                    Race {race.race_number} - {race.track_name || race.track_code}
                </h4>
                <div className="flex flex-col gap-1 items-end shrink-0 ml-2">
                    {race.race_status && (
                        <span className={`text-xs px-2 py-1 rounded text-center min-w-[70px] ${race.race_status === 'completed'
                            ? 'bg-green-900/30 text-green-400'
                            : race.race_status === 'upcoming'
                                ? 'bg-blue-900/30 text-blue-400'
                                : race.race_status === 'cancelled'
                                    ? 'bg-red-900/50 text-red-500 font-bold border border-red-900'
                                    : race.race_status === 'delayed'
                                        ? 'bg-orange-900/50 text-orange-400 font-bold border border-orange-900'
                                        : 'bg-gray-900/30 text-gray-400'
                            }`}>
                            {race.race_status === 'completed' ? 'Complete' :
                                race.race_status === 'upcoming' ? 'Upcoming' :
                                    race.race_status === 'cancelled' ? 'CANCELLED' :
                                        race.race_status === 'delayed' ? 'DELAYED' : 'Past'}
                        </span>
                    )}
                    {/* Claims Tag */}
                    {race.has_claims && (
                        <span className="text-xs px-2 py-1 rounded text-center min-w-[70px] bg-purple-900/30 text-purple-400">
                            Claims
                        </span>
                    )}
                </div>
            </div>

            {/* Date and Time Section - Fixed Height */}
            <div className="mb-4 space-y-1 h-[48px] border-b border-gray-800/50 pb-2">
                <p className="text-sm text-gray-400 flex items-center gap-2">
                    <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                    {race.race_date}
                </p>
                <p className="text-sm text-white font-bold flex items-center gap-2">
                    <svg className="w-4 h-4 text-purple-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                    Post Time: {race.post_time_iso ? new Date(race.post_time_iso).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', timeZoneName: 'short' }) : (race.post_time || 'TBD')}
                </p>
            </div>

            {/* Details Section */}
            <div className="space-y-2 mb-4 flex-1">
                {/* Race Details Block - Fixed Height for alignment */}
                <div className="h-[64px]">
                    {race.race_type && (
                        <p className="text-sm text-purple-300 truncate">
                            {race.race_type} • {race.surface}
                        </p>
                    )}
                    {race.purse && (
                        <p className="text-sm text-green-400 truncate">
                            Purse: {race.purse} • {race.distance}
                        </p>
                    )}
                    {!minimal && (
                        <p className="text-sm text-gray-400">
                            {race.entry_count} entries
                        </p>
                    )}
                </div>

                {/* Results Display - Pushed to bottom via flex-1 of container if needed, but here it flows naturally */}
                {race.results && race.results.length > 0 && (
                    <div className="mt-2 pt-3 border-t border-gray-800">
                        <p className="text-xs font-bold text-gray-500 uppercase mb-2">Top 3 Finishers</p>
                        <div className="space-y-1">
                            {race.results.map((result) => (
                                <div key={result.position} className="flex justify-between items-center text-sm">
                                    <div className="flex items-center gap-2 overflow-hidden">
                                        {(() => {
                                            const style = getPostColor(result.number);
                                            return (
                                                <span
                                                    className="inline-flex w-5 h-5 flex-shrink-0 items-center justify-center rounded-md text-xs font-bold shadow-sm leading-none"
                                                    style={{ backgroundColor: style.bg, color: style.text }}
                                                >
                                                    {result.number}
                                                </span>
                                            );
                                        })()}
                                        <span className="text-white font-medium truncate">{result.horse}</span>
                                    </div>
                                    {/* Trainer Name Display - Right Side */}
                                    {result.trainer && result.trainer !== 'N/A' && (
                                        <span className="text-xs text-gray-500 ml-2 whitespace-nowrap overflow-hidden text-ellipsis max-w-[80px] md:max-w-[100px]">
                                            {result.trainer}
                                        </span>
                                    )}
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>

            {/* View Details Indicator - Optional subtle text at bottom */}
            <div className="mt-auto pt-2 text-center opacity-0 group-hover:opacity-100 transition-opacity">
                <span className="text-xs text-purple-400 font-medium uppercase tracking-wider">View Race Details →</span>
            </div>
        </Link>
    );
}
