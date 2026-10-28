"""Distributed File System - DataNode.

A chunk server in the HDFS-style cluster. Stores fixed-size chunks on disk
and serves/blocks them. Multiple replicas of this app form the DataNodes;
the NameNode (file_service/main.py) coordinates which node stores what.

Endpoints:
    GET  /ping          -> liveness + node id + chunk count
    GET  /nodes/summary -> this node's stored chunk inventory
    PUT  /chunks/{cid}  -> store a chunk (raw body)
    GET  /chunks/{cid}  -> fetch a chunk
    HEAD /chunks/{cid}  -> chunk existence probe
"""

import os
from pathlib import Path

from fastapi import Body, FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

NODE_ID = os.getenv("NODE_ID", "datanode-1")
CHUNK_DIR = Path(os.getenv("CHUNK_DIR", "/data/chunks"))

app = FastAPI(title=f"DataNode {NODE_ID}", version="1.0.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    CHUNK_DIR.mkdir(parents=True, exist_ok=True)


def _chunk_path(chunk_id: str) -> Path:
    safe = "".join(c for c in chunk_id if c.isalnum() or c in "-_")
    return CHUNK_DIR / safe[:2] / safe


def _chunks_list():
    if not CHUNK_DIR.exists():
        return []
    return [p.name for p in CHUNK_DIR.rglob("*") if p.is_file()]


@app.get("/ping")
def ping():
    return {"node_id": NODE_ID, "status": "UP", "chunks_stored": len(_chunks_list())}


@app.get("/nodes/summary")
def summary():
    chunks = _chunks_list()
    return {"node_id": NODE_ID, "chunks": chunks, "count": len(chunks)}


@app.put("/chunks/{chunk_id}")
async def put_chunk(chunk_id: str, body: bytes = Body(...)):
    if not body:
        return Response(status_code=400, content=b"empty chunk body")
    path = _chunk_path(chunk_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return {"node_id": NODE_ID, "chunk_id": chunk_id, "stored": True, "bytes": len(body)}


@app.get("/chunks/{chunk_id}")
def get_chunk(chunk_id: str):
    path = _chunk_path(chunk_id)
    if not path.exists():
        return Response(status_code=404, content=b"chunk not found")
    return Response(content=path.read_bytes(), media_type="application/octet-stream")


@app.head("/chunks/{chunk_id}")
def head_chunk(chunk_id: str):
    path = _chunk_path(chunk_id)
    return Response(status_code=200 if path.exists() else 404)


@app.delete("/chunks/{chunk_id}")
def delete_chunk(chunk_id: str):
    path = _chunk_path(chunk_id)
    if not path.exists():
        return {"node_id": NODE_ID, "chunk_id": chunk_id, "deleted": False}
    path.unlink()
    return {"node_id": NODE_ID, "chunk_id": chunk_id, "deleted": True}