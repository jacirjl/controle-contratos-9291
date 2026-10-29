import http.server
import socketserver
import os
import json
import sqlite3
import subprocess
import urllib.parse
import ingest_engine

PORT = 8092
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))


class ContractPlatformHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT_DIR, **kwargs)

    def _send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _handle_ingest_delta(self):
        conn = sqlite3.connect(ingest_engine.DB_PATH)
        try:
            summary = ingest_engine.run_delta_ingestion(conn, force_rebuild=False)
            if summary.get("new_pages_ingested_delta", 0) > 0:
                events = ingest_engine.populate_structured_tables(conn)
                ingest_engine.patch_frontend_data_js(conn, summary, events)
        finally:
            conn.close()
        self._send_json({
            "ok": True,
            "summary": summary
        })

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)

        if parsed.path in ("/", "/index.html"):
            self.send_response(302)
            self.send_header("Location", "/plataforma-controle-9291/index.html")
            self.end_headers()
            return

        if parsed.path == "/api/status":
            conn = sqlite3.connect(ingest_engine.DB_PATH)
            conn.row_factory = sqlite3.Row
            try:
                cur = conn.cursor()
                watermarks = [dict(r) for r in cur.execute("SELECT * FROM document_watermarks ORDER BY doc_id").fetchall()]
                total_chunks = cur.execute("SELECT COUNT(*) FROM vector_chunks").fetchone()[0]
                total_events = cur.execute("SELECT COUNT(*) FROM chronological_events").fetchone()[0]
            finally:
                conn.close()

            total_pages = sum(w.get("last_ingested_page", 0) for w in watermarks)
            total_tokens = sum(w.get("tokens_cached", 0) for w in watermarks) or (total_pages * 850)
            self._send_json({
                "ok": True,
                "db_path": "db/contrato_9291.sqlite",
                "total_pdfs": len(watermarks),
                "total_pages_indexed": total_pages,
                "total_vector_chunks": total_chunks,
                "total_chronological_events": total_events,
                "estimated_tokens_saved_on_resync": total_tokens,
                "watermarks": watermarks
            })
            return

        if parsed.path == "/api/vector-search":
            q = query.get("q", [""])[0]
            raw_os = (query.get("os", [""])[0] or "").strip()
            os_map = {
                "": "TODOS",
                "TODOS": "TODOS",
                "PROC_RMEC": "COBRANCA_RMEC",
                "PROC_MAE": "CONTRATO_GERAL",
            }
            mapped_filter = os_map.get(raw_os, raw_os)
            top_k = int(query.get("limit", ["15"])[0])

            conn = sqlite3.connect(ingest_engine.DB_PATH)
            try:
                results = ingest_engine.semantic_vector_search(
                    conn, q, top_k=top_k, filter_os=mapped_filter
                )
            finally:
                conn.close()

            self._send_json({
                "ok": True,
                "query": q,
                "os_filter": mapped_filter,
                "count": len(results),
                "results": results
            })
            return

        if parsed.path == "/api/ingest-delta":
            self._handle_ingest_delta()
            return

        if parsed.path == "/api/timeline":
            conn = sqlite3.connect(ingest_engine.DB_PATH)
            conn.row_factory = sqlite3.Row
            try:
                cur = conn.cursor()
                events = [dict(r) for r in cur.execute(
                    "SELECT * FROM chronological_events ORDER BY date_iso ASC, step_number ASC, page_num ASC"
                ).fetchall()]
            finally:
                conn.close()
            self._send_json({
                "ok": True,
                "count": len(events),
                "events": events
            })
            return

        if parsed.path == "/api/git-history":
            try:
                log_out = subprocess.check_output(
                    ["git", "log", "-n", "20", "--pretty=format:%h|%ad|%d|%s", "--date=iso"],
                    cwd=ROOT_DIR, text=True, encoding="utf-8", errors="replace"
                )
                commits = []
                for line in log_out.splitlines():
                    parts = line.split("|", 3)
                    if len(parts) == 4:
                        commits.append({
                            "hash": parts[0].strip(),
                            "date": parts[1].strip(),
                            "refs": parts[2].strip(),
                            "subject": parts[3].strip()
                        })
                remote_out = subprocess.check_output(
                    ["git", "remote", "get-url", "origin"],
                    cwd=ROOT_DIR, text=True, encoding="utf-8", errors="replace"
                ).strip()
            except Exception as e:
                commits = []
                remote_out = str(e)
            self._send_json({
                "ok": True,
                "remote": remote_out,
                "commits": commits
            })
            return

        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/ingest-delta":
            self._handle_ingest_delta()
            return
        self._send_json({"ok": False, "error": "Endpoint not found"}, status=404)


if __name__ == "__main__":
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("", PORT), ContractPlatformHandler) as httpd:
        print(f"Servidor da Plataforma Contrato 9291/2025 ativo em: http://localhost:{PORT}/plataforma-controle-9291/index.html")
        httpd.serve_forever()
