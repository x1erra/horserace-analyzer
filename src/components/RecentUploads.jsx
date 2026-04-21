import { useState, useEffect, useCallback } from 'react';
import {
    HiOutlineCheckCircle,
    HiOutlineClock,
    HiOutlineDocumentText,
    HiOutlineEye,
    HiOutlineRefresh,
    HiOutlineTrash,
    HiOutlineXCircle,
} from 'react-icons/hi';

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

    if (loading) return <div className="rounded-lg border border-gray-900 bg-black p-5 text-sm text-gray-500 animate-pulse">Loading recent uploads...</div>;
    if (error) return null; // Hide on error to be unobtrusive
    if (uploads.length === 0) return compact ? null : <div className="rounded-lg border border-gray-900 bg-black p-5 text-gray-500">No recent uploads found.</div>;

    const stalledAfterMs = 15 * 60 * 1000;

    return (
        <div className={`rounded-lg border border-purple-900/50 bg-black shadow-[0_0_24px_rgba(147,51,234,0.08)] ${compact ? 'p-4' : 'p-5'}`}>
            <div className="mb-4 flex items-center justify-between gap-4">
                <div>
                    <h4 className={`font-semibold text-white ${compact ? 'text-sm' : 'text-lg'}`}>
                        {compact ? 'Recent Uploads' : 'Upload History'}
                    </h4>
                    {!compact && <p className="mt-1 text-sm text-gray-500">Recent local PDFs and parser status</p>}
                </div>
                {!compact && (
                    <button
                        onClick={fetchUploads}
                        className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-gray-800 text-gray-400 transition hover:border-purple-500/50 hover:text-purple-300"
                        title="Refresh"
                        aria-label="Refresh uploads"
                    >
                        <HiOutlineRefresh className="h-5 w-5" />
                    </button>
                )}
            </div>

            <div className="divide-y divide-gray-900">
                {uploads.map((upload) => {
                    const uploadedAt = new Date(upload.uploaded_at);
                    const isQueued = upload.upload_status === 'queued';
                    const isParsing = upload.upload_status === 'parsing';
                    const isActive = isQueued || isParsing;
                    const isStalled = isActive && (Date.now() - uploadedAt.getTime()) > stalledAfterMs;
                    const isFailed = upload.upload_status === 'failed';
                    const statusLabel = isStalled ? 'Stalled' : isQueued ? 'Queued' : isParsing ? 'Parsing...' : isFailed ? 'Failed' : null;
                    const statusClass = isStalled || isFailed
                        ? 'border-red-500/30 bg-red-500/10 text-red-300'
                        : isActive
                            ? 'border-yellow-500/30 bg-yellow-500/10 text-yellow-300'
                            : 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300';
                    const RowStatusIcon = isStalled || isFailed ? HiOutlineXCircle : isActive ? HiOutlineClock : HiOutlineCheckCircle;

                    return (
                        <div
                            key={upload.id}
                            className={`group flex items-center justify-between gap-3 ${compact ? 'py-2 text-xs' : 'py-4 text-sm'}`}
                        >
                            <div className="flex min-w-0 flex-1 items-start gap-3">
                                {!compact && (
                                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md border border-gray-800 bg-gray-950 text-gray-400">
                                        <HiOutlineDocumentText className="h-5 w-5" />
                                    </div>
                                )}
                                <div className="min-w-0 flex-1">
                                    <a
                                        href={`${baseUrl}/api/uploads/${upload.filename}`}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="block truncate font-medium text-purple-300 transition hover:text-purple-100"
                                        title={upload.filename}
                                    >
                                        {upload.filename}
                                    </a>

                                    <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-2 text-xs text-gray-500">
                                        <span>{uploadedAt.toLocaleDateString()}</span>
                                        {upload.track_code && <span>{upload.track_code}</span>}
                                        {upload.race_date && <span>{upload.race_date}</span>}
                                        <span
                                            className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[10px] font-medium ${statusClass}`}
                                            title={upload.error_message || undefined}
                                        >
                                            <RowStatusIcon className="h-3.5 w-3.5" />
                                            {statusLabel || 'Complete'}
                                        </span>
                                    </div>
                                </div>
                            </div>

                            {!compact && upload.races_extracted > 0 && (
                                <div className="hidden text-right text-xs text-gray-400 sm:block">
                                    <div>{upload.races_extracted} races</div>
                                    <div>{upload.entries_extracted} entries</div>
                                </div>
                            )}

                            <div className="flex shrink-0 items-center gap-1">
                                <a
                                    href={`${baseUrl}/api/uploads/${upload.filename}`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="inline-flex h-9 w-9 items-center justify-center rounded-md text-gray-600 transition hover:bg-purple-500/10 hover:text-purple-300"
                                    title="View PDF"
                                    aria-label={`View ${upload.filename}`}
                                >
                                    <HiOutlineEye className="h-5 w-5" />
                                </a>
                                {!compact && (
                                    <button
                                        type="button"
                                        onClick={() => handleReprocess(upload)}
                                        disabled={isActive}
                                        className="inline-flex h-9 w-9 items-center justify-center rounded-md text-gray-600 transition hover:bg-blue-500/10 hover:text-blue-300 disabled:cursor-not-allowed disabled:opacity-30"
                                        title="Reprocess upload"
                                        aria-label={`Reprocess ${upload.filename}`}
                                    >
                                        <HiOutlineRefresh className="h-5 w-5" />
                                    </button>
                                )}
                                <button
                                    type="button"
                                    onClick={() => handleDelete(upload)}
                                    disabled={isActive}
                                    className="inline-flex h-9 w-9 items-center justify-center rounded-md text-gray-600 transition hover:bg-red-500/10 hover:text-red-300 disabled:cursor-not-allowed disabled:opacity-30"
                                    title="Remove upload"
                                    aria-label={`Remove ${upload.filename}`}
                                >
                                    <HiOutlineTrash className="h-5 w-5" />
                                </button>
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
