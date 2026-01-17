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
            <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-purple-500"></div>
        </div>;
    }

    if (isAuthenticated) {
        return children;
    }

    return (
        <div className="min-h-screen bg-black flex items-center justify-center p-4">
            <div className="w-full max-w-md bg-black rounded-xl shadow-2xl border border-purple-900/30 p-8">
                <div className="text-center mb-8">
                    <div className="flex justify-center mb-6">
                        <img src="/horse_logo.png" alt="TrackData Logo" className="w-24 h-24 object-contain" />
                    </div>
                    <h1 className="text-3xl font-bold text-white mb-2">TrackData</h1>
                    <p className="text-stone-400">Please enter your password to continue.</p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-6">
                    <div>
                        <input
                            type="password"
                            placeholder="Enter Password"
                            className="w-full px-4 py-3 bg-stone-800 border border-stone-700 rounded-lg text-white placeholder-stone-500 focus:outline-none focus:ring-2 focus:ring-purple-500/50 transition-all font-mono"
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
                        className="w-full py-3 bg-black border border-purple-900/50 hover:bg-purple-900/20 hover:border-purple-500/50 text-white font-semibold rounded-lg transition-all shadow-[0_0_15px_rgba(147,51,234,0.1)]"
                    >
                        Unlock Application
                    </button>
                </form>

                <div className="mt-8 text-center">
                    <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-stone-800 border border-stone-700">
                        <svg className="w-3 h-3 text-purple-500" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clipRule="evenodd" />
                        </svg>
                        <span className="text-[10px] uppercase tracking-widest text-stone-500 font-medium">Secured by AES-256</span>
                    </div>
                    <p className="mt-6 text-xs text-stone-600">
                        TrackData &copy; {new Date().getFullYear()}
                    </p>
                </div>
            </div>
        </div>
    );
};

export default PasswordGate;
