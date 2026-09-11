# Baseline Trajectory Report

**Background:** Aditya Hegde is a B.Tech in Computer Science Engineering student with a focus on automation, build routines, and dynamic program loading, proficient in C, GoLang, Rust, and Python, and experienced in Git, Perforce, and Docker.

**Goal:** Aditya aims to continue his career in software engineering, focusing on automation, build systems, and distributed systems, leveraging his experience in internships and open-source projects.

## 1. Recommended Path

* **Phase 1: Deepen Systems Engineering Portfolio & Production Packaging (2026–2027)**
* Take core systems projects from "toy / WIP" implementations to rigorously benchmarked open-source libraries. Specifically, add comprehensive property-based testing (e.g., `proptest` for Rust), fuzzing, and Chaos Engineering simulation suites (e.g., Jepsen-style network partition tests) to **Quaso** (Raft consensus) and **Meerkat** (leaderless directory sync).
* Translate Akamai internship outcomes (build automation, profile-guided optimization / PGO on Akamai GHost) into technical case studies on modern build performance (e.g., Bazel, mold/lld linkers, cache orchestration).
* Complete final-year undergraduate studies while targeting elite infrastructure-focused engineering internships or new-grad roles.


* **Phase 2: Transition into Systems / Distributed Infrastructure Engineer (Years 1–2 Post-Grad)**
* Target platform infrastructure, CDN/edge compute, cloud runtime, or distributed database organizations (e.g., Akamai, Cloudflare, Fastly, Databricks, PingCAP, ScyllaDB, CockroachDB).
* Work on low-level network stacks, distributed storage, or internal developer platform tooling (build orchestration, CI cache distribution, low-latency RPC frameworks).


* **Phase 3: Advance to Senior Systems Engineer / Core Infrastructure Lead (Years 3–5)**
* Drive critical architecture across large-scale distributed consensus engines, kernel-space acceleration (eBPF, DPDK, io_uring), or large-scale build/artifact pipelines.
* Lead technical RFCs for mission-critical distributed services and mentor junior systems programmers.



**Reasoning:**

Aditya exhibits an exceptionally strong technical foundation in low-level systems programming (C, Rust, Go) and distributed systems fundamentals (Raft, buffer pool management, kernel-space key-value stores, distributed file systems). His high academic distinction (8.94 CGPA, CNR-Rao distinction across 6 semesters) coupled with production infrastructure experience at Akamai positions him directly for high-complexity core systems engineering. Focusing early career steps on platform, runtime, and distributed storage infrastructure avoids generalist product development and directly fulfills his systems engineering aspirations.

## 2. Risk Analysis & Feasibility Flags

* **Undergraduate Timeline Constraint:** As a 2023–2027 B.Tech candidate, full-time employment is tied to university graduation cycles. Securing extended pre-placement offers (PPOs) or specialized remote off-campus roles before mid-2027 requires proactive planning.
* **The "Toy Project" Perception:** Multiple impressive projects are marked as "toy implementation", "WIP", or course-related. Technical hiring committees at top infrastructure firms look for production robustness—such as edge-case fault tolerance, deterministic simulation, and formal verification—over simple functional prototypes.
* **Niche Systems Hiring Market:** Junior roles dedicated purely to low-level systems (Rust/C kernel modules, custom consensus protocols) are more limited and selective than general full-stack or backend web development roles. Aditya must maintain broad distributed systems appeal (e.g., Go/microservices/gRPC) alongside low-level Rust/C work.
* **Over-Breadth Across Systems Layers:** The portfolio spans embedded microcontrollers (Raspberry Pi Pico OS/schedulers), kernel-space KV stores, hypervisor orchestration (Proxmox), and application-level consensus. While demonstrating broad technical range, specialized teams in distributed systems want clear proof of depth in network protocols, concurrency, and distributed state machines.

## 3. Experience Analysis & Skills to Acquire

**Technical Skills to Acquire:**

* **Enterprise Build Systems & Toolchains:** Production mastery of hermetic, distributed build tools such as **Bazel** or **Buck2**, including remote execution pipelines and distributed artifact caching.
* **Modern Linux Kernel & Asynchronous I/O:** Production utilization of **io_uring**, **eBPF** (Cilium/BCC/libbpf) for low-overhead kernel tracing and network telemetry, and memory-mapped file I/O.
* **Distributed Systems Verification & Chaos Testing:** Fault-injection testing tools, formal verification concepts (TLA+ or Alloy for protocol modeling), and deterministic network simulation environments (e.g., Madsim for Rust).
* **High-Throughput Concurrency & Profiling:** CPU cache profiling (`perf`, Valgrind), memory safety analysis (ASan/TSan), flamegraph profiling, and lock-free data structures.
* **Production Observability & Metrics:** Structured metrics telemetry via OpenTelemetry, Prometheus, and distributed tracing across RPC boundaries.

**Common Transition Hurdles:**

* **Moving Beyond Academic Implementations:** Shifting from building paper implementations (e.g., vanilla Raft from the Ongaro/Ousterhout paper) to handling production realities: dynamic cluster membership changes, log compaction, snapshot distribution, and non-blocking disk I/O.
* **Navigating the High Systems Hiring Bar:** Rigorous live-coding interview rounds centered on multithreaded concurrency (mutexes, atomics, condition variables, reader-writer locks) and low-level Linux operating system internals.
* **Balancing Passion for Niche Systems with Industry Demand:** Managing career opportunities where everyday industry work may involve distributed cloud infrastructure (Kubernetes operators, Go microservices) rather than custom OS kernels and low-level microcontrollers.

## 4. Mentor Discovery Strategy

Aditya should target mentors with the following backgrounds:

* **Target Profiles & Job Titles:**
* **Staff / Principal Systems Engineer** at a cloud infrastructure, CDN, or database platform company (e.g., Akamai, Cloudflare, Fastly, Cockroach Labs, Redpanda).
* **Lead Infrastructure / Build Systems Engineer** (DevEx / Platform Engineering) who designs large-scale distributed compilation and CI/CD pipelines (e.g., Bazel / toolchain leads at Google, Meta, or Bloomberg).
* **Open Source Core Contributor / Maintainer** in major Rust or Go distributed systems projects (e.g., Tokio, etcd, TiKV, Envoy).


* **Strategic Value of These Mentors:**
* **Codebase & Architecture Maturation:** Reviewing custom implementations (like Quaso and Meerkat) to guide them toward production-grade resiliency, determinism, and benchmarking standards.
* **Navigating High-Bar Infrastructure Interviews:** Providing concrete preparation for systems design interviews that test distributed consensus, network latency budgets, and OS-level primitives.
* **Career Pathing at Graduation:** Advising on how to convert high-impact internships (such as Akamai's ghost-dev) into high-leverage infrastructure roles while bypassing standard campus generalist hiring pipelines.