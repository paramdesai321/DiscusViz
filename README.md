# DiscusViz

DiscusViz is a web-based visualization and editing tool for discussion
graphs. It allows users to represent conversations as interactive
node-link structures rather than linear threads, making it easier to
explore relationships such as replies, support, and contradictions.

## Features

-   Create and delete discussion nodes\
-   Create typed edges (reply, supports, contradicts, references)\
-   Interactive graph visualization using Cytoscape.js\
-   REST API backend built with FastAPI\
-   Lightweight SQLite database for storage

## Project Structure

DiscusViz/ │── src/ │ ├── app.py \# FastAPI backend │ ├── index.html \#
Frontend visualization │ └── discusviz.db \# SQLite database
(auto-created)

## Requirements

-   Python 3.10+
-   pip

## Installation

### 1. Clone the repository

git clone `<your-repo-url>`{=html}\
cd DiscusViz/src

### 2. Create a virtual environment (recommended)

python3 -m venv venv\
source venv/bin/activate \# Mac/Linux

### 3. Install dependencies

pip install fastapi uvicorn sqlalchemy

## Running the Application

### 1. Start the backend server

uvicorn app:app --reload

The API will be available at:\
http://127.0.0.1:8000

API docs:\
http://127.0.0.1:8000/docs

### 2. Open the frontend

open index.html

## Usage

1.  Click "Add node" to create a discussion point\
2.  Click one node, then another to create an edge\
3.  Select edge types from the dropdown\
4.  The graph updates automatically

## API Endpoints

-   GET /graph\
-   POST /nodes\
-   DELETE /nodes/{id}\
-   POST /edges\
-   DELETE /edges/{id}

## Notes

-   CORS is enabled for development\
-   SQLite database is auto-created\
-   Data is stored locally

## Future Improvements

-   Node editing\
-   Edge styling\
-   Graph layouts\
-   Authentication
