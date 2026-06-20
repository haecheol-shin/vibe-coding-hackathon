from fastapi import FastAPI


app = FastAPI(title="Vibe Coding Hackathon API")


# Basic endpoint used to verify that the API is running.
@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}