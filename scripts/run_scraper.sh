#!/bin/bash
# Script to run the event scraper, suitable for cron scheduling
#
# Cron examples:
#   Daily at 6 AM:     0 6 * * * /path/to/run_scraper.sh
#   Every 12 hours:    0 */12 * * * /path/to/run_scraper.sh
#   Weekly on Monday:  0 6 * * 1 /path/to/run_scraper.sh

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Change to project directory
cd "$PROJECT_DIR"

# Activate virtual environment if it exists
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Set timestamp for logging
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")

# Run the scraper
echo "[$TIMESTAMP] Starting event scraper..."
python -m src.main 2>&1 | tee -a "logs/cron_$TIMESTAMP.log"

# Capture exit code
EXIT_CODE=${PIPESTATUS[0]}

if [ $EXIT_CODE -eq 0 ]; then
    echo "[$TIMESTAMP] Scraper completed successfully"
else
    echo "[$TIMESTAMP] Scraper failed with exit code $EXIT_CODE"
fi

exit $EXIT_CODE
