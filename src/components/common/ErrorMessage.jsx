import React from 'react';
import { HiOutlineRefresh, HiOutlineExclamationCircle } from 'react-icons/hi';

const ErrorMessage = ({
    message = "Something went wrong while loading data.",
    onRetry,
    details = ""
}) => {
    const handleRefresh = () => {
        window.location.reload();
    };

    return (
        <div className="w-full max-w-2xl mx-auto my-8 animate-fadeIn">
            <div className="bg-amber-900/10 border border-amber-500/30 rounded-2xl p-6 md:p-8 backdrop-blur-sm shadow-[0_0_20px_rgba(245,158,11,0.05)]">
                <div className="flex flex-col items-center text-center">
                    <div className="w-16 h-16 bg-amber-500/10 rounded-full flex items-center justify-center mb-6">
                        <HiOutlineExclamationCircle className="w-10 h-10 text-amber-500" />
                    </div>

                    <h4 className="text-xl font-bold text-white mb-3">
                        Notice: Connection Issue
                    </h4>

                    <p className="text-gray-300 leading-relaxed max-w-md">
                        {message} This often happens due to a transient network glitch or a brief server pause—especially on mobile devices.
                    </p>

                    <div className="mt-8 flex justify-center w-full">
                        <button
                            onClick={onRetry || handleRefresh}
                            className="flex items-center justify-center gap-3 bg-amber-500/10 border border-amber-500/30 hover:bg-amber-500/20 hover:border-amber-500/50 text-amber-400 px-10 py-4 rounded-2xl transition-all font-bold text-lg shadow-[0_0_20px_rgba(245,158,11,0.1)] group"
                        >
                            <HiOutlineRefresh className="w-6 h-6 group-hover:rotate-180 transition-transform duration-500" />
                            Refresh & Retry
                        </button>
                    </div>

                    {details && (
                        <div className="mt-8 pt-6 border-t border-amber-500/10 w-full">
                            <p className="text-xs text-amber-500/50 uppercase tracking-widest font-mono">
                                Technical Details (Optional)
                            </p>
                            <p className="text-xs text-gray-500 mt-2 font-mono break-all">
                                {details}
                            </p>
                        </div>
                    )}
                </div>
            </div>

            <div className="mt-4 text-center">
                <p className="text-sm text-gray-500 italic">
                    Tip: If the problem persists, please check your internet connection and try again in a few moments.
                </p>
            </div>
        </div>
    );
};

export default ErrorMessage;
