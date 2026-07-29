from pathlib import Path

from fastapi import FastAPI
import uvicorn
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from schema.chatSchema import ChatRequest, ChatResponse
from brain.orchestrator import handle_message

import html as _html

app = FastAPI(title="JARVIS")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

@app.get("/card", response_class=HTMLResponse)
def news_card(title: str = "", source: str = "", body: str = "", url: str = "", image: str = ""):
    """
    Renders a single news item as its own tiny styled page — this is what
    each spawned window (PyQt) or floating panel (plain browser) loads.
    Kept as a standalone route so it can be opened either as a real OS
    window's content (PyQt) or as an <iframe>/popup (plain browser).
    """
    safe_title = _html.escape(title or "Untitled")
    safe_source = _html.escape(source or "")
    safe_body = _html.escape(body or "")
    safe_open_url = url if url.startswith(("http://", "https://")) else "#"
    safe_image_url = image if image.startswith(("http://", "https://")) else ""
    image_block = (
        f'<img class="thumb" src="{safe_image_url}" alt="" onerror="this.style.display=\'none\'" />'
        if safe_image_url
        else ""
    )

    return f"""<!DOCTYPE html>
          <html><head><meta charset="UTF-8">
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <style>
            @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;700;900&display=swap');
            
            * {{
              margin: 0;
              padding: 0;
              box-sizing: border-box;
            }}
            
            html, body {{
              margin: 0;
              height: 100%;
              min-height: 100%;
              background: transparent;
            }}
            
            body {{
              font-family: 'Orbitron', sans-serif;
              background: rgba(5, 10, 15, 0.95);
              border: 1px solid rgba(0, 255, 255, 0.6);
              border-radius: 14px;
              box-shadow: 
                0 0 30px rgba(0, 255, 255, 0.3),
                0 0 60px rgba(0, 255, 255, 0.1),
                inset 0 0 40px rgba(0, 255, 255, 0.05);
              color: #eaf9ff;
              height: 100%;
              display: flex;
              flex-direction: column;
              -webkit-app-region: drag;
              position: relative;
              overflow: hidden;
            }}
            
            /* Animated scan line effect */
            body::before {{
              content: '';
              position: absolute;
              top: 0;
              left: 0;
              right: 0;
              height: 1px;
              background: linear-gradient(90deg, transparent, rgba(0, 255, 255, 0.3), transparent);
              animation: scanDown 4s linear infinite;
              pointer-events: none;
              z-index: 10;
            }}
            
            @keyframes scanDown {{
              0% {{ top: -1px; opacity: 0; }}
              10% {{ opacity: 1; }}
              90% {{ opacity: 1; }}
              100% {{ top: 100%; opacity: 0; }}
            }}
            
            /* Corner decorations */
            body::after {{
              content: '';
              position: absolute;
              top: 0;
              left: 0;
              right: 0;
              bottom: 0;
              border: 1px solid transparent;
              border-image: linear-gradient(45deg, rgba(0, 255, 255, 0.3), transparent 40%, transparent 60%, rgba(0, 255, 255, 0.3)) 1;
              border-radius: 14px;
              pointer-events: none;
            }}
            
            .thumb {{
              width: 100%;
              max-height: 120px;
              object-fit: cover;
              display: block;
              border-bottom: 1px solid rgba(0, 255, 255, 0.4);
              -webkit-app-region: no-drag;
              filter: brightness(0.8) saturate(1.2);
              transition: filter 0.3s ease;
              flex-shrink: 0;
            }}
            
            .thumb:hover {{
              filter: brightness(1) saturate(1.5);
            }}
            
            .content {{
              padding: 14px 18px;
              display: flex;
              flex-direction: column;
              gap: 8px;
              flex: 1;
              min-height: 0;
              position: relative;
              z-index: 5;
              overflow: hidden;
            }}
            
            .source {{
              font-family: 'Orbitron', sans-serif;
              font-size: 8px;
              letter-spacing: 0.3em;
              text-transform: uppercase;
              color: #4fd6ff;
              opacity: 0.9;
              display: flex;
              align-items: center;
              gap: 6px;
              flex-shrink: 0;
              min-height: 16px;
            }}
            
            .source::before {{
              content: '';
              display: inline-block;
              width: 5px;
              height: 5px;
              background: #4fd6ff;
              border-radius: 50%;
              box-shadow: 0 0 10px #4fd6ff, 0 0 20px rgba(79, 214, 255, 0.5);
              animation: pulse 2s ease-in-out infinite;
              flex-shrink: 0;
            }}
            
            @keyframes pulse {{
              0%, 100% {{ opacity: 0.6; transform: scale(1); }}
              50% {{ opacity: 1; transform: scale(1.3); }}
            }}
            
            .title {{
              font-family: 'Orbitron', sans-serif;
              font-size: 13px;
              line-height: 1.4;
              font-weight: 700;
              color: #eaf9ff;
              text-shadow: 0 0 10px rgba(0, 255, 255, 0.3);
              letter-spacing: 0.3px;
              flex-shrink: 0;
              max-height: 3.6em;
              overflow: hidden;
              display: -webkit-box;
              -webkit-line-clamp: 2;
              -webkit-box-orient: vertical;
              word-break: break-word;
            }}
            
            .body-wrapper {{
              flex: 1;
              min-height: 0;
              position: relative;
              overflow: hidden;
            }}
            
            .body {{
              font-family: 'Courier New', monospace;
              font-size: 10px;
              line-height: 1.5;
              color: #9fd3e8;
              height: 100%;
              overflow-y: auto;
              padding-right: 4px;
              word-break: break-word;
              overflow-wrap: break-word;
            }}
            
            .body::-webkit-scrollbar {{
              width: 3px;
            }}
            
            .body::-webkit-scrollbar-track {{
              background: rgba(0, 255, 255, 0.05);
              border-radius: 3px;
            }}
            
            .body::-webkit-scrollbar-thumb {{
              background: rgba(0, 255, 255, 0.3);
              border-radius: 3px;
            }}
            
            .body::-webkit-scrollbar-thumb:hover {{
              background: rgba(0, 255, 255, 0.5);
            }}
            
            .button-container {{
              flex-shrink: 0;
              padding-top: 4px;
            }}
            
            a.open {{
              -webkit-app-region: no-drag;
              display: inline-flex;
              align-items: center;
              font-family: 'Orbitron', sans-serif;
              font-size: 9px;
              letter-spacing: 0.15em;
              text-transform: uppercase;
              color: #0a1620;
              background: linear-gradient(135deg, #4fd6ff 0%, #00ffff 100%);
              padding: 8px 16px;
              border-radius: 25px;
              text-decoration: none;
              font-weight: 700;
              transition: all 0.3s ease;
              border: 1px solid rgba(0, 255, 255, 0.5);
              box-shadow: 0 0 15px rgba(0, 255, 255, 0.3);
              position: relative;
              overflow: hidden;
              max-width: 100%;
              white-space: nowrap;
              text-overflow: ellipsis;
            }}
            
            a.open::before {{
              content: '';
              position: absolute;
              top: -50%;
              left: -50%;
              width: 200%;
              height: 200%;
              background: radial-gradient(circle, rgba(255, 255, 255, 0.3) 0%, transparent 60%);
              opacity: 0;
              transition: opacity 0.3s ease;
            }}
            
            a.open:hover {{
              opacity: 1;
              transform: translateY(-1px);
              box-shadow: 0 0 25px rgba(0, 255, 255, 0.5), 0 3px 12px rgba(0, 255, 255, 0.2);
              border-color: #00ffff;
              color: #050a0f;
            }}
            
            a.open:hover::before {{
              opacity: 1;
            }}
            
            a.open:active {{
              transform: translateY(0);
            }}
            
            /* Data stream effect */
            .data-stream {{
              position: absolute;
              top: 0;
              right: 0;
              bottom: 0;
              width: 20px;
              background: repeating-linear-gradient(
                0deg,
                transparent,
                transparent 2px,
                rgba(0, 255, 255, 0.03) 2px,
                rgba(0, 255, 255, 0.03) 4px
              );
              pointer-events: none;
              z-index: 1;
            }}

            /* Responsive adjustments for different window sizes */
            @media (max-width: 280px) {{
              .content {{
                padding: 10px 12px;
                gap: 6px;
              }}
              
              .title {{
                font-size: 11px;
              }}
              
              .body {{
                font-size: 9px;
              }}
              
              a.open {{
                font-size: 8px;
                padding: 6px 12px;
              }}
            }}

            @media (min-width: 400px) {{
              .content {{
                padding: 18px 22px;
                gap: 12px;
              }}
              
              .title {{
                font-size: 15px;
              }}
              
              .body {{
                font-size: 11px;
              }}
              
              a.open {{
                font-size: 10px;
                padding: 10px 20px;
              }}
            }}
          </style></head>
          <body>
            <div class="data-stream"></div>
            {image_block}
            <div class="content">
              <div class="source">{safe_source}</div>
              <div class="title">{safe_title}</div>
              <div class="body-wrapper">
                <div class="body">{safe_body}</div>
              </div>
              <div class="button-container">
                <a class="open" href="{safe_open_url}" target="_blank" rel="noopener">
                  <span style="margin-right: 6px;">◈</span> Open Source
                </a>
              </div>
            </div>
          </body></html>"""

if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)