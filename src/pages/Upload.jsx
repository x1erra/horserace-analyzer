import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';

export default function Upload() {
    const navigate = useNavigate();
    const [selectedFile, setSelectedFile] = useState(null);
    const [uploadStatus, setUploadStatus] = useState('');
    const [uploading, setUploading] = useState(false);
    const [parseResult, setParseResult] = useState(null);

    // Handle file selection
    const handleFileChange = (e) => {
        const file = e.target.files[0];
        if (file && file.type === 'application/pdf') {
            setSelectedFile(file);
            setUploadStatus('');
            setParseResult(null);
        } else {
            setSelectedFile(null);
            setUploadStatus('Please select a PDF file.');
        }
    };

    // Handle file drop
    const handleDrop = (e) => {
        e.preventDefault();
        const file = e.dataTransfer.files[0];
        if (file && file.type === 'application/pdf') {
            setSelectedFile(file);
            setUploadStatus('');
            setParseResult(null);
        } else {
            setSelectedFile(null);
            setUploadStatus('Please drop a PDF file.');
        }
    };

    // Handle upload submit
    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!selectedFile) return;

        try {
            setUploading(true);
            setUploadStatus('Uploading and parsing PDF...');
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
                    timeout: 60000, // 60 second timeout
                }
            );

            if (response.data.success) {
                setParseResult(response.data);
                setUploadStatus('Success! PDF parsed successfully.');
                setSelectedFile(null);
            } else {
                setUploadStatus(`Error: ${response.data.error || 'Upload failed'}`);
            }
        } catch (err) {
            console.error('Upload error:', err);
            const errorMsg = err.response?.data?.error || err.message || 'Upload failed';
            setUploadStatus(`Error: ${errorMsg}`);
        } finally {
            setUploading(false);
        }
    };

    return (
        <div className="space-y-8">
            <h3 className="text-3xl font-bold text-white">Upload Daily Racing Form</h3>
            <p className="text-sm text-gray-400 mb-4">
                Upload a DRF PDF to extract upcoming races. Results will appear in the Dashboard after parsing.
            </p>

            {/* Upload Form */}
            <form onSubmit={handleSubmit} className="bg-black rounded-xl shadow-md p-6 border border-purple-900/50 space-y-4 opacity-0 animate-fadeIn" style={{ animationDelay: '50ms' }}>
                <div
                    onDrop={handleDrop}
                    onDragOver={(e) => e.preventDefault()}
                    className="border-2 border-dashed border-purple-900/50 rounded-md p-8 text-center cursor-pointer hover:border-purple-600 transition duration-200"
                >
                    <p className="text-gray-300 mb-4">Drag & drop PDF here or click to select</p>
                    <input
                        type="file"
                        accept="application/pdf"
                        onChange={handleFileChange}
                        className="hidden"
                        id="file-upload"
                        disabled={uploading}
                    />
                    <label htmlFor="file-upload" className={`${uploading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'} bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded-md transition duration-200`}>
                        Select PDF
                    </label>
                    {selectedFile && (
                        <p className="text-purple-400 mt-4">
                            Selected: {selectedFile.name} ({(selectedFile.size / 1024 / 1024).toFixed(2)} MB)
                        </p>
                    )}
                </div>

                <button
                    type="submit"
                    disabled={!selectedFile || uploading}
                    className="w-full bg-gradient-to-r from-purple-600 to-purple-700 hover:from-purple-700 hover:to-purple-800 text-white py-3 rounded-md transition duration-200 font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    {uploading ? 'Uploading & Parsing...' : 'Upload & Parse'}
                </button>
            </form>

            {/* Status Messages */}
            {uploadStatus && (
                <div className={`p-4 rounded-md ${parseResult ? 'bg-green-900/20 border border-green-500/50' : 'bg-red-900/20 border border-red-500/50'}`}>
                    <p className={`${parseResult ? 'text-green-400' : 'text-red-400'} font-medium`}>
                        {uploadStatus}
                    </p>
                </div>
            )}

            {/* Parse Results */}
            {parseResult && (
                <div className="bg-black rounded-xl shadow-md p-6 border border-purple-900/50 space-y-4 opacity-0 animate-fadeIn">
                    <h4 className="text-xl font-semibold text-white mb-4">Parse Results</h4>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <div className="bg-purple-900/20 p-4 rounded-md border border-purple-900/50">
                            <p className="text-gray-400 text-sm">Track</p>
                            <p className="text-white text-2xl font-bold">{parseResult.track_code}</p>
                        </div>
                        <div className="bg-purple-900/20 p-4 rounded-md border border-purple-900/50">
                            <p className="text-gray-400 text-sm">Date</p>
                            <p className="text-white text-2xl font-bold">{parseResult.race_date}</p>
                        </div>
                        <div className="bg-purple-900/20 p-4 rounded-md border border-purple-900/50">
                            <p className="text-gray-400 text-sm">Races</p>
                            <p className="text-purple-400 text-2xl font-bold">{parseResult.races_parsed}</p>
                        </div>
                        <div className="bg-purple-900/20 p-4 rounded-md border border-purple-900/50">
                            <p className="text-gray-400 text-sm">Entries</p>
                            <p className="text-purple-400 text-2xl font-bold">{parseResult.entries_parsed}</p>
                        </div>
                    </div>

                    <div className="flex gap-4 mt-6">
                        <button
                            onClick={() => navigate('/dashboard')}
                            className="flex-1 bg-purple-600 hover:bg-purple-700 text-white py-2 rounded-md transition"
                        >
                            View Dashboard
                        </button>
                        <button
                            onClick={() => {
                                setParseResult(null);
                                setUploadStatus('');
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
            <div className="bg-black rounded-xl shadow-md p-6 border border-purple-900/50 opacity-0 animate-fadeIn" style={{ animationDelay: '100ms' }}>
                <h4 className="text-lg font-semibold text-white mb-3">How It Works</h4>
                <ol className="list-decimal list-inside space-y-2 text-gray-400 text-sm">
                    <li>Upload a Daily Racing Form (DRF) PDF for today or future races</li>
                    <li>The parser extracts all races, horses, jockeys, and race conditions</li>
                    <li>Data is stored in the database with status "upcoming"</li>
                    <li>View the races on the Dashboard to analyze and make picks</li>
                    <li>After races complete, the Equibase crawler will fetch results automatically</li>
                </ol>
            </div>

            {/* Recent Uploads (optional future enhancement) */}
            {/* Could show list of recent uploads here */}
        </div>
    );
}
