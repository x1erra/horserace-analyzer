import React, { useState, useEffect } from 'react';

const PasswordGate = ({ children }) => {
    const [password, setPassword] = useState('');
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const [error, setError] = useState('');
    const [isLoading, setIsLoading] = useState(true);

    const APP_PASSWORD = import.meta.env.VITE_APP_PASSWORD;

    useEffect(() => {
        const authStatus = localStorage.getItem('isAppAuthenticated');
        if (authStatus === 'true') {
            setIsAuthenticated(true);
        }
        setIsLoading(false);
    }, []);

    const handleSubmit = (e) => {
        e.preventDefault();

        if (!APP_PASSWORD) {
            setError('System Error: Password not configured. Please check .env file.');
            return;
        }

        if (password === APP_PASSWORD) {
            localStorage.setItem('isAppAuthenticated', 'true');
            setIsAuthenticated(true);
            setError('');
        } else {
            setError('Incorrect password. Please try again.');
        }
    };

    if (isLoading) {
        return <div className="min-h-screen bg-black flex items-center justify-center">
            <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
        </div>;
    }

    if (isAuthenticated) {
        return children;
    }

    return (
        <div className="min-h-screen bg-black flex items-center justify-center p-4">
            <div className="w-full max-w-md bg-stone-900 rounded-xl shadow-2xl border border-stone-800 p-8">
                <div className="text-center mb-8">
                    <div className="inline-block p-4 rounded-full bg-blue-500/10 mb-4">
                        <svg className="w-8 h-8 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                        </svg>
                    </div>
                    <h1 className="text-2xl font-bold text-white mb-2">Restricted Access</h1>
                    <p className="text-stone-400">Please enter your password to continue to TrackData.</p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-6">
                    <div>
                        <input
                            type="password"
                            placeholder="Enter Password"
                            className="w-full px-4 py-3 bg-stone-800 border border-stone-700 rounded-lg text-white placeholder-stone-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50 transition-all"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            autoFocus
                        />
                    </div>

                    {error && (
                        <div className="bg-red-500/10 border border-red-500/50 text-red-500 px-4 py-3 rounded-lg text-sm text-center">
                            {error}
                        </div>
                    )}

                    <button
                        type="submit"
                        className="w-full py-3 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-lg transition-colors shadow-lg shadow-blue-900/20"
                    >
                        Unlock Application
                    </button>
                </form>

                <div className="mt-8 text-center">
                    <p className="text-xs text-stone-600">
                        Securely encrypted access. TrackData &copy; {new Date().getFullYear()}
                    </p>
                </div>
            </div>
        </div>
    );
};

export default PasswordGate;
