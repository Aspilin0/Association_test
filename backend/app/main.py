"""aiohttp 入口：托管 REST API + 静态前端（免构建）。

说明：因当前环境无外网，无法安装 fastapi/uvicorn，改用已内置的 aiohttp
作为 HTTP 层。引擎/评分/候选/网络等核心逻辑与框架无关，后续联网后可平替 FastAPI。
"""
from __future__ import annotations

import json
from pathlib import Path

from aiohttp import web

from . import embeddings as emb_mod
from . import llm as llm_mod
from .config import config
from .schemas import CreateSessionRequest, SubmitRequest
from .services.engine import AppError, Engine
from .services.store import SessionStore

llm = llm_mod.get_provider(config)
embeddings = emb_mod.get_provider(config)
store = SessionStore(embeddings)
engine = Engine(config, llm, store)

FRONTEND_DIR = (Path(__file__).resolve().parent.parent.parent / "frontend").resolve()

_STATUS = {
    "SESSION_NOT_FOUND": 404,
    "SESSION_FINISHED": 409,
    "INVALID_WORD": 400,
    "INVALID_INPUT": 400,
    "NOT_IMPLEMENTED": 501,
}


def _dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def _json(data, status: int = 200) -> web.Response:
    return web.json_response(data, status=status, dumps=_dumps)


def _dump(model) -> dict:
    return model.model_dump(mode="json", by_alias=True)


def _err(e: AppError) -> web.Response:
    return _json(
        {"error": {"code": e.code, "message": e.message}}, _STATUS.get(e.code, 400)
    )


async def _read_body(request: web.Request):
    try:
        return await request.json()
    except Exception:
        return None


# ---- 路由处理 ----
async def health(request: web.Request) -> web.Response:
    return _json(
        {
            "status": "ok",
            "llm_provider": llm.name,
            "embedding_provider": embeddings.name,
        }
    )


async def create_session(request: web.Request) -> web.Response:
    body = await _read_body(request)
    if body is None:
        return _json({"error": {"code": "INVALID_INPUT", "message": "请求体不是有效 JSON"}}, 400)
    try:
        req = CreateSessionRequest(**body)
    except Exception as ex:
        return _json({"error": {"code": "INVALID_INPUT", "message": str(ex)}}, 400)
    try:
        result = await engine.create_session(req)
    except AppError as e:
        return _err(e)
    return _json(_dump(result))


async def get_session(request: web.Request) -> web.Response:
    session_id = request.match_info["session_id"]
    try:
        return _json(_dump(engine.get_state(session_id)))
    except AppError as e:
        return _err(e)


async def submit(request: web.Request) -> web.Response:
    session_id = request.match_info["session_id"]
    body = await _read_body(request)
    if body is None:
        return _json({"error": {"code": "INVALID_INPUT", "message": "请求体不是有效 JSON"}}, 400)
    try:
        req = SubmitRequest(**body)
    except Exception as ex:
        return _json({"error": {"code": "INVALID_INPUT", "message": str(ex)}}, 400)
    try:
        result = await engine.submit_word(
            session_id, req.word, req.reaction_time_ms, req.source
        )
    except AppError as e:
        return _err(e)
    return _json(_dump(result))


async def reshuffle(request: web.Request) -> web.Response:
    session_id = request.match_info["session_id"]
    try:
        return _json(_dump(await engine.reshuffle(session_id)))
    except AppError as e:
        return _err(e)


async def finish(request: web.Request) -> web.Response:
    session_id = request.match_info["session_id"]
    try:
        return _json(_dump(engine.finish(session_id)))
    except AppError as e:
        return _err(e)


async def network(request: web.Request) -> web.Response:
    session_id = request.match_info["session_id"]
    try:
        return _json(engine.get_network(session_id))
    except AppError as e:
        return _err(e)


async def report(request: web.Request) -> web.Response:
    session_id = request.match_info["session_id"]
    try:
        return _json(await engine.generate_report(session_id))
    except AppError as e:
        return _err(e)


async def index(request: web.Request) -> web.Response:
    return web.FileResponse(FRONTEND_DIR / "index.html")


async def static_files(request: web.Request) -> web.Response:
    name = request.match_info["name"]
    path = (FRONTEND_DIR / name).resolve()
    if not str(path).startswith(str(FRONTEND_DIR)) or not path.is_file():
        return web.Response(status=404, text="Not Found")
    return web.FileResponse(path)


@web.middleware
async def middleware(request: web.Request, handler):
    if request.method == "OPTIONS":
        return web.Response(
            status=204,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
            },
        )
    try:
        resp = await handler(request)
    except web.HTTPException:
        raise
    except Exception as ex:
        resp = _json({"error": {"code": "INTERNAL", "message": str(ex)}}, 500)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


def create_app() -> web.Application:
    app = web.Application(middlewares=[middleware])
    app.router.add_get("/health", health)
    app.router.add_post("/api/v1/sessions", create_session)
    app.router.add_get("/api/v1/sessions/{session_id}", get_session)
    app.router.add_post("/api/v1/sessions/{session_id}/submit", submit)
    app.router.add_post("/api/v1/sessions/{session_id}/reshuffle", reshuffle)
    app.router.add_post("/api/v1/sessions/{session_id}/finish", finish)
    app.router.add_get("/api/v1/sessions/{session_id}/network", network)
    app.router.add_post("/api/v1/sessions/{session_id}/report", report)
    app.router.add_get("/", index)
    app.router.add_get("/{name}", static_files)
    return app


app = create_app()


if __name__ == "__main__":
    print(
        f"[start] llm={llm.name} embedding={embeddings.name} "
        f"frontend={FRONTEND_DIR}"
    )
    web.run_app(app, host="127.0.0.1", port=8000)
