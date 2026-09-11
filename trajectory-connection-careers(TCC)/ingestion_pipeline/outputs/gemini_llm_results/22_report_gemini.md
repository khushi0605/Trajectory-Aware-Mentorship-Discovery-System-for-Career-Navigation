# Baseline Trajectory Report

**Background:** Lilah Harryman is a PL/SQL Developer with over a year of experience in designing, developing, and optimizing database applications, specializing in Oracle PL/SQL, SQL tuning, and data modeling.
**Goal:** Lilah aims to continue advancing in her career as a PL/SQL Developer, focusing on enhancing system performance and reliability through innovative database solutions.

---

## 1. Recommended Path

* **Phase 1: Deepen Oracle Core Architecture & Modern Database DevOps (Months 1–12)**
* **Objective:** Expand from writing isolated stored procedures and packages to mastering Oracle internal architecture, advanced diagnostic instrumentation, and automated deployment pipelines.
* **Focus Areas:** Oracle 19c/23ai database internals, Automatic Workload Repository (AWR), Active Session History (ASH), SQL Plan Management (SPM), advanced indexing (bitmap, function-based, partition pruning), and Database DevOps (Liquibase/Flyway integrated into Git-based CI/CD).
* **Milestone:** Refactor a high-volume batch processing job into bulk-processing logic (FORALL / BULK COLLECT) using version-controlled migration scripts, reducing batch window time by 30%+ with zero production downtime.


* **Phase 2: Transition into Mid/Senior Database Engineer with Cloud Integration (Months 12–24)**
* **Objective:** Break out of proprietary on-premise silos by connecting Oracle systems with modern cloud platforms and programmatic data pipelines.
* **Focus Areas:** Oracle Autonomous Database / Oracle Cloud Infrastructure (OCI), AWS RDS for Oracle, programmatic data manipulation with Python (oracledb, SQLAlchemy), and REST API integration using Oracle REST Data Services (ORDS).
* **Milestone:** Architect an end-to-end data integration module connecting an Oracle database with cloud-native data pipelines via ORDS and Python, establishing automated schema migration testing in staging environments.


* **Phase 3: Mature into Senior Oracle Database Engineer / Performance Architect (Year 2+)**
* **Objective:** Establish formal authority over database reliability, complex system migrations, and architectural governance.
* **Focus Areas:** Advanced database reliability engineering, high-availability architecture (Oracle Data Guard, Real Application Clusters [RAC]), database security (Transparent Data Encryption, Virtual Private Database), and technical mentorship.
* **Milestone:** Step into a Senior Oracle Database Engineer or Database Solutions Architect role, driving platform stability, multi-terabyte data migrations, and reliability across enterprise transactional systems.



**Reasoning:** The candidate has an educational background aligned with this domain (B.S. in IT with PL/SQL specialization from University of Arkansas), legitimate enterprise employer exposure (Windstream, J.B. Hunt), and valid industry certifications (Oracle OCA, Microsoft SQL Server). While her stated experience is early-career (~1–2 years post-graduation), she has demonstrated a solid grasp of core procedural database concepts. Her fastest route to advancement is not switching stacks, but becoming an indispensable performance-tuning and cloud-integrated database engineer who bridges classical PL/SQL routines with modern CI/CD and cloud managed services.

---

## 2. Risk Analysis & Feasibility Flags

* **Scope and Metric Plausibility Flags:**
* Claiming to have *"Spearheaded a team of 4 developers"* while holding the title of **Associate** PL/SQL Developer at J.B. Hunt within months of college graduation will be viewed with skepticism by senior engineering managers.
* Stating that she *"migrated over 500,000 customer records"* is framed as a major win, but 500k rows is a relatively small dataset in enterprise Oracle contexts. Overemphasizing this metric signals junior-level scale to hiring managers accustomed to processing tens or hundreds of millions of rows.


* **Narrow Ecosystem Lock-In (The "PL/SQL Silo"):** Pure PL/SQL developer roles are increasingly constrained to legacy ERPs, telecommunications billing, and financial core engines. Many modern tech stacks avoid embedding business logic inside database engines (preferring application-tier services with lightweight data layers). Over-specializing solely in stored procedures without broader cloud, Python, or data engineering skills limits market mobility.
* **Lack of Programmatic & Cloud Tooling:** The resume lists no general-purpose scripting languages (such as Python or Bash), no cloud providers (AWS, Azure, OCI), and no infrastructure/DevOps tools (Docker, Git, CI/CD). Modern database development requires automation outside the database console.
* **Resume Layout & Formatting Artifacts:** Stray symbols and template markers (`@ lilah.harryman@gmail.com`, `X& (939) 745-4405`, `9 123 Oak Street`) detract from an otherwise structured background and should be cleaned up for professional corporate screening.

---

## 3. Experience Analysis & Skills to Acquire

**Technical Skills to Acquire:**

* **Advanced Oracle Diagnostics & Tuning:** Interpreting AWR/ASH reports, execution plans, SQL Trace/TKPROF, hints, optimizer statistics management, and indexing strategies.
* **Python for Data Pipelines:** Writing automation scripts using `python-oracledb` to handle ETL tasks, automated data validation, and database health monitoring.
* **Database DevOps & Schema Versioning:** Liquibase or Flyway coupled with Git and GitHub Actions/GitLab CI to replace manual script executions with automated, tested database release pipelines.
* **Modern Oracle Cloud & API Services:** Oracle REST Data Services (ORDS) to expose database procedures as RESTful endpoints, and managing Oracle workloads on AWS RDS or Oracle Autonomous Transaction Processing (ATP).

**Common Hurdles & Transition Struggles:**

* **Moving Away from Business Logic in the Database:** Many modern software engineering teams actively discourage placing business rules inside triggers and stored procedures; learning to collaborate with backend engineers to place logic in the application tier while optimizing the database for pure set-based I/O throughput is a critical shift.
* **Transitioning from Single-Table Scripts to Distributed Architectures:** Adapting procedural mindset (loops, cursors) to highly parallelized, set-based operations and understanding how relational data models interact with distributed caching layers (Redis) and message brokers (Kafka).
* **Calibrating Early-Career Narrative:** Moving away from exaggerating early-tenure leadership claims ("spearheading teams" as an associate) toward demonstrating authentic, hands-on technical competence in resolving complex query regressions and concurrency deadlocks.

---

## 4. Mentor Discovery Strategy

The candidate should seek mentors who have deep expertise in enterprise database platforms and have guided databases through modernization:

* **Target Profiles & Job Titles:**
* **Principal / Lead Oracle Database Architect (Enterprise / Telecom / Logistics):** A veteran Oracle ACE or certified professional who understands the deep internals of Oracle 19c/23ai, RAC, and AWR tuning, and can review advanced performance scenarios.
* **Lead Data Platform / Database DevOps Engineer:** A practitioner who has modernized traditional DBA/developer teams by implementing automated database CI/CD, Liquibase, and cloud migrations.
* **Engineering Manager (Data Infrastructure / Core Banking & Billing Systems):** A hiring manager who leads database-heavy engineering units, capable of advising the candidate on how to present realistic, high-impact achievements that appeal to enterprise hiring bars.



**Relevance:** These mentors will help the candidate elevate her foundational PL/SQL knowledge into advanced performance tuning and database reliability engineering, while guiding her to expand beyond proprietary stored procedures into cloud integration and modern Database DevOps practices.