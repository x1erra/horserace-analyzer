import { useState } from 'react';

export default function Upload() {
    const [selectedFile, setSelectedFile] = useState(null);
    const [uploadStatus, setUploadStatus] = useState('');

    // Handle file selection
    const handleFileChange = (e) => {
        const file = e.target.files[0];
        if (file && file.type === 'application/pdf') {
            setSelectedFile(file);
            setUploadStatus('');
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
        } else {
            setSelectedFile(null);
            setUploadStatus('Please drop a PDF file.');
        }
    };

    // Handle upload submit (placeholder for parsing)
    const handleSubmit = (e) => {
        e.preventDefault();
        if (selectedFile) {
            // Placeholder: Later, send to backend for parsing (e.g., via FormData axios post)
            console.log('Uploading file:', selectedFile.name);
            setUploadStatus('File uploaded successfully. Parsing in progress...');
            setSelectedFile(null);
        }
    };

    return (
        <div className="space-y-8">
            <h3 className="text-3xl font-bold text-white">Upload Daily Racing Form</h3>
            <p className="text-sm text-gray-400 mb-4">Upload PDF for parsing (results will show in dashboard after processing).</p>

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
                    />
                    <label htmlFor="file-upload" className="bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded-md transition duration-200 cursor-pointer">
                        Select PDF
                    </label>
                    {selectedFile && <p className="text-purple-400 mt-4">Selected: {selectedFile.name}</p>}
                </div>
                <button type="submit" disabled={!selectedFile} className="w-full bg-gradient-to-r from-purple-600 to-purple-700 hover:from-purple-700 hover:to-purple-800 text-white py-3 rounded-md transition duration-200 font-medium disabled:opacity-50 disabled:cursor-not-allowed">
                    Upload & Parse
                </button>
            </form>

            {uploadStatus && <p className="text-sm text-gray-400 flex justify-center">{uploadStatus}</p>}
        </div>
    );
}
