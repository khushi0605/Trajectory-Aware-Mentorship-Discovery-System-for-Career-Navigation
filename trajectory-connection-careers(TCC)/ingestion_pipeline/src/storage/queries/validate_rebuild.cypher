MATCH (n) RETURN labels(n), count(*);
MATCH ()-[r]->() RETURN type(r), count(*);
MATCH (d:Decision)-[:TRIGGERED_TRANSITION]->(j:Job) RETURN d.text, j.role LIMIT 10;
MATCH (c:Candidate)-[:MADE_DECISION]->(d) RETURN c.id, d.text LIMIT 10;
