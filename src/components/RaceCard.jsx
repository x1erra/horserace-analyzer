import { Link } from 'react-router-dom';

export default function RaceCard({ race, linkTo, minimal = false }) {
    // Determine link if not provided
    const detailsLink = linkTo || `/race/${race.race_key}`;

    return (
        <div className="bg-black rounded-xl shadow-md p-6 hover:shadow-xl transition border border-purple-900/50 flex flex-col h-full">
            <div className="flex justify-between items-start mb-2">
                <h4 className="text-xl font-bold text-white">
                    Race {race.race_number} - {race.track_name || race.track_code}
                </h4>
                <div className="flex flex-col gap-1 items-end">
                    {race.race_status && (
                        <span className={`text-xs px-2 py-1 rounded text-center min-w-[70px] ${race.race_status === 'completed'
                            ? 'bg-green-900/30 text-green-400'
                            : race.race_status === 'upcoming'
                                ? 'bg-blue-900/30 text-blue-400'
                                : 'bg-gray-900/30 text-gray-400'
                            }`}>
                            {race.race_status === 'completed' ? 'Complete' :
                                race.race_status === 'upcoming' ? 'Upcoming' : 'Past'}
                        </span>
                    )}
                    {/* Claims Tag */}
                    {race.has_claims && (
                        <span className="text-xs px-2 py-1 rounded text-center min-w-[70px] bg-purple-900/30 text-purple-400 border border-purple-500/30">
                            Claims
                        </span>
                    )}
                </div>
            </div>

            <div className="mb-4 space-y-1">
                <p className="text-sm text-gray-400 flex items-center gap-2">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                    {race.race_date}
                </p>
                <p className="text-sm text-white font-bold flex items-center gap-2">
                    <svg className="w-4 h-4 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                    Post Time: {race.post_time || 'TBD'}
                </p>
            </div>

            <div className="space-y-2 mb-4 flex-1">
                {race.race_type && (
                    <p className="text-sm text-purple-300">
                        {race.race_type} • {race.surface}
                    </p>
                )}
                {race.purse && (
                    <p className="text-sm text-green-400">
                        Purse: {race.purse} • {race.distance}
                    </p>
                )}
                {!minimal && (
                    <p className="text-sm text-gray-400">
                        {race.entry_count} entries
                    </p>
                )}

                {/* Results Display */}
                {race.results && race.results.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-gray-800">
                        <p className="text-xs font-bold text-gray-500 uppercase mb-2">Top 3 Finishers</p>
                        <div className="space-y-1">
                            {race.results.map((result) => (
                                <div key={result.position} className="flex justify-between items-center text-sm">
                                    <div className="flex items-center gap-2 overflow-hidden">
                                        <span className={`
                                            w-5 h-5 flex-shrink-0 flex items-center justify-center rounded-full text-xs font-bold text-black
                                            ${result.position === 1 ? 'bg-yellow-400' :
                                                result.position === 2 ? 'bg-gray-300' :
                                                    'bg-orange-400'}
                                        `}>
                                            {result.position}
                                        </span>
                                        <span className="text-white font-medium truncate">#{result.number} {result.horse}</span>
                                    </div>
                                    {/* Trainer Name Display - Right Side */}
                                    {result.trainer && result.trainer !== 'N/A' && (
                                        <span className="text-xs text-gray-500 ml-2 whitespace-nowrap overflow-hidden text-ellipsis max-w-[100px] md:max-w-[120px]">
                                            {result.trainer}
                                        </span>
                                    )}
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>

            <Link
                to={detailsLink}
                className="w-full block bg-black border border-purple-600 hover:bg-purple-900/20 hover:border-purple-500 text-white py-2 rounded-md transition text-center mt-auto shadow-[0_0_10px_rgba(147,51,234,0.2)]"
            >
                View Details
            </Link>
        </div>
    );
}
