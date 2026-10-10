import os
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import psycopg2
import redis

from app.logic import BadJob, build_message, parse_job

QUEUE = "notifications"                  # producers push here
PROCESSING = "notifications:processing"  # jobs currently being handled
DEAD = "notifications:dead"              # jobs that can never succeed
STALE_AFTER = 30                         # seconds without a heartbeat = unhealthy

state = {"running": True, "heartbeat": time.time()}


def log(msg):
    print(f"[worker] {msg}", flush=True)   # flush so `docker compose logs` shows it live


# ---------- health endpoint ----------
class Health(BaseHTTPRequestHandler):
    def do_GET(self):
        alive = time.time() - state["heartbeat"] < STALE_AFTER
        if self.path == "/health" and alive:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        else:
            self.send_response(503)
            self.end_headers()

    def log_message(self, *args):
        pass                                # keep the logs quiet


# ---------- graceful shutdown ----------
def stop(*_):
    log("stop signal received, finishing current job")
    state["running"] = False


# ---------- database ----------
def save_with_retry(job) -> bool:
    """Insert the notification. Retry while the DB is unreachable.
    Returns False only if we were told to stop.
    Raises psycopg2.Error for permanent problems (bad data)."""
    while state["running"]:
        try:
            conn = psycopg2.connect(
                host=os.environ["DB_HOST"], dbname=os.environ["DB_NAME"],
                user=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
                connect_timeout=5)
            try:
                with conn, conn.cursor() as cur:   # commits on success, rolls back on error
                    cur.execute(
                        "INSERT INTO notifications (user_id, application_id, message) "
                        "VALUES (%s, %s, %s)",
                        (job["user_id"], job["application_id"], build_message(job["status"])))
            finally:
                conn.close()                       # "with conn" does not close it
            return True
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
            log(f"database unavailable ({e}); retrying in 3s")
            time.sleep(3)
    return False


# ---------- main loop ----------
def recover_orphans(r):
    """Jobs left in 'processing' by a crashed worker go back to the queue.
    Assumes ONE worker instance; with several, this could steal in-flight jobs."""
    moved = 0
    while r.lmove(PROCESSING, QUEUE, src="RIGHT", dest="RIGHT"):
        moved += 1
    if moved:
        log(f"recovered {moved} unfinished job(s)")


def main():
    threading.Thread(target=lambda: HTTPServer(("0.0.0.0", 8000), Health).serve_forever(),
                    daemon=True).start()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    r = redis.Redis(host=os.environ.get("REDIS_HOST", "redis"), decode_responses=True)
    log("started")

    while state["running"]:
        try:
            recover_needed = False
            if not state.get("recovered"):
                recover_orphans(r)
                state["recovered"] = True

            # Atomically take a job and park it in 'processing'; wait up to 5 s.
            raw = r.blmove(QUEUE, PROCESSING, 5, src="RIGHT", dest="LEFT")
            state["heartbeat"] = time.time()
            if raw is None:
                continue                          # nothing arrived; loop again

            try:
                job = parse_job(raw)
                if not save_with_retry(job):
                    break                         # shutting down; job stays in 'processing'
                log(f"saved '{job['status']}' notification for application {job['application_id']}")
            except (BadJob, psycopg2.Error) as e:
                log(f"moving job to dead-letter list ({e}): {raw!r}")
                r.lpush(DEAD, raw)

            r.lrem(PROCESSING, 1, raw)            # done (or dead-lettered): remove from 'processing'

        except redis.ConnectionError as e:
            log(f"redis unavailable ({e}); retrying in 3s")
            time.sleep(3)

    log("stopped")


if __name__ == "__main__":
    main()