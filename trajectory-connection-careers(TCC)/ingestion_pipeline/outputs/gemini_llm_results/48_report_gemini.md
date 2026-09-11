# Baseline Trajectory Report

**Background:** A Computer Science student with experience in C++, concurrent programming, and database internals, having worked on projects such as buffer pool management and CHIP-8 emulator in Rust.

**Goal:** To pursue a career in systems software and performance-oriented engineering, focusing on developing efficient and scalable solutions.

## 1. Recommended Path

* **Phase 1: Deepen Systems Core & Benchmarking (2026–2027)**
* Expand database internals work beyond the buffer pool manager (CMU BusTub) into execution engines: implement B+ tree indexing, volcano/vectorized query execution, and write-ahead logging (WAL/ARIES recovery) in modern C++20 or Rust.
* Rigorously benchmark systems projects using automated stress-testing suites, race-condition detectors (ThreadSanitizer, AddressSanitizer), and CPU/memory profilers (`perf`, Valgrind/Cachegrind, Google Benchmark).
* Complete final-year undergraduate requirements while leveraging the Akamai and Gauntlet internships to pursue early-career systems, storage, and platform engineering roles.


* **Phase 2: Step into Core Systems / Storage / Database Engineering (Years 1–2 Post-Grad)**
* Target database vendors, cloud infrastructure providers, or systems software teams (e.g., Akamai, Cockroach Labs, SingleStore, MongoDB, Snowflake, Red Hat, Databricks).
* Work on storage engines, disk scheduling, memory allocators, or distributed execution runtimes where low-level latency and concurrency correctness are critical.


* **Phase 3: Advance to Senior Systems Engineer / Performance Architect (Years 3–5)**
* Own core components of distributed storage, database engines, or low-latency runtime kernels.
* Lead technical design for high-concurrency protocols, lock-free data structures, and hardware-accelerated data processing (SIMD, cache-line optimization).



**Reasoning:**

Nikhitha possesses strong foundational skills in low-level systems programming (C++17, Rust), concurrency primitives (shared mutexes, atomic reference counting, RAII guards), and database storage internals (adaptive replacement caching, asynchronous disk scheduling), reinforced by an exceptional academic record (9.15 CGPA, distinction scholarships). Internships at Akamai and Gauntlet demonstrate versatility across applied systems, static analysis, and enterprise RAG pipelines. Channeling this trajectory directly into database and storage internals capitalizes on her demonstrated strengths in concurrency and performance engineering.

## 2. Risk Analysis & Feasibility Flags

* **Undergraduate Timeline:** As an undergraduate graduating in mid-2027, full-time opportunities are governed by graduation dates; pre-placement offers (PPOs) from Akamai or off-campus systems hiring timelines must be managed proactively.
* **Academic Coursework Project Perception:** The CMU BusTub project and CHIP-8 emulator are well-known student curriculum projects. While technically rigorous, top-tier systems teams evaluate whether a candidate can write novel systems code from scratch, manage complex build systems, and handle non-academic production edge cases.
* **Diluted Systems Narrative:** The resume lists frontend and mobile application frameworks (Flutter, React, Firebase) alongside web scraping scripts. For specialized performance and systems roles, prominent inclusion of high-level scripting and app-dev tools can dilute focus during technical resume screening.
* **Selective Niche Market:** Roles specifically hiring new graduates into C++ or Rust storage engines and kernel/runtime systems are fewer in number and carry a high technical bar compared to generalist backend or full-stack roles.

## 3. Experience Analysis & Skills to Acquire

**Technical Skills to Acquire:**

* **Modern C++ Standards & Memory Models:** C++20/C++23 features (concepts, coroutines, ranges, `std::atomic` memory orders: acquire-release semantics, sequential consistency).
* **Low-Level Linux I/O & OS Internals:** Asynchronous I/O via **io_uring**, direct I/O (`O_DIRECT`), memory-mapped files (`mmap`), page cache behavior, and Linux process scheduling.
* **Performance Profiling & Microbenchmarking:** Profiling CPU cache misses, branch mispredictions, memory allocations, and flamegraphs using `perf`, eBPF/BCC tools, and heap profilers (Jemalloc, TCMalloc).
* **Lock-Free Concurrency & Vectorization:** Lock-free queues, compare-and-swap (CAS) primitives, false sharing mitigation (cache-line alignment), and SIMD vector instructions (AVX-512, NEON).
* **Distributed Storage Fundamentals:** Replication models, consensus algorithms (Raft, Paxos), distributed write-ahead logging, and LSM-tree storage engines (RocksDB internals).

**Common Transition Hurdles:**

* **Bridging Coursework to Production Scale:** Moving from educational database assignments with pre-built scaffolding (like CMU BusTub) to designing entire subsystems, custom memory allocators, and thread pools from scratch.
* **Mastering Concurrency Edge Cases:** Transitioning from basic thread safety with mutual exclusion locks to high-throughput, low-contention concurrent programming without introducing deadlocks, data races, or priority inversions.
* **Structuring the Resume for Systems Filters:** Pruning out auxiliary web scraping and mobile app bullets to give prime visual weight to memory-managed systems code, compiler sanitizers, and latency benchmarks.

## 4. Mentor Discovery Strategy

Nikhitha should target mentors with the following backgrounds:

* **Target Profiles & Job Titles:**
* **Staff / Senior Database Engine Engineer** at database or storage infrastructure companies (e.g., Cockroach Labs, PingCAP, ScyllaDB, SingleStore, ClickHouse).
* **Principal Systems Software Engineer** working on low-latency distributed storage, file systems, or OS runtimes at cloud infrastructure platforms (e.g., Akamai Ghost/Storage teams, Cloudflare, Fastly, AWS EC2/EBS).
* **Open-Source Database / Systems Maintainer** actively contributing to production C++ or Rust storage engines (e.g., RocksDB, TiKV, DuckDB).


* **Strategic Value of These Mentors:**
* **Codebase & Architecture Critique:** Reviewing independent storage engine projects to advise on production-level benchmarking, memory layout optimizations, and sanitization testing.
* **Interview Preparation for Core Systems:** Providing mock technical interviews focusing on concurrency bug diagnosis, memory hierarchy analysis, and low-level C++/Rust language semantics.
* **Navigating High-Bar Systems Hiring:** Advising on converting intern experience at Akamai into a permanent systems-oriented engineering track and finding specialized infrastructure teams that hire junior talent.