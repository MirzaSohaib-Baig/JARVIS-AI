from pathlib import Path

import subprocess
import sys
import threading

from fastapi import FastAPI, Query
import uvicorn
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
# from fastapi.middleware.cors import CORSMiddleware

from schema.chatSchema import ChatRequest, ChatResponse
from brain.orchestrator import handle_message
from tools.browser_automation import open_window_async

app = FastAPI(title="JARVIS")

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

HUD_PATH = Path(__file__).parent /"hud"

app.mount("/static", StaticFiles(directory=HUD_PATH), name="static")

@app.get("/")
async def get_hud():
    """Serve the JARVIS HUD HTML file."""
    return FileResponse(HUD_PATH / "jarvis-hud.html")

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    result = handle_message(request.message, request.history, session_id=request.session_id)
    updated_history = request.history + [
        {"role": "user", "content": request.message}, 
        {"role": "assistant", "content": result["reply"]}
        ]
    return ChatResponse(reply=result["reply"], history=updated_history, cards=result["cards"])

@app.get("/open-browser")
def open_external_browser(
    url: str = Query(...), 
    width: int = Query(600),
    height: int = Query(450),
    left: int = Query(100),
    top: int = Query(100)
):
    try:
        # Launch Playwright in a background daemon thread so HTTP response resolves instantly
        threading.Thread(
            target=open_window_async,
            args=(url, left, top, width, height),
            daemon=True
        ).start()

        return {"status": "success", "opened": url, "engine": "playwright"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/video-player")
async def video_player(embed_url: str = "", title: str = "JARVIS Video Player"):
    """Serve a video player page for native windows."""
    # Extract video ID for clean embed URL
    video_id = ""
    if "youtube.com/embed/" in embed_url:
        video_id = embed_url.split("youtube.com/embed/")[-1].split("?")[0]
    elif "watch?v=" in embed_url:
        video_id = embed_url.split("watch?v=")[-1].split("&")[0]
    elif "youtu.be/" in embed_url:
        video_id = embed_url.split("youtu.be/")[-1].split("?")[0]
    
    if video_id:
        embed_src = f"https://www.youtube.com/embed/{video_id}?autoplay=1&rel=0&modestbranding=1&enablejsapi=1"
    else:
        embed_src = embed_url
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            background: #000; 
            display: flex; 
            align-items: center; 
            justify-content: center;
            height: 100vh;
            overflow: hidden;
        }}
        iframe {{
            width: 100%;
            height: 100%;
            border: none;
        }}
    </style>
</head>
<body>
    <iframe 
        src="{embed_src}" 
        allow="autoplay; encrypted-media; fullscreen" 
        allowfullscreen>
    </iframe>
</body>
</html>"""
    return HTMLResponse(content=html)


if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)