import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import {
    HiOutlineCheckCircle,
    HiOutlineClock,
    HiOutlineDatabase,
    HiOutlineDocumentText,
    HiOutlineExclamationCircle,
    HiOutlineInformationCircle,
    HiOutlineUpload,
} from 'react-icons/hi';
import RecentUploads from '../components/RecentUploads';

export default function Upload() {
    const navigate = useNavigate();
    const [selectedFile, setSelectedFile] = useState(null);
    const [dragActive, setDragActive] = useState(false);
    const [uploadStatus, setUploadStatus] = useState('');
    const [uploadStatusType, setUploadStatusType] = useState('idle');
    const [uploading, setUploading] = useState(false);
    const [parseResult, setParseResult] = useState(null);
    const [historyRefreshToken, setHistoryRefreshToken] = useState(0);

    const isPdfFile = (file) => {
        return file && (file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf'));
    };

    // Handle file selection
    const handleFileChange = (e) => {
        const file = e.target.files[0];
        if (isPdfFile(file)) {
            setSelectedFile(file);
            setUploadStatus('');
            setUploadStatusType('idle');
            setParseResult(null);
        } else {
            setSelectedFile(null);
            setUploadStatus('Please select a PDF file.');
            setUploadStatusType('error');
        }
    };

    // Handle file drop
    const handleDrop = (e) => {
        e.preventDefault();
        const file = e.dataTransfer.files[0];
        if (isPdfFile(file)) {
            setSelectedFile(file);
            setUploadStatus('');
            setUploadStatusType('idle');
            setParseResult(null);
        } else {
            setSelectedFile(null);
            setUploadStatus('Please drop a PDF file.');
            setUploadStatusType('error');
        }
    };

    // Handle upload submit
    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!selectedFile) return;

        try {
            setUploading(true);
            setUploadStatus('Uploading PDF...');
            setUploadStatusType('info');
            setParseResult(null);

            const formData = new FormData();
            formData.append('file', selectedFile);

            const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:5001';
            const response = await axios.post(
                `${baseUrl}/api/upload-drf`,
                formData,
                {
                    headers: {
                        'Content-Type': 'multipart/form-data',
                    },
                    timeout: 240000,
                }
            );

            if (response.data.queued) {
                setUploadStatus('Upload queued. Parsing will continue in the background.');
                setUploadStatusType('info');
                setSelectedFile(null);
                setHistoryRefreshToken((value) => value + 1);
            } else if (response.data.success) {
                setParseResult(response.data);
                setUploadStatus('Success! PDF parsed successfully.');
                setUploadStatusType('success');
                setSelectedFile(null);
                setHistoryRefreshToken((value) => value + 1);
            } else {
                setUploadStatus(`Error: ${response.data.error || 'Upload failed'}`);
                setUploadStatusType('error');
                setHistoryRefreshToken((value) => value + 1);
            }
        } catch (err) {
            console.error('Upload error:', err);
            const errorMsg = err.response?.data?.error || err.message || 'Upload failed';
            setUploadStatus(`Error: ${errorMsg}`);
            setUploadStatusType('error');
            setHistoryRefreshToken((value) => value + 1);
        } finally {
            setUploading(false);
        }
    };

    const statusClasses = {
        info: 'bg-blue-500/10 border-blue-500/40 text-blue-200',
        success: 'bg-emerald-500/10 border-emerald-500/40 text-emerald-200',
        error: 'bg-red-500/10 border-red-500/40 text-red-200',
        idle: 'bg-gray-900/40 border-gray-700 text-gray-300'
    };
    const statusIcon = {
        info: HiOutlineClock,
        success: HiOutlineCheckCircle,
        error: HiOutlineExclamationCircle,
        idle: HiOutlineInformationCircle
    };
    const StatusIcon = statusIcon[uploadStatusType] || statusIcon.idle;

    return (
        <div className="space-y-6">
            <div className="space-y-3">
                <h3 className="text-3xl font-bold text-white md:text-4xl">DRF Uploads</h3>
                <p className="max-w-2xl text-sm leading-6 text-gray-400">
                    Queue dense Daily Racing Form PDFs for local parsing and review extracted race cards as soon as processing finishes.
                </p>
            </div>

            {/* Status Messages */}
            {uploadStatus && (
                <div className={`flex items-center gap-3 rounded-md border p-4 ${statusClasses[uploadStatusType] || statusClasses.idle}`}>
                    <StatusIcon className="h-5 w-5 shrink-0" />
                    <p className="text-sm font-medium">
                        {uploadStatus}
                    </p>
                </div>
            )}

            <div className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(420px,0.9fr)]">
                <form
                    onSubmit={handleSubmit}
                    className="rounded-lg border border-purple-900/50 bg-black shadow-[0_0_24px_rgba(147,51,234,0.08)] opacity-0 animate-fadeIn"
                    style={{ animationDelay: '50ms' }}
                >
                    <div className="border-b border-purple-900/40 p-5">
                        <h4 className="text-lg font-semibold text-white">New Upload</h4>
                        <p className="mt-1 text-sm text-gray-500">PDF only, 16 MB maximum</p>
                    </div>

                    <div className="space-y-5 p-5">
                        <label
                            htmlFor="file-upload"
                            onDrop={(e) => {
                                setDragActive(false);
                                handleDrop(e);
                            }}
                            onDragOver={(e) => {
                                e.preventDefault();
                                setDragActive(true);
                            }}
                            onDragLeave={() => setDragActive(false)}
                            className={`block cursor-pointer rounded-lg border-2 border-dashed p-8 text-center transition ${dragActive
                                ? 'border-emerald-400 bg-emerald-500/10'
                                : 'border-purple-900/60 bg-gray-950/40 hover:border-purple-500/70 hover:bg-purple-500/10'
                                } ${uploading ? 'pointer-events-none opacity-60' : ''}`}
                        >
                            <input
                                type="file"
                                accept="application/pdf"
                                onChange={handleFileChange}
                                className="hidden"
                                id="file-upload"
                                disabled={uploading}
                            />
                            <span className="mx-auto flex h-16 w-16 items-center justify-center rounded-md border border-gray-700 bg-black text-gray-300">
                                {selectedFile ? <HiOutlineDocumentText className="h-8 w-8 text-emerald-300" /> : <HiOutlineUpload className="h-8 w-8" />}
                            </span>
                            <span className="mt-5 block text-lg font-semibold text-white">
                                {selectedFile ? selectedFile.name : 'Drop DRF PDF'}
                            </span>
                            <span className="mt-2 block text-sm text-gray-500">
                                {selectedFile
                                    ? `${(selectedFile.size / 1024 / 1024).toFixed(2)} MB ready`
                                    : 'Click to browse or drag a file here'}
                            </span>
                        </label>

                        <div className="flex flex-col gap-3 sm:flex-row">
                            <button
                                type="submit"
                                disabled={!selectedFile || uploading}
                                className="inline-flex flex-1 items-center justify-center gap-2 rounded-md border border-emerald-500/40 bg-emerald-500/10 px-5 py-3 text-sm font-semibold text-emerald-100 transition hover:border-emerald-400 hover:bg-emerald-500/20 disabled:cursor-not-allowed disabled:opacity-40"
                            >
                                {uploading ? <HiOutlineClock className="h-5 w-5 animate-spin" /> : <HiOutlineUpload className="h-5 w-5" />}
                                {uploading ? 'Uploading' : 'Queue Upload'}
                            </button>
                            <button
                                type="button"
                                onClick={() => {
                                    setSelectedFile(null);
                                    setParseResult(null);
                                    setUploadStatus('');
                                    setUploadStatusType('idle');
                                }}
                                disabled={uploading || (!selectedFile && !parseResult && !uploadStatus)}
                                className="inline-flex items-center justify-center rounded-md border border-gray-800 px-5 py-3 text-sm font-medium text-gray-300 transition hover:border-gray-600 hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
                            >
                                Clear
                            </button>
                        </div>
                    </div>
                </form>

                <RecentUploads limit={10} refreshToken={historyRefreshToken} />
            </div>

            {/* Parse Results */}
            {parseResult && (
                <div className="rounded-lg border border-emerald-500/30 bg-black p-6 shadow-md opacity-0 animate-fadeIn">
                    <h4 className="mb-4 text-xl font-semibold text-white">Parse Results</h4>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <div className="rounded-md border border-gray-800 p-4">
                            <p className="text-gray-400 text-sm">Track</p>
                            <p className="text-white text-2xl font-bold">{parseResult.track_code}</p>
                        </div>
                        <div className="rounded-md border border-gray-800 p-4">
                            <p className="text-gray-400 text-sm">Date</p>
                            <p className="text-white text-2xl font-bold">{parseResult.race_date}</p>
                        </div>
                        <div className="rounded-md border border-gray-800 p-4">
                            <p className="text-gray-400 text-sm">Races</p>
                            <p className="text-emerald-300 text-2xl font-bold">{parseResult.races_parsed}</p>
                        </div>
                        <div className="rounded-md border border-gray-800 p-4">
                            <p className="text-gray-400 text-sm">Entries</p>
                            <p className="text-emerald-300 text-2xl font-bold">{parseResult.entries_parsed}</p>
                        </div>
                    </div>

                    <div className="flex gap-4 mt-6">
                        <button
                            onClick={() => navigate('/dashboard')}
                            className="flex-1 bg-black border border-purple-900/50 hover:bg-purple-900/20 hover:border-purple-500/50 text-white py-2 rounded-md transition shadow-[0_0_10px_rgba(147,51,234,0.1)]"
                        >
                            View Dashboard
                        </button>
                        <button
                            onClick={() => {
                                setParseResult(null);
                                setUploadStatus('');
                                setUploadStatusType('idle');
                                setSelectedFile(null);
                            }}
                            className="flex-1 bg-gray-700 hover:bg-gray-600 text-white py-2 rounded-md transition"
                        >
                            Upload Another
                        </button>
                    </div>
                </div>
            )}

            {/* Instructions */}
            <details className="rounded-lg border border-gray-900 bg-black px-5 py-4 text-sm text-gray-500">
                <summary className="cursor-pointer font-medium text-gray-300">Upload notes</summary>
                <div className="mt-4 grid gap-3 text-gray-500 md:grid-cols-3">
                    <div className="flex gap-3">
                        <HiOutlineDatabase className="mt-0.5 h-5 w-5 shrink-0 text-emerald-400" />
                        <p>PDFs are stored locally on the Umbrel-backed upload volume.</p>
                    </div>
                    <div className="flex gap-3">
                        <HiOutlineClock className="mt-0.5 h-5 w-5 shrink-0 text-blue-400" />
                        <p>Parsing runs in the background, so this page can be left or refreshed.</p>
                    </div>
                    <div className="flex gap-3">
                        <HiOutlineCheckCircle className="mt-0.5 h-5 w-5 shrink-0 text-purple-300" />
                        <p>Completed race cards are available from Dashboard and race views.</p>
                    </div>
                </div>
            </details>
        </div>
    );
}
