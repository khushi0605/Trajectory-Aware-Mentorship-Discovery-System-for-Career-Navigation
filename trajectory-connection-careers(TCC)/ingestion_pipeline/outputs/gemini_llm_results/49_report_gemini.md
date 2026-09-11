# Baseline Trajectory Report

**Background:** Suchitra Shankar is an undergraduate in Computer Science & Engineering at PES University (Class of 2027, CGPA 8.57, CNR-Rao distinction) with deep domain expertise in distributed systems, storage engine internals, and performance profiling. Her record includes an ACM SIGMOD-affiliated workshop publication on LSM-tree compaction (*Amethyst*), a consensus implementation in Go (*MiniRaft*), causal profiling research (*MiCoz*), and industry R&D experience at Firebolt Analytics and Sansera Engineering.
**Goal:** Suchitra aims to continue her career in research and development, focusing on optimizing and analyzing complex systems and storage solutions (targeting Database Internals Engineer, Distributed Storage Systems Researcher, or Core Infrastructure Engineer).

## 1. Recommended Path

To establish herself as an authority in high-performance storage architectures and modern database internals, the recommended sequence focuses on core systems programming, open-source storage engine contributions, and elite industrial R&D placement:

1. **Deepen Storage Engine & Systems Programming in C++/Rust (Months 1–6):**
* Expand from Go into systems-level C++20 and Rust to interact with low-level kernel interfaces, zero-copy I/O (io_uring), and memory-mapped file systems.
* Contribute directly to production-grade distributed storage systems and analytical engines (e.g., RocksDB, Apache Arrow, Velox, DuckDB, or ClickHouse), specifically focusing on compaction heuristics, block cache eviction, and vectorized execution kernels.


2. **Target Specialized Storage & Database R&D Fellowships/Roles (Months 6–12):**
* Secure research engineer or storage engine internships at top database and infrastructure organizations (e.g., Firebolt, ClickHouse, SingleStore, Snowflake, Databricks, Cockroach Labs, or MongoDB).
* Submit follow-up research on adaptive LSM-tree memory layouts or vectorized Parquet scan performance to tier-1 database venues (SIGMOD, VLDB, or FAST).


3. **Choose Long-Term Specialization: Industry Core Systems vs. Systems Ph.D. (Months 12–24):**
* **Path A (Industry Database Kernel Engineer):** Join core storage and execution engine teams building analytical lakehouses, cloud data warehouses, or distributed transactional key-value stores.
* **Path B (Graduate Systems Research):** Leverage her SIGMOD/MASCOTS publications and strong GPA to pursue a fully-funded Ph.D. or MS in Computer Systems at global top-tier institutions specializing in database architectures and storage hardware (e.g., CMU Database Group, UW Systems Lab, or UIUC).



**Reasoning:** Suchitra already possesses what most undergraduate resumes lack: peer-reviewed research in database architectures (SIGMOD co-located FORMATS 2026), working implementations of Raft and LSM-trees, and empirical profiling rigor (p95/p99 tail latency, Mann–Whitney U hypothesis testing). Capitalizing on this rare storage engine niche rather than generic backend web development yields the highest career upside and compensation.

## 2. Risk Analysis & Feasibility Flags

* **Runtime Language Trade-Offs (Go vs. C++/Rust):** While Go is exceptional for distributed consensus and microservice control planes (Raft, Kubernetes, CockroachDB), core performance-critical storage engines and vectorized database execution engines (e.g., ClickHouse, Velox, DuckDB, RocksDB) predominantly require modern C++ or Rust to control memory allocations and eliminate garbage collection pauses.
* **Undergraduate Timeline Constraints:** As an undergraduate graduating in 2027, many specialized "Core Database Engine" openings typically list Master's/Ph.D. requirements or multi-year industry experience. Overcoming this requires leveraging her published research and active open-source codebase contributions.
* **Niche Market Concentration:** Pure storage engine and database kernel engineering roles represent a concentrated, highly technical segment of the software industry. Hiring processes focus intensively on concurrency primitives, cache coherence, CPU cache lines, and file system semantics.
* **Feasibility Verdict:** Exceptionally high feasibility for elite infrastructure R&D roles, database engineering teams, and top-tier graduate programs; requires deliberate demonstration of manual memory management and low-level kernel I/O to match the depth of her architectural designs.

## 3. Experience Analysis & Skills to Acquire

**Technical Skills to Acquire:**

* **Low-Level Storage Primitives:** Modern C++ (C++20), Rust, Linux kernel storage APIs (`io_uring`, `O_DIRECT`), and memory-mapped I/O.
* **Database Architecture Internals:** Vectorized query execution, SIMD acceleration for column-store filtering, buffer pool management, write-ahead logging (WAL), and MVCC concurrency control.
* **Advanced Storage Formats:** Deep structural mastery of Apache Parquet, Arrow, and Lance formats for analytical data processing.
* **Formal Verification for Distributed Systems:** TLA+ or Jepsen testing to validate consensus protocols, state-machine replication, and data-loss edge cases under network partitions.

**Common Hurdles & Transition Struggles:**

* **Managing GC Interference at Scale:** Overcoming Go's garbage collector when benchmarking microsecond-level storage latencies; moving to zero-allocation memory buffers and manual off-heap arenas.
* **Simulating Production-Scale Failures:** Scaling past local single-machine distributed testbeds to evaluate tail latency and write amplification under massive, skewed multi-terabyte production workloads.
* **Navigating the Academic vs. Production Implementation Gap:** Bridging elegant theoretical compaction algorithms with the messy edge cases of real-world databases (disk space exhaustion, power failure recovery, crash-consistent corruption handling).

## 4. Mentor Discovery Strategy

**Target Mentor Profiles:**

* **Principal Storage Engine Architect / Database Kernel Engineer:** A senior engineer at companies like Snowflake, ClickHouse, Databricks, or Cockroach Labs who designs distributed storage formats and compaction engines.
* **Database Systems Professor or Postdoctoral Researcher:** An academic affiliated with research groups focusing on storage hardware, persistent memory, and modern database kernels (e.g., CMU Database Group, Wisconsin Systems, or EPFL LAB).

**Relevance & Focus Areas:**

* **Past Job Titles to Search:** *Database Kernel Engineer*, *Staff Storage Systems Engineer*, *LSM-Tree / Engine Developer (RocksDB/Pebbles)*, *Systems Research Scientist (VLDB/SIGMOD)*.
* **Why They Are Relevant:** Mentors in this specialized domain can review engine architectures (like *Amethyst*), advise on navigating the transition from Go to low-level C++/Rust primitives, and provide warm introductions to specialized database engineering teams and top graduate research labs.