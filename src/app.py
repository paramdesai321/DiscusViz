from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Text, ForeignKey, or_
from sqlalchemy.orm import declarative_base, sessionmaker
import uuid
from fastapi import Body

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

# added for cleaner generate input
class GenerateIn(BaseModel):
    text: str

# simple in-memory undo stack
undo_stack = []

def save_snapshot(db):
    nodes = db.query(NodeDB).all()
    edges = db.query(EdgeDB).all()

    snapshot = {
        "nodes": [{"id": n.id, "title": n.title, "body": n.body} for n in nodes],
        "edges": [{"id": e.id, "source": e.source, "target": e.target, "type": e.type} for e in edges],
    }
    undo_stack.append(snapshot)

def restore_snapshot(db, snapshot):
    db.query(EdgeDB).delete()
    db.query(NodeDB).delete()

    for n in snapshot["nodes"]:
        db.add(NodeDB(id=n["id"], title=n["title"], body=n["body"]))

    for e in snapshot["edges"]:
        db.add(EdgeDB(id=e["id"], source=e["source"], target=e["target"], type=e["type"]))

    db.commit()

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

    # save state before modifying graph
    save_snapshot(db)

    db.add(NodeDB(id=node_id, title=n.title, body=n.body))
    db.commit()
    return {"id": node_id}

# added: edit/update node
@app.put("/nodes/{node_id}")
def update_node(node_id: str, n: NodeIn):
    db = SessionLocal()
    node = db.get(NodeDB, node_id)
    if not node:
        raise HTTPException(404, "Node not found")

    save_snapshot(db)

    node.title = n.title
    node.body = n.body
    db.commit()
    return {"ok": True}

# added: duplicate node
@app.post("/nodes/{node_id}/duplicate")
def duplicate_node(node_id: str):
    db = SessionLocal()
    node = db.get(NodeDB, node_id)
    if not node:
        raise HTTPException(404, "Node not found")

    save_snapshot(db)

    new_id = str(uuid.uuid4())
    db.add(NodeDB(
        id=new_id,
        title=f"{node.title} (copy)",
        body=node.body
    ))
    db.commit()
    return {"id": new_id}

@app.delete("/nodes/{node_id}")
def delete_node(node_id: str):
    db = SessionLocal()
    node = db.get(NodeDB, node_id)
    if not node:
        raise HTTPException(404, "Node not found")

    # save state before modifying graph
    save_snapshot(db)

    # delete connected edges too
    db.query(EdgeDB).filter(or_(EdgeDB.source == node_id, EdgeDB.target == node_id)).delete()
    db.delete(node)
    db.commit()
    return {"ok": True}

@app.post("/edges")
def create_edge(e: EdgeIn):
    db = SessionLocal()
    # basic validation: nodes exist
    if not db.get(NodeDB, e.source) or not db.get(NodeDB, e.target):
        raise HTTPException(400, "Source/target node missing")

    # save state before modifying graph
    save_snapshot(db)

    edge_id = str(uuid.uuid4())
    db.add(EdgeDB(id=edge_id, source=e.source, target=e.target, type=e.type))
    db.commit()
    return {"id": edge_id}

# added: edit/update edge
@app.put("/edges/{edge_id}")
def update_edge(edge_id: str, e: EdgeIn):
    db = SessionLocal()
    edge = db.get(EdgeDB, edge_id)
    if not edge:
        raise HTTPException(404, "Edge not found")

    # basic validation: nodes exist
    if not db.get(NodeDB, e.source) or not db.get(NodeDB, e.target):
        raise HTTPException(400, "Source/target node missing")

    save_snapshot(db)

    edge.source = e.source
    edge.target = e.target
    edge.type = e.type
    db.commit()
    return {"ok": True}

@app.delete("/edges/{edge_id}")
def delete_edge(edge_id: str):
    db = SessionLocal()
    edge = db.get(EdgeDB, edge_id)
    if not edge:
        raise HTTPException(404, "Edge not found")

    # save state before modifying graph
    save_snapshot(db)

    db.delete(edge)
    db.commit()
    return {"ok": True}

@app.post("/generate")
def generate_graph(payload: GenerateIn):
    db = SessionLocal()

    # save state before modifying graph
    save_snapshot(db)

    # Clear old graph (optional but helpful)
    db.query(EdgeDB).delete()
    db.query(NodeDB).delete()

    # 1. Split text into sentences
    sentences = [s.strip() for s in payload.text.split('.') if s.strip()]

    node_ids = []

    # 2. Create nodes
    for s in sentences:
        nid = str(uuid.uuid4())
        db.add(NodeDB(id=nid, title=s, body=s))
        node_ids.append(nid)

    # 3. Create edges (simple logic)
    for i in range(len(sentences) - 1):
        s = sentences[i].lower()

        if "but" in s or "however" in s:
            etype = "contradicts"
        elif "because" in s or "therefore" in s:
            etype = "supports"
        else:
            etype = "reply"

        db.add(EdgeDB(
            id=str(uuid.uuid4()),
            source=node_ids[i],
            target=node_ids[i+1],
            type=etype
        ))

    db.commit()
    return {"status": "ok"}

# added: undo last graph-changing action
@app.post("/undo")
def undo_last_action():
    db = SessionLocal()
    if not undo_stack:
        raise HTTPException(400, "Nothing to undo")

    snapshot = undo_stack.pop()
    restore_snapshot(db, snapshot)
    return {"ok": True}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ok for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
