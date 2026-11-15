import sys
import webbrowser
import uvicorn

def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    port = 8000
    host = "127.0.0.1"
    url = f"http://{host}:{port}"
    
    print("\n" + "="*60)
    print("  * Starting LlamaReader Web UI")
    print(f"  * App URL: {url}")
    print("  * Press Ctrl+C in this terminal to stop the server.")
    print("="*60 + "\n")
    
    # Optional auto-open browser in a separate thread/timer
    try:
        webbrowser.open(url)
    except Exception:
        pass
        
    uvicorn.run("app.main:app", host=host, port=port, reload=False)

if __name__ == "__main__":
    main()
