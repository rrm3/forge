from fastapi import FastAPI

app = FastAPI(title="Forge", description="AI Tuesdays - Digital Science internal chat and RAG application")


@app.get("/health")
async def health():
    return {"status": "ok"}
