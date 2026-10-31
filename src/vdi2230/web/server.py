from __future__ import annotations

import argparse
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
import json
import logging
import math
from urllib.parse import urlsplit

from vdi2230.domain.models import JsonValue, ProjectSnapshot
from vdi2230.domain.section import section_primitives
from vdi2230.infrastructure.report import render_text_report
from vdi2230.ui.forms import CaseFormDefinition
from vdi2230.ui.reference_cases import build_reference_cases


LOGGER = logging.getLogger(__name__)
MAX_BODY_BYTES = 32_768
SAFETY_LABELS = {
    "SF": "抗屈服安全系数",
    "SD": "疲劳安全系数",
    "SG": "抗滑移安全系数",
    "Sp": "支承面压安全系数",
    "SpK": "螺栓头支承面压安全系数",
    "SpMu": "螺母支承面压安全系数",
}
ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
}


def reference_project(case: CaseFormDefinition) -> ProjectSnapshot:
    return ProjectSnapshot(
        case_id=case.case_id,
        title=case.title,
        inputs={field.key: field.default_value for field in case.fields},
        input_units={field.key: field.unit for field in case.fields},
        input_sources={field.key: field.source for field in case.fields},
        assumptions=(
            "固定 PDF 参考算例；输入只读，不支持参数化设计计算。",
            "二维剖面是示意图，不是制造图；部分绘图尺寸为示意值。",
        ),
    )


class ReferenceServer(ThreadingHTTPServer):
    def __init__(self, port: int = 8765) -> None:
        self.cases = {case.case_id: case for case in build_reference_cases()}
        super().__init__(("127.0.0.1", port), ReferenceRequestHandler)


class ReferenceRequestHandler(BaseHTTPRequestHandler):
    server: ReferenceServer

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; "
            "frame-ancestors 'none'; form-action 'none'",
        )
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            LOGGER.info("Browser disconnected while receiving %s", self.path)

    def _json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def _local_request(self) -> bool:
        hosts = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        origin = self.headers.get("Origin")
        if self.headers.get("Host") not in hosts or (
            origin is not None and origin not in {f"http://{host}" for host in hosts}
        ):
            self._json(403, {"error": "仅允许本机同源访问。"})
            return False
        return True

    def _case(self, path: str, *, calculate: bool = False) -> CaseFormDefinition | None:
        parts = path.strip("/").split("/")
        expected_length = 4 if calculate else 3
        if (
            len(parts) == expected_length
            and parts[:2] == ["api", "cases"]
            and (not calculate or parts[3] == "calculate")
        ):
            return self.server.cases.get(parts[2])
        return None

    def do_GET(self) -> None:
        if not self._local_request():
            return
        path = urlsplit(self.path).path
        if path in ASSETS:
            name, content_type = ASSETS[path]
            try:
                body = files("vdi2230.web").joinpath("static", name).read_bytes()
            except OSError:
                LOGGER.exception("Cannot read bundled web asset %s", name)
                self._json(500, {"error": "网页资源读取失败，请检查安装。"})
                return
            self._send(200, body, content_type)
        elif path == "/api/cases":
            self._json(200, [
                {"case_id": case.case_id, "title": case.title}
                for case in self.server.cases.values()
            ])
        elif (case := self._case(path)) is not None:
            project = reference_project(case)
            geometry = case.geometry(project.inputs)
            if geometry is None:
                LOGGER.error("Missing section geometry for %s", case.case_id)
                self._json(500, {"error": "该算例缺少剖面几何。"})
                return
            self._json(200, {
                "case_id": case.case_id,
                "title": case.title,
                "inputs": project.inputs,
                "fields": [asdict(field) for field in case.fields],
                "geometry": asdict(geometry),
                "section": [asdict(item) for item in section_primitives(640, 500, geometry)],
            })
        else:
            self._json(404, {"error": "未找到页面或参考算例。"})

    def do_POST(self) -> None:
        if not self._local_request():
            return
        case = self._case(urlsplit(self.path).path, calculate=True)
        if case is None:
            self._json(404, {"error": "未找到参考算例。"})
            return
        if self.headers.get_content_type() != "application/json":
            self._json(415, {"error": "计算请求必须使用 application/json。"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._json(400, {"error": "无效的请求长度。"})
            return
        if not 0 < length <= MAX_BODY_BYTES:
            self._json(413, {"error": "请求为空或超过 32 KiB 限制。"})
            return
        try:
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict) or set(payload) != {"inputs"}:
                raise ValueError("请求必须只包含 inputs 对象。")
            raw_inputs = payload["inputs"]
            if not isinstance(raw_inputs, dict):
                raise ValueError("inputs 必须是参考输入对象。")
            inputs: dict[str, JsonValue] = {}
            for key, value in raw_inputs.items():
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                ):
                    raise ValueError(f"参考输入 {key} 必须是有限数值。")
                inputs[key] = value
            project = reference_project(case)
            if inputs != project.inputs:
                raise ValueError("仅支持固定 PDF 参考输入；不接受修改后的参数。")
            result = case.calculate(project)
        except (ValueError, UnicodeDecodeError) as exc:
            LOGGER.warning("Rejected calculation for %s: %s", case.case_id, exc)
            self._json(400, {"error": str(exc)})
            return
        except (ArithmeticError, TypeError, RuntimeError):
            LOGGER.exception("Calculation failed for %s", case.case_id)
            self._json(500, {"error": "计算失败，请检查服务日志。"})
            return
        self._json(200, {
            **asdict(result),
            "overall_status": result.overall_status.value,
            "is_fully_calculated": result.is_fully_calculated,
            "safety_factors": [
                {**asdict(value), "label": SAFETY_LABELS[value.symbol]}
                for value in result.values if value.symbol in SAFETY_LABELS
            ],
            "report": render_text_report(project, result),
        })


def main() -> None:
    parser = argparse.ArgumentParser(description="Local VDI 2230 reference-case web UI")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("--port must be between 0 and 65535")
    logging.basicConfig(level=logging.INFO)
    try:
        server = ReferenceServer(args.port)
    except OSError as exc:
        parser.exit(1, f"Cannot start local web server: {exc}\n")
    with server:
        print(f"VDI 2230 web UI: http://127.0.0.1:{server.server_port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nWeb server stopped.", flush=True)
