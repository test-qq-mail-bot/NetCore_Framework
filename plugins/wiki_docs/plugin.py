"""
plugins/wiki_docs/plugin.py - 内置文档插件

功能：将框架内置 wiki/ 文档通过 API 暴露给前端，
并在左侧菜单注册“使用文档”入口
"""
import urllib.parse
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from core.auth import get_current_user
from core.config_loader import WIKI_DIR
from core.logger import get_logger
from plugins.base_plugin import BasePlugin

logger = get_logger()


class WikiDocsPlugin(BasePlugin):
    """文档插件：提供 wiki 文档列表与内容读取"""

    def get_metadata(self) -> Dict[str, str]:
        return {
            "name": "wiki_docs",
            "version": "20260823-V1",
            "description": "内置使用文档插件",
            "author": "NetCore Team",
        }

    def on_load(self) -> bool:
        logger.info("文档插件加载完成，文档目录：%s", WIKI_DIR)
        return True

    def get_routes(self) -> Optional[APIRouter]:
        # 安全：/api/wiki/* 属于后台内容接口，必须登录后才能访问。
        # 这里在路由级统一挂 get_current_user 依赖（未带合法 JWT 一律 401），
        # 避免匿名用户直接拉取内网运维文档。前端 wiki 页由已登录会话发起请求
        # （axios 拦截器自动带 Authorization 头），因此正常使用不受影响。
        router = APIRouter(dependencies=[Depends(get_current_user)])

        @router.get("/api/wiki/doc/{name}")
        async def wiki_doc(name: str):
            """读取指定文档内容（需登录，防止路径穿越）

            浏览器刷新时 URL 中的中文文件名会被编码为 %xx 形式发给服务端，
            这里用 urllib.parse.unquote 兜底解码一次还原为真实文件名。
            即便 FastAPI 已部分解码，对已解码字符串再 unquote 也不会改变内容，
            可安全兼容多层编码/查询字符串等残留编码场景。

            文档缺失时返回结构化 JSON（而非纯文本 404），
            前端可据此明确区分「路由不存在/插件未加载」与「wiki 目录缺文件」。
            """
            from fastapi.responses import JSONResponse
            decoded = urllib.parse.unquote(name)
            safe = Path(decoded).name
            path = WIKI_DIR / safe
            if not path.exists() or not str(path.resolve()).startswith(str(WIKI_DIR.resolve())):
                return JSONResponse(status_code=404, content={
                    "detail": "文档不存在：%s（请检查程序目录 wiki/ 文件夹是否完整）" % safe})
            return PlainTextResponse(path.read_text(encoding="utf-8"), media_type="text/markdown")

        return router

    def get_menus(self) -> List[Dict]:
        docs = []
        if WIKI_DIR.exists():
            for f in sorted(WIKI_DIR.glob("*.md")):
                docs.append({
                    "id": "wiki_%s" % f.stem,
                    "label": f.stem,
                    "path": "/wiki/view/%s" % f.name,
                })
        return [{
            "id": "wiki_docs",
            "label": "使用文档",
            "icon": "doc",
            "children": docs,
        }]
