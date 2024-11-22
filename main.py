import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from firebase_admin import credentials, firestore, initialize_app
from pydantic import BaseModel
from firecrawl import FirecrawlApp
import os
# Initialize Firebase Admin SDK
cred = credentials.Certificate(json.loads(os.environ.get('FIREBASE_SERVICE_ACCOUNT_KEY')))
initialize_app(cred)

# Get a reference to the Firestore database
db = firestore.client()

app = FastAPI()

firecrawl_app = FirecrawlApp(api_key=os.environ.get('FIRECRAWL_API_KEY'))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

class UrlInput(BaseModel):
    url: str

class UserAction(BaseModel):
    action: str
    data: dict

@app.get('/self')
async def fetch_this():
    return { 'example': 'This is an example'}

async def log_action(action: str, data: dict):
    try:
        doc_ref = db.collection("user_actions").add({
            "action": action,
            "data": data,
            "timestamp": firestore.SERVER_TIMESTAMP
        })
        print(f"Action logged with ID: {doc_ref[1].id}")
    except Exception as e:
        print(f"Error logging action: {e}")

@app.get("/actions")
async def get_actions():
    try:
        # Get all documents from the "user_actions" collection
        docs = db.collection("user_actions").stream()
        return [{"id": doc.id, **doc.to_dict()} for doc in docs]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@app.post("/map")
async def map_site(input: UrlInput):
    try:
        result = firecrawl_app.map_url(input.url)
        await log_action("SITEMAP_RETRIEVED", {"url": input.url, "links": result["links"]})
        return result
    except Exception as e:
        await log_action("SITEMAP_ERROR", {"url": input.url, "error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/scrape")
async def scrape_page(input: UrlInput):
    try:
        result = firecrawl_app.scrape_url(input.url, params={'formats': ['markdown', 'html']})
        await log_action("CONTENT_SCRAPED", {"url": input.url})
        return result
    except Exception as e:
        await log_action("SCRAPE_ERROR", {"url": input.url, "error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)