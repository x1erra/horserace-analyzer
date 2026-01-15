
import subprocess
import os

def test_powershell():
    url = "https://www.equibase.com/static/entry/PRX011426USA-EQB.html"
    print(f"Testing PowerShell Fetch: {url}")
    
    outfile = "probe_prx.html"
    if os.path.exists(outfile):
        os.remove(outfile)
        
    cmd = ["powershell", "-Command", f"Invoke-WebRequest -Uri '{url}' -OutFile '{outfile}'"]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        print("Return Code:", result.returncode)
        if result.stderr:
            print("Stderr:", result.stderr)
            
        if os.path.exists(outfile):
            size = os.path.getsize(outfile)
            print(f"Downloaded File Size: {size}")
            if size > 5000:
                print("SUCCESS: File is large.")
            else:
                print("FAIL: File to small.")
        else:
             print("FAIL: File not created.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_powershell()
