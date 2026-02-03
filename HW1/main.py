from fastapi import FastAPI
from routers.advertisement import router
import uvicorn

app = FastAPI(title="Advertisement Moderation API")

@app.get("/")
async def root():
    return {"message": "Advertisement Moderation API"}

app.include_router(router, prefix="/advertisement")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8007)
