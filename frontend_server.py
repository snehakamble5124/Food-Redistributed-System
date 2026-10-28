import sys
import os
import time
import uvicorn
from fastapi import FastAPI, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse

app = FastAPI(title="Frontend Server")

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")

@app.get("/")
def serve_index():
    return FileResponse(os.path.join(FRONTEND_DIR, "login.html"))

@app.get("/login")
@app.get("/login.html")
def serve_login():
    return FileResponse(os.path.join(FRONTEND_DIR, "login.html"))

@app.get("/admin")
@app.get("/admin.html")
def serve_admin():
    return FileResponse(os.path.join(FRONTEND_DIR, "admin.html"))

@app.get("/donor")
@app.get("/donor.html")
def serve_donor():
    return FileResponse(os.path.join(FRONTEND_DIR, "donor.html"))

@app.get("/ngo")
@app.get("/ngo.html")
def serve_ngo():
    return FileResponse(os.path.join(FRONTEND_DIR, "ngo.html"))

@app.get("/volunteer")
@app.get("/volunteer.html")
def serve_volunteer():
    return FileResponse(os.path.join(FRONTEND_DIR, "volunteer.html"))

@app.get("/index")
@app.get("/index.html")
def serve_index_page():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.middleware("http")
async def no_cache_js(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/js/") or request.url.path.startswith("/css/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

app.mount("/css", StaticFiles(directory=os.path.join(FRONTEND_DIR, "css")), name="css")
app.mount("/js", StaticFiles(directory=os.path.join(FRONTEND_DIR, "js")), name="js")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3000)
