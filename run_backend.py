import os
import sys
import uvicorn

if __name__ == "__main__":
    # Set default environment variables
    os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")
    os.environ.setdefault("MONGODB_DB", "portfolio_ai")
    os.environ.setdefault("JWT_SECRET", "portfolio-ai-super-secret-key-2024")

    print("Starting AI Portfolio Backend on http://localhost:8000 ...")
    
    # Run the uvicorn server
    uvicorn.run(
        "backend.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )
