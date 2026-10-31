PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY, phone TEXT UNIQUE NOT NULL,
 name TEXT NOT NULL, salt TEXT NOT NULL, password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
 token TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), expires INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS elections (
 id INTEGER PRIMARY KEY, creator_id INTEGER NOT NULL REFERENCES users(id),
 title TEXT NOT NULL, method TEXT NOT NULL CHECK(method IN ('SINGLE','SCORE')),
 visibility TEXT NOT NULL CHECK(visibility IN ('PUBLIC','PRIVATE')),
 status TEXT NOT NULL DEFAULT 'DRAFT' CHECK(status IN ('DRAFT','OPEN','CLOSED')),
 duration INTEGER NOT NULL CHECK(duration BETWEEN 1 AND 10080),
 ends_at INTEGER, published INTEGER NOT NULL DEFAULT 0 CHECK(published IN (0,1))
);
CREATE TABLE IF NOT EXISTS candidates (
 id INTEGER PRIMARY KEY, election_id INTEGER NOT NULL REFERENCES elections(id), name TEXT NOT NULL,
 UNIQUE(id,election_id)
);
-- A round is explicit even though this increment supports only the first round.
CREATE TABLE IF NOT EXISTS rounds (
 id INTEGER PRIMARY KEY, election_id INTEGER NOT NULL REFERENCES elections(id), number INTEGER NOT NULL DEFAULT 1,
 UNIQUE(election_id,number), UNIQUE(id,election_id)
);
-- Participation and selections are separate. This is NOT cryptographic anonymity:
-- both tables retain an internal ballot link. No UI exports this link or identities.
CREATE TABLE IF NOT EXISTS ballots (
 id INTEGER PRIMARY KEY, election_id INTEGER NOT NULL, round_id INTEGER NOT NULL,
 user_id INTEGER NOT NULL REFERENCES users(id),
 FOREIGN KEY(round_id,election_id) REFERENCES rounds(id,election_id),
 UNIQUE(round_id,user_id), UNIQUE(id,election_id)
);
CREATE TABLE IF NOT EXISTS choices (
 ballot_id INTEGER NOT NULL, election_id INTEGER NOT NULL, candidate_id INTEGER NOT NULL,
 score INTEGER NOT NULL CHECK(typeof(score)='integer' AND score BETWEEN 0 AND 5),
 PRIMARY KEY(ballot_id,candidate_id),
 FOREIGN KEY(ballot_id,election_id) REFERENCES ballots(id,election_id),
 FOREIGN KEY(candidate_id,election_id) REFERENCES candidates(id,election_id)
);
CREATE TABLE IF NOT EXISTS audit (
 id INTEGER PRIMARY KEY, election_id INTEGER NOT NULL REFERENCES elections(id),
 actor_id INTEGER NOT NULL REFERENCES users(id), action TEXT NOT NULL, created INTEGER NOT NULL
);
