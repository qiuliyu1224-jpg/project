"""Atomic deadline closure and opt-in automatic result publication.

Legacy activities retain manual publication until their owner explicitly changes
the setting. Private results never become public through this task.
"""
import time


def refresh(con, now=None):
    """Close elapsed activities and publish eligible opt-in public results.

    A savepoint preserves the caller's transaction. The same function is used
    by incoming requests and the maintenance worker, so neither a browser nor
    an open results page is required for deadline processing.
    """
    from voting_rules import counts, event_row

    now = int(time.time()) if now is None else int(now)
    con.execute('SAVEPOINT deadline_publication')
    try:
        closed = con.execute(
            "UPDATE elections SET status='CLOSED',paused=0 "
            "WHERE status='OPEN' AND ends_at<=?", (now,)
        ).rowcount
        pending = con.execute(
            "SELECT * FROM elections WHERE status='CLOSED' "
            "AND visibility='PUBLIC' AND auto_publish=1 AND published=0"
        ).fetchall()
        published = 0
        for row in pending:
            event = event_row(row)
            # Round one is not a final outcome when a fresh runoff is needed.
            # Ties/no-votes remain transparent statuses, never invented winners.
            if event['method'] == 'MAJORITY' and counts(con, event)['state'] == 'RUNOFF_REQUIRED':
                continue
            published += con.execute(
                "UPDATE elections SET published=1 WHERE id=? AND status='CLOSED' "
                "AND visibility='PUBLIC' AND auto_publish=1 AND published=0",
                (event['id'],)
            ).rowcount
        con.execute('RELEASE SAVEPOINT deadline_publication')
        return {'closed': closed, 'published': published}
    except Exception:
        con.execute('ROLLBACK TO SAVEPOINT deadline_publication')
        con.execute('RELEASE SAVEPOINT deadline_publication')
        raise
