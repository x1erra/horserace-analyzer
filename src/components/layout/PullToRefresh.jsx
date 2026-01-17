import { useState, useEffect, useRef } from 'react';

const PullToRefresh = ({ children }) => {
    const [startPoint, setStartPoint] = useState(0);
    const [pullChange, setPullChange] = useState(0);
    const [loading, setLoading] = useState(false);
    const contentRef = useRef(null);
    const refreshThreshold = 150; // pixels to pull down to trigger refresh

    useEffect(() => {
        // Prevent default pull-to-refresh behavior in some browsers if needed
        // focusing mainly on custom implementation

        // Add non-passive event listener to prevent default scrolling behavior when pulling
        const element = contentRef.current;
        if (!element) return;

        /* 
           Note: We are not preventing default touch behavior globally to keep normal scrolling.
           We only want to intercept when at the top.
        */
    }, []);

    const initLoading = () => {
        setLoading(true);
        // Simulate refresh or actually reload
        window.location.reload();
    };

    const pullStart = (e) => {
        const { screenY } = e.targetTouches[0];
        // Only enable pull if at the top of the page
        if (window.scrollY === 0) {
            setStartPoint(screenY);
        }
    };

    const pull = (e) => {
        const { screenY } = e.targetTouches[0];
        // Only pull if we started at the top and are pulling down
        if (window.scrollY === 0 && startPoint > 0 && screenY > startPoint) {
            const change = screenY - startPoint;
            // Add some resistance (logarithmic or just division)
            // limit the pull to a max visual distance for better feel
            const resistance = change * 0.5;
            setPullChange(resistance);
        }
    };

    const endPull = (e) => {
        if (!startPoint) return;

        if (pullChange > refreshThreshold) {
            initLoading();
        } else {
            setPullChange(0);
            setStartPoint(0);
        }
    };

    return (
        <div
            ref={contentRef}
            onTouchStart={pullStart}
            onTouchMove={pull}
            onTouchEnd={endPull}
            className="min-h-screen relative"
        >
            {/* Loading Indicator */}
            <div
                className="fixed top-0 left-0 w-full flex justify-center items-center pointer-events-none z-50 transition-transform duration-200"
                style={{
                    height: `${Math.min(pullChange, 200)}px`, // cap the visual height
                    opacity: pullChange > 0 ? 1 : 0,
                    transform: `translateY(${pullChange > 0 ? 0 : -50}px)`
                }}
            >
                <div className="bg-white/90 backdrop-blur-sm rounded-full p-2 shadow-lg text-gray-800 flex items-center justify-center">
                    {loading ? (
                        <div className="animate-spin h-6 w-6 border-2 border-gray-800 border-t-transparent rounded-full"></div>
                    ) : (
                        <svg
                            className={`w-6 h-6 transform transition-transform duration-300 ${pullChange > refreshThreshold ? 'rotate-180' : ''}`}
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                        >
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
                        </svg>
                    )}
                </div>
            </div>

            {/* Main Content with transform */}
            <div
                style={{
                    transform: `translateY(${pullChange}px)`,
                    transition: pullChange === 0 ? 'transform 0.3s ease-out' : 'none'
                }}
            >
                {children}
            </div>
        </div>
    );
};

export default PullToRefresh;
