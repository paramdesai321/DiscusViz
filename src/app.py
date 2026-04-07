from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Text, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker
import uuid

app = FastAPI(title="DiscusViz API")

engine = create_engine("sqlite:///discusviz.db", connect_args={"check_same_thread": False})
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


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ok for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
