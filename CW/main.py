from fastapi import FastAPI
from routers.users import router as user_router, root_router
import uvicorn

app = FastAPI()

@app.get("/")
async def root():
    return {'message': 'Hello World'}

app.include_router(user_router, prefix='/users')
app.include_router(root_router)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)