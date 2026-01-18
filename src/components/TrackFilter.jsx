export default function TrackFilter({ tracks, selectedTrack, onSelectTrack }) {
    return (
        <div className="flex flex-wrap gap-2 mb-6">
            <button
                onClick={() => onSelectTrack('All')}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${selectedTrack === 'All'
                    ? 'bg-purple-900/40 text-purple-100 border border-purple-500/40 shadow-sm'
                    : 'bg-black border border-purple-500/20 text-purple-400/80 hover:bg-purple-500/10 hover:text-purple-200 hover:border-purple-500/40'
                    }`}
            >
                All Tracks
            </button>
            {tracks.map(track => (
                <button
                    key={track}
                    onClick={() => onSelectTrack(track)}
                    className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${selectedTrack === track
                        ? 'bg-purple-900/40 text-purple-100 border border-purple-500/40 shadow-sm'
                        : 'bg-black border border-purple-500/20 text-purple-400/80 hover:bg-purple-500/10 hover:text-purple-200 hover:border-purple-500/40'
                        }`}
                >
                    {track}
                </button>
            ))}
        </div>
    );
}
