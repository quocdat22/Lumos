import os
import subprocess
import sys
import uvicorn

from lumos.config import get_settings


def run_api():
    """Start the FastAPI backend server."""
    settings = get_settings()
    print(f"Starting Lumos FastAPI server at http://{settings.backend_host}:{settings.backend_port}...")
    uvicorn.run(
        "lumos.api.main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=False,
    )


def run_ui():
    """Start the Streamlit web interface."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    app_path = os.path.join(current_dir, "ui", "app.py")
    print(f"Launching Lumos Streamlit UI...")
    subprocess.run([sys.executable, "-m", "streamlit", "run", app_path])


def main():
    """CLI entrypoint for Lumos."""
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("📚 Lumos - Native E-Book RAG Chatbot")
        print("\nUsage:")
        print("  uv run lumos api    Start the FastAPI REST backend (default: http://localhost:8000)")
        print("  uv run lumos ui     Start the Streamlit Web UI (default: http://localhost:8501)")
        sys.exit(0)

    command = sys.argv[1].lower()
    if command == "api":
        run_api()
    elif command == "ui":
        run_ui()
    else:
        print(f"❌ Unknown command '{command}'. Available commands: 'api', 'ui'")
        sys.exit(1)


if __name__ == "__main__":
    main()
