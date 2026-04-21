import { useState, useEffect, useCallback } from 'react';

export default function RecentUploads({ limit = 5, compact = false, refreshToken = 0 }) {
    const [uploads, setUploads] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:5001';

    const fetchUploads = useCallback(async () => {
        try {
            setError(null);
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
    }, [baseUrl, limit]);

    useEffect(() => {
        fetchUploads();
    }, [fetchUploads, refreshToken]);

    useEffect(() => {
        const hasActiveUpload = uploads.some((upload) => ['queued', 'parsing'].includes(upload.upload_status));
        if (!hasActiveUpload) return undefined;

        const interval = setInterval(fetchUploads, 5000);
        return () => clearInterval(interval);
    }, [fetchUploads, uploads]);

    const handleReprocess = async (upload) => {
        try {
            const response = await fetch(`${baseUrl}/api/uploads/${upload.id}/reprocess`, {
                method: 'POST'
            });
            if (!response.ok) throw new Error('Failed to reprocess upload');
            await fetchUploads();
        } catch (err) {
            console.error('Error reprocessing upload:', err);
            setError(err.message);
        }
    };

    const handleDelete = async (upload) => {
        if (!window.confirm(`Remove ${upload.filename} from upload history?`)) return;

        try {
            const response = await fetch(`${baseUrl}/api/uploads/${upload.id}`, {
                method: 'DELETE'
            });
            if (!response.ok) throw new Error('Failed to delete upload');
            await fetchUploads();
        } catch (err) {
            console.error('Error deleting upload:', err);
            setError(err.message);
        }
    };

    if (loading) return <div className="text-gray-500 text-sm animate-pulse">Loading recent uploads...</div>;
    if (error) return null; // Hide on error to be unobtrusive
    if (uploads.length === 0) return compact ? null : <div className="text-gray-500">No recent uploads found.</div>;

    const stalledAfterMs = 15 * 60 * 1000;

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
                {uploads.map((upload) => {
                    const uploadedAt = new Date(upload.uploaded_at);
                    const isQueued = upload.upload_status === 'queued';
                    const isParsing = upload.upload_status === 'parsing';
                    const isActive = isQueued || isParsing;
                    const isStalled = isActive && (Date.now() - uploadedAt.getTime()) > stalledAfterMs;
                    const isFailed = upload.upload_status === 'failed';
                    const statusLabel = isStalled ? 'Stalled' : isQueued ? 'Queued' : isParsing ? 'Parsing...' : isFailed ? 'Failed' : null;
                    const statusClass = isStalled || isFailed
                        ? 'text-red-500 bg-red-900/30'
                        : 'text-yellow-500 bg-yellow-900/30 animate-pulse';

                    return (
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
                                    {statusLabel && (
                                        <span
                                            className={`${statusClass} text-[10px] px-1.5 py-0.5 rounded`}
                                            title={upload.error_message || undefined}
                                        >
                                            {statusLabel}
                                        </span>
                                    )}
                                </div>

                                {!compact && (
                                    <div className="flex gap-4 text-gray-500 mt-1">
                                        <span>{uploadedAt.toLocaleDateString()}</span>
                                        {upload.track_code && <span>{upload.track_code}</span>}
                                        {upload.race_date && <span>{upload.race_date}</span>}
                                    </div>
                                )}
                                {compact && (
                                    <div className="text-gray-500 text-[10px] truncate">
                                        {uploadedAt.toLocaleDateString()}
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

                            <div className="ml-3 flex items-center gap-2">
                                <a
                                    href={`${baseUrl}/api/uploads/${upload.filename}`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-gray-600 group-hover:text-purple-400 transition"
                                    title="View PDF"
                                >
                                    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                                    </svg>
                                </a>
                                {!compact && (
                                    <button
                                        type="button"
                                        onClick={() => handleReprocess(upload)}
                                        disabled={isActive}
                                        className="text-gray-600 hover:text-blue-400 disabled:opacity-30 disabled:cursor-not-allowed transition"
                                        title="Reprocess upload"
                                    >
                                        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v6h6M20 20v-6h-6M5.64 18.36A9 9 0 0018.36 5.64M18.36 5.64H14M18.36 5.64V10M18.36 5.64A9 9 0 005.64 18.36M5.64 18.36H10M5.64 18.36V14" />
                                        </svg>
                                    </button>
                                )}
                                <button
                                    type="button"
                                    onClick={() => handleDelete(upload)}
                                    disabled={isActive}
                                    className="text-gray-600 hover:text-red-400 disabled:opacity-30 disabled:cursor-not-allowed transition"
                                    title="Remove upload"
                                >
                                    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7M10 11v6M14 11v6M9 7V4h6v3M4 7h16" />
                                    </svg>
                                </button>
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
