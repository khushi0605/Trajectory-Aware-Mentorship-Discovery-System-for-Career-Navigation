// src/storage/queries/candidate_job_queries.cypher
// ===============================================
// Candidate ↔ Job Queries (Fixed Version)
// ===============================================

// 1️⃣ Top N candidates for a given job (example role: 'android_app_developer_trainee')
MATCH (c:Candidate)-[r:MATCHES_JOB]->(j:Job {role: 'android_app_developer_trainee'})
RETURN c.user_id, r.score AS MatchScore, c.experience_level
ORDER BY MatchScore DESC
LIMIT 10;

// 2️⃣ All jobs a candidate matches above a threshold (example user: 'user_ac9f7c933787', threshold 0.2)
MATCH (c:Candidate {user_id: 'user_ac9f7c933787'})-[r:MATCHES_JOB]->(j:Job)
WHERE r.score > 0.2
RETURN j.role, r.score AS MatchScore
ORDER BY MatchScore DESC;

// 3️⃣ Skill gap analysis between candidate and a job
MATCH (j:Job {role: 'android_app_developer_trainee'})-[:REQUIRES_SKILL]->(s:Skill)
MATCH (c:Candidate {user_id: 'user_ac9f7c933787'})
OPTIONAL MATCH (c)-[hs:HAS_SKILL]->(s)
WITH c, j, s, hs
WHERE hs IS NULL
RETURN c.user_id AS Candidate, j.role AS Job, collect(s.name) AS MissingSkills;

// 4️⃣ Candidates sharing the same domain (example domain: 'web_dev')
MATCH (c:Candidate)-[:IN_DOMAIN]->(d:Domain {name: 'web_dev'})
RETURN c.user_id AS Candidate, c.experience_level AS ExperienceLevel
ORDER BY c.user_id;

// 5️⃣ Visualize a candidate’s full graph (example user: 'user_ac9f7c933787')
MATCH path=(c:Candidate {user_id: 'user_ac9f7c933787'})-[*1..2]-()
RETURN path
LIMIT 50;

// 6️⃣ Find candidates who faced the same struggle type as candidate X
MATCH (c:Candidate {user_id: 'user_ac9f7c933787'})-[:FACED]->(s:Struggle)-[:IN_DOMAIN]->(d:Domain)
MATCH (other:Candidate)-[:FACED]->(s2:Struggle)-[:IN_DOMAIN]->(d)
WHERE other.user_id <> 'user_ac9f7c933787'
RETURN other.user_id, s2.text, d.name ORDER BY d.name;

// 7️⃣ Find candidates who made the same role transition
MATCH (c:Candidate)-[:MADE_DECISION]->(dec:Decision)-[:TRIGGERED_TRANSITION {
  from_role: 'software_engineer', to_role: 'data_scientist'
}]->(j:Job)
RETURN c.user_id, dec.text, dec.confidence ORDER BY dec.confidence DESC;

// 8️⃣ Find candidates whose learning patterns share a theme with a query list
MATCH (c:Candidate)-[:LEARNED_VIA]->(lp:LearningPattern)
WHERE any(theme IN ['machine_learning', 'backend'] WHERE lp.themes CONTAINS theme)
RETURN c.user_id, lp.text, lp.themes;

// 9️⃣ Shortest reachability path between two candidates via shared Skill + Decision
MATCH path = shortestPath(
  (a:Candidate {user_id: 'user_ac9f7c933787'})-[:HAS_SKILL|MADE_DECISION*..6]-(b:Candidate {user_id: 'user_76f9f0b30307'})
)
RETURN path;