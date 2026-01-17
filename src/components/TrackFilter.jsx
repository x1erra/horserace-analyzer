export default function TrackFilter({ tracks, selectedTrack, onSelectTrack }) {
    return (
        <div className="flex flex-wrap gap-2 mb-6">
            <button
                onClick={() => onSelectTrack('All')}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${selectedTrack === 'All'
                        ? 'bg-purple-600 text-white shadow-lg shadow-purple-900/50'
                        : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-200'
                    }`}
            >
                All Tracks
            </button>
            {tracks.map(track => (
                <button
                    key={track}
                    onClick={() => onSelectTrack(track)}
                    className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${selectedTrack === track
                            ? 'bg-purple-600 text-white shadow-lg shadow-purple-900/50'
                            : 'bg-gray-900 border border-gray-800 text-gray-400 hover:border-purple-500/50 hover:text-purple-300'
                        }`}
                >
                    {track}
                </button>
            ))}
        </div>
    );
}
