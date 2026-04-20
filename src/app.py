from fastapi.middleware.cors import CORSMiddleware
import re
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Text, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker
import uuid
from fastapi import Body
import uuid
import threading

db_lock = threading.Lock()
app = FastAPI(title="DiscusViz API")

engine = create_engine(
    "sqlite:///discusviz.db",
    connect_args={
        "check_same_thread": False,
        "timeout": 30
    }
)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class NodeDB(Base):
    __tablename__ = "nodes"
    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    body = Column(Text, nullable=True)

class EdgeDB(Base):
    __tablename__ = "edges"
    id = Column(String, primary_key=True)
    source = Column(String, ForeignKey("nodes.id"), nullable=False)
    target = Column(String, ForeignKey("nodes.id"), nullable=False)
    type = Column(String, nullable=False)

Base.metadata.create_all(bind=engine)

class NodeIn(BaseModel):
    title: str
    body: str | None = None

class EdgeIn(BaseModel):
    source: str
    target: str
    type: str  # "reply", "supports", etc.

@app.get("/graph")
def get_graph():
    db = SessionLocal()
    nodes = db.query(NodeDB).all()
    edges = db.query(EdgeDB).all()
    return {
        "nodes": [{"data": {"id": n.id, "label": n.title, "body": n.body}} for n in nodes],
        "edges": [{"data": {"id": e.id, "source": e.source, "target": e.target, "type": e.type}} for e in edges],
    }

@app.post("/nodes")
def create_node(n: NodeIn):
    db = SessionLocal()
    node_id = str(uuid.uuid4())
    db.add(NodeDB(id=node_id, title=n.title, body=n.body))
    db.commit()
    return {"id": node_id}

@app.delete("/nodes/{node_id}")
def delete_node(node_id: str):
    db = SessionLocal()
    node = db.get(NodeDB, node_id)
    if not node:
        raise HTTPException(404, "Node not found")
    # delete connected edges too
    db.query(EdgeDB).filter((EdgeDB.source == node_id) | (EdgeDB.target == node_id)).delete()
    db.delete(node)
    db.commit()
    return {"ok": True}

@app.post("/edges")
def create_edge(e: EdgeIn):
    db = SessionLocal()
    # basic validation: nodes exist
    if not db.get(NodeDB, e.source) or not db.get(NodeDB, e.target):
        raise HTTPException(400, "Source/target node missing")
    edge_id = str(uuid.uuid4())
    db.add(EdgeDB(id=edge_id, source=e.source, target=e.target, type=e.type))
    db.commit()
    return {"id": edge_id}

@app.delete("/edges/{edge_id}")
def delete_edge(edge_id: str):
    db = SessionLocal()
    edge = db.get(EdgeDB, edge_id)
    if not edge:
        raise HTTPException(404, "Edge not found")
    db.delete(edge)
    db.commit()
    return {"ok": True}
from fastapi import Body
from openai import OpenAI
import uuid
import json


client = OpenAI(
    base_url="http://localhost:11434/v1",
    api_key="llama3"  # dummy, required but unused
)

@app.post("/generate")
def generate_graph(payload: dict = Body(...)):
    text = payload.get("text", "")

    with db_lock:   # 🔥 THIS FIXES EVERYTHING
        db = SessionLocal()
        try:
            db.query(EdgeDB).delete()
            db.query(NodeDB).delete()
            db.commit()
            prompt = f"""
Return ONLY valid JSON.

Format:
{{
  "nodes": [{{"id": "1", "label": "text"}}],
  "edges": [{{"source": "1", "target": "2", "type": "supports"}}]
}}

Edge types must be one of:
reply, supports, contradicts, references

Do not include any explanation.

Text:
{text}
"""
            # --- LLM call here ---
            response = client.chat.completions.create(
                model="llama3",
                messages=[{"role": "user", "content": prompt}]
            )

            content = response.choices[0].message.content
            print("LLM OUTPUT:", content)


# Extract JSON block
            match = re.search(r"\{.*\}", content, re.DOTALL)

            if not match:
                return {"error": "No JSON found in LLM output", "raw": content}

            json_str = match.group(0)

            try:
                data = json.loads(json_str)
            except Exception as e:
                return {"error": "Invalid JSON", "raw": content}
            id_map = {}

            for node in data.get("nodes", []):
                nid = str(uuid.uuid4())
                id_map[node["id"]] = nid

                db.add(NodeDB(
                    id=nid,
                    title=node["label"],
                    body=node["label"]
                ))

            for edge in data.get("edges", []):
                if edge["source"] not in id_map or edge["target"] not in id_map:
                    continue

                db.add(EdgeDB(
                    id=str(uuid.uuid4()),
                    source=id_map[edge["source"]],
                    target=id_map[edge["target"]],
                    type=edge["type"]
                ))

            db.commit()
        finally:
            db.close()

    return {"status": "ok"}


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ok for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
