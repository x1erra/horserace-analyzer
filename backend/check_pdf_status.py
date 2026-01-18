
import logging
import sys
import os
import time
import subprocess
from datetime import date

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_pdf_status():
    track_code = 'GP'
    race_date = date.today()
    
    # Construct URL variables
    mm = race_date.strftime('%m')
    dd = race_date.strftime('%d')
    yy = race_date.strftime('%y')
    
    logger.info("Running PowerShell download command for Races 1-5...")
    
    # Loop for races 1 to 5
    for r_num in range(1, 6):
        race_number = r_num
        url = f"https://www.equibase.com/static/chart/pdf/{track_code}{mm}{dd}{yy}USA{race_number}.pdf"
        logger.info(f"Checking Race {race_number}: {url}")
        
        current_ps_script = f"""
        $headers = @{{
            "User-Agent" = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            "Accept" = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
            "Accept-Language" = "en-US,en;q=0.9"
            "Referer" = "https://www.equibase.com/"
            "Sec-Ch-Ua" = '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"'
            "Sec-Ch-Ua-Mobile" = "?0"
            "Sec-Ch-Ua-Platform" = '"Windows"'
            "Sec-Fetch-Dest" = "document"
            "Sec-Fetch-Mode" = "navigate"
            "Sec-Fetch-Site" = "same-origin"
            "Sec-Fetch-User" = "?1"
            "Upgrade-Insecure-Requests" = "1"
        }}
        
        try {{
            Invoke-WebRequest -Uri '{url}' -OutFile 'temp_race_{race_number}.pdf' -Headers $headers -TimeoutSec 10 -ErrorAction Stop
            Write-Host "Success"
        }} catch {{
            Write-Host "Error: $($_.Exception.Message)"
        }}
        """
        
        cmd = [
            "powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", current_ps_script
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            output = result.stdout.strip()
            logger.info(f"Race {race_number} Status: {output}")
            
            # Clean up if success
            if "Success" in output and os.path.exists(f"temp_race_{race_number}.pdf"):
                os.remove(f"temp_race_{race_number}.pdf")
                
        except Exception as e:
            logger.error(f"Execution failed: {e}")

if __name__ == "__main__":
    check_pdf_status()
