export default function Header() {
    return (
        <header className="bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 px-6 lg:px-10 py-4">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
                        Dashboard
                    </h2>
                    <p className="text-gray-600 dark:text-gray-400 mt-1">
                        Today's races • Model performance • Value alerts
                    </p>
                </div>

                <div className="flex items-center gap-6">
                    <div className="text-right">
                        <p className="text-sm text-gray-500 dark:text-gray-400">Model Accuracy</p>
                        <p className="text-2xl font-bold text-green-600 dark:text-green-400">78.4%</p>
                    </div>
                    <button className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-lg font-medium transition">
                        Run Today's Cards
                    </button>
                </div>
            </div>
        </header>
    );
}