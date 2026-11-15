import os
import sys
import webbrowser
import uvicorn

def main():
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    # Read dynamic PORT from cloud environment (Render, Railway), fallback to 8000 locally
    port = int(os.environ.get("PORT", 8000))
    # Bind to 0.0.0.0 so external cloud traffic reaches the container
    host = os.environ.get("HOST", "0.0.0.0")
    
    print("\n" + "="*60)
    print("  * Starting LlamaReader Web UI")
    print(f"  * App URL: http://{host}:{port}")
    print("  * Press Ctrl+C in this terminal to stop the server.")
    print("="*60 + "\n")
    
    # Auto-open browser only on local desktop (when PORT is not set by cloud host)
    if not os.environ.get("PORT"):
        try:
            webbrowser.open(f"http://127.0.0.1:{port}")
        except Exception:
            pass
        
    uvicorn.run("app.main:app", host=host, port=port, reload=False)

if __name__ == "__main__":
    main()
