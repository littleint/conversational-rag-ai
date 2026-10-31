import os
import sys
import webbrowser
import uvicorn

def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    is_cloud = "PORT" in os.environ
    port = int(os.getenv("PORT", 8000))
    host = "0.0.0.0"
    url = f"http://0.0.0.0:{port}" if is_cloud else f"http://localhost:{port}"
    
    print("\n" + "="*60)
    print("  * Starting LlamaReader Web UI")
    print(f"  * App URL: {url}")
    print("  * Press Ctrl+C in this terminal to stop the server.")
    print("="*60 + "\n", flush=True)
    
    # Auto-open browser only when running locally (not on cloud servers)
    if not is_cloud:
        try:
            webbrowser.open(url)
        except Exception:
            pass
        
    uvicorn.run("app.main:app", host=host, port=port, reload=False)

if __name__ == "__main__":
    main()
