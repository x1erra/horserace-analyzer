import { useState, useEffect } from 'react';

export default function RecentUploads({ limit = 5, compact = false }) {
    const [uploads, setUploads] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        fetchUploads();
    }, [limit]);

    const fetchUploads = async () => {
        try {
            const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:5001';
            const response = await fetch(`${baseUrl}/api/uploads?limit=${limit}`);
            if (!response.ok) throw new Error('Failed to fetch uploads');
            const data = await response.json();
            setUploads(data.uploads || []);
        } catch (err) {
            console.error('Error fetching uploads:', err);
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    if (loading) return <div className="text-gray-500 text-sm animate-pulse">Loading recent uploads...</div>;
    if (error) return null; // Hide on error to be unobtrusive
    if (uploads.length === 0) return compact ? null : <div className="text-gray-500">No recent uploads found.</div>;

    const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:5001';

    return (
        <div className={`bg-black rounded-xl border border-purple-900/50 overflow-hidden ${compact ? 'p-4' : 'p-6'}`}>
            <div className="flex justify-between items-center mb-4">
                <h4 className={`font-semibold text-white ${compact ? 'text-sm' : 'text-lg'}`}>
                    {compact ? 'Recent Uploads' : 'Recent Upload History'}
                </h4>
                {!compact && (
                    <button
                        onClick={fetchUploads}
                        className="text-xs text-purple-400 hover:text-purple-300 transition"
                    >
                        Refresh
                    </button>
                )}
            </div>

            <div className="space-y-3">
                {uploads.map((upload) => (
                    <div
                        key={upload.id}
                        className={`flex items-center justify-between group ${compact ? 'text-xs' : 'text-sm py-2 border-b border-gray-800 last:border-0'}`}
                    >
                        <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2">
                                <a
                                    href={`${baseUrl}/api/uploads/${upload.filename}`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-purple-400 hover:text-purple-300 font-medium truncate hover:underline"
                                    title={upload.filename}
                                >
                                    {upload.filename}
                                </a>
                                {upload.upload_status === 'parsing' && (
                                    <span className="text-yellow-500 animate-pulse text-[10px] px-1.5 py-0.5 rounded bg-yellow-900/30">
                                        Parsing...
                                    </span>
                                )}
                                {upload.upload_status === 'failed' && (
                                    <span className="text-red-500 text-[10px] px-1.5 py-0.5 rounded bg-red-900/30">
                                        Failed
                                    </span>
                                )}
                            </div>

                            {!compact && (
                                <div className="flex gap-4 text-gray-500 mt-1">
                                    <span>{new Date(upload.uploaded_at).toLocaleDateString()}</span>
                                    {upload.track_code && <span>{upload.track_code}</span>}
                                    {upload.race_date && <span>{upload.race_date}</span>}
                                </div>
                            )}
                            {compact && (
                                <div className="text-gray-500 text-[10px] truncate">
                                    {new Date(upload.uploaded_at).toLocaleDateString()}
                                    {upload.track_code && ` • ${upload.track_code}`}
                                </div>
                            )}
                        </div>

                        {!compact && upload.races_extracted > 0 && (
                            <div className="text-gray-400 text-xs text-right ml-4">
                                <div>{upload.races_extracted} races</div>
                                <div>{upload.entries_extracted} entries</div>
                            </div>
                        )}

                        <a
                            href={`${baseUrl}/api/uploads/${upload.filename}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="ml-3 text-gray-600 group-hover:text-purple-400 transition"
                            title="View PDF"
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                            </svg>
                        </a>
                    </div>
                ))}
            </div>
        </div>
    );
}
