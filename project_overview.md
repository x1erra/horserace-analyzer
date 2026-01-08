# Horse Racing Analyzer Project Overview

## Project Description
This is a modern web app for horse racing analysis, built with a sleek, Apple-like polish: clean high-contrast UI (dark theme with black backgrounds, purple accents, white text), subtle animations, responsive layouts, and intuitive navigation. The frontend uses React with Vite, Tailwind CSS for styling, React Router for navigation, React Icons for visuals, and Chart.js for charts/visualizations.

The app analyzes horse racing data from PDFs (e.g., Daily Racing Form for upcoming races) and web-crawled sources (e.g., Equibase for past results). It provides dashboards, detailed views, predictions, and tools for insights and probability estimation.

Key features:
- PDF parsing for uploaded Daily Racing Form (DRF) files to extract race data for upcoming events.
- Web crawling (via firecrawl or similar) for past race results from Equibase.
- Data storage (e.g., JSON files or future database) for races, horses, results, and stats.
- Dynamic pages with real-time data fetching via Axios from a Flask backend API.
- Gorgeous UI: Mobile-responsive sidebar with toggle, grid layouts, hover effects, fade-in animations (via Framer Motion), and premium feel.

Backend: Python with Flask to serve parsed JSON data; cron-scheduled crawling/parsing.

GitHub repo: Set up for version control and collaboration.

## Page Breakdown and Functionality
The app's navigation sidebar includes the following pages. Development will proceed one page at a time, starting from foundational setup and integrating parsing/crawling as needed.

### Upload
- **Purpose**: Allows users to upload a Daily Racing Form (DRF) PDF for an upcoming race that hasn't occurred yet.
- **Functionality**:
  - File upload interface (drag-and-drop or select).
  - Trigger PDF parser (e.g., using PyPDF2 in backend) to extract key data: race conditions, horse entries (names, jockeys, trainers, weights, odds, etc.), pace figures, and other stats.
  - Store parsed data (e.g., as JSON in a dated file or database).
  - Add the upcoming race to the Dashboard and Races pages for analysis.
  - Success feedback: Confirmation message, preview of extracted data.
- **Integration**: Backend endpoint to handle upload and parsing; frontend uses FormData for submission.

### Dashboard
- **Purpose**: Overview of today's or upcoming races, primarily from user-uploaded DRF PDFs.
- **Functionality**:
  - Display grid of race cards with summaries (e.g., race number, track, date, top horse preview, win prob placeholder).
  - "Analyze" button on each card links to a detailed race page (e.g., RaceDetails), where calculations/retrievals from parsed PDF data are performed (e.g., probability estimates, stats visualizations).
  - Dynamic data fetching from backend API.
  - Responsive grid: 1-col mobile, multi-col desktop.
- **Integration**: Fetch from API; use placeholders until real data; add filters for date/track.

### Races
- **Purpose**: Comprehensive list of all races—past (crawled with results) and upcoming (from uploads).
- **Functionality**:
  - Filterable/searchable list or grid of race cards.
  - Past races include results (winners, payouts, times).
  - Upcoming races link to analysis features.
  - Simple navigation to individual race details.
  - Draw from stored data for calculations/operations.
- **Integration**: Combine crawled (Equibase) and parsed (DRF) data; backend serves unified list.

### Horses
- **Purpose**: Library for searching and viewing horse profiles and stats.
- **Functionality**:
  - Search bar to query horse names from stored data (crawled or parsed).
  - Grid of horse cards with basic stats (e.g., wins, speed figures, recent races).
  - Each horse links to its own detail page: In-depth stats, race history, jockey/trainer associations, visualizations (e.g., performance charts).
  - Stats sourced from web crawling (past) or PDF parsing (upcoming).
- **Integration**: Backend API for search/queries; potential database for efficient lookups.

### Predictions
- **Purpose**: Generate and display race predictions based on parsed/crawled data. (Note: This page was in the sidebar but not detailed in the latest plan; assuming it fits for probability estimation.)
- **Functionality**:
  - Sortable table of predictions per race (e.g., win probabilities, top contenders).
  - Detailed analysis section: Contender lists, key takeaways, final prediction, notes.
  - Use ML/models (future) or rule-based calcs from stats like pace, odds, history.
  - Link from Dashboard/Races.
- **Integration**: Compute on-the-fly or pre-store; visualize with Chart.js.

### Results
- **Purpose**: Archive of all crawled past race results for reference and calculations.
- **Functionality**:
  - List/table of results by date/track/race.
  - Details: Winners, payouts, fractional times, comments.
  - Searchable/filterable.
  - Data used for backend operations (e.g., historical analysis, probability tuning).
- **Integration**: Crawled daily from Equibase; parsed and stored as JSON; API endpoint for querying.

## Development Gameplan
- **Approach**: Build one page at a time, starting with Upload (for data ingestion), then Dashboard, Races, Horses, Predictions, Results.
- **Data Flow**:
  - Uploads → Parse PDF → Store JSON → Feed to Dashboard/Races.
  - Crawling → Parse results → Store JSON → Feed to Races/Results/Horses.
  - All pages fetch dynamically via API for freshness.
- **Tech Notes**:
  - Always provide full updated files (not just changes) for safety.
  - Ensure Apple-like polish: Subtle animations, clean layouts, purple/black/white theme.
  - Future expansions: Betting simulator, favorites, ML for predictions.
- **Storage**: Start with file-based JSON; evolve to SQLite or cloud DB if needed.
- **Crawling/Parsing**: Use firecrawl for Equibase; PyPDF2/regex for PDFs; cron for daily updates.
