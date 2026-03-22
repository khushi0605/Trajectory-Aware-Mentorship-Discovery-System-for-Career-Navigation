// src/storage/queries/candidate_job_queries.cypher

// 1. Top N candidates for a given job (e.g., 'data_scientist')
MATCH (c:Candidate)-[r:MATCHES_JOB]->(j:Job {role: 'data_scientist'})
RETURN c.user_id, r.score AS MatchScore, c.experience_level
ORDER BY MatchScore DESC
LIMIT 10;

// 2. All jobs a candidate matches above a threshold (e.g., candidate 'user_123', threshold > 0.6)
MATCH (c:Candidate {user_id: 'user_123'})-[r:MATCHES_JOB]->(j:Job)
WHERE r.score > 0.6
RETURN j.role, r.score AS MatchScore
ORDER BY MatchScore DESC;

// 3. Skill gap analysis between candidate and job
MATCH (j:Job {role: 'data_scientist'})-[:REQUIRES_SKILL]->(s:Skill)
MATCH (c:Candidate {user_id: 'user_123'})
OPTIONAL MATCH (c)-[:HAS_SKILL]->(s)
WITH c, j, s, CASE WHEN (c)-[:HAS_SKILL]->(s) THEN true ELSE false END AS has_skill
WHERE has_skill = false
RETURN c.user_id AS Candidate, j.role AS Job, collect(s.name) AS MissingSkills;

// 4. Candidates sharing the same domain
MATCH (c:Candidate)-[:IN_DOMAIN]->(d:Domain {name: 'machine_learning'})
RETURN c.user_id AS Candidate, c.experience_level AS ExperienceLevel
ORDER BY c.user_id;

// 5. Visualize a Candidate's entire mapped ecosystem (Helpful for graph rendering tools like Neo4j Bloom)
MATCH path=(c:Candidate {user_id: 'user_123'})-[*1..2]-()
RETURN path;
