"""Small-demo lifecycle task, active only while the server process runs."""
import logging
import sqlite3
import threading


def start_maintenance(interval=5):
    import app
    stop=threading.Event()
    def run():
        while not stop.wait(interval):
            try:
                con=app.connect()
                try:
                    with con: app.refresh(con)
                finally: con.close()
            except sqlite3.Error:
                logging.exception('Deadline refresh failed; will retry')
    worker=threading.Thread(target=run,daemon=True,name='votelab-deadlines')
    worker.start()
    return stop,worker
