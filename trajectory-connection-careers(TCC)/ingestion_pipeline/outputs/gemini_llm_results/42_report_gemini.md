# Baseline Trajectory Report

**Background:** Alex Greenwood is a mid-tier Java Developer with over 7 years of experience in back-end development, transitioning into front-end engineering, and has a strong foundation in web development and a growing interest in mobile app development.

**Goal:** Alex aims to leverage his extensive Java development experience and recent training in iOS app development to migrate into mobile app development and take on new challenges.

## 1. Recommended Path

* **Phase 1: Choose Platform Direction & Ship Production Mobile Apps (Months 1–4)**
* Decide between native iOS (Swift/SwiftUI) or Android (Kotlin/Jetpack Compose). Given Alex's deep Java foundation, Android offers the fastest lateral transition, while iOS leverages the Coursera coursework. Alternatively, cross-platform frameworks (Flutter or React Native) capitalize on both front-end and back-end fluency.
* Build and deploy at least two complete, polished mobile applications to the Apple App Store or Google Play Store. Case studies must showcase offline caching, background syncing, RESTful API integration, and reactive UI architecture.


* **Phase 2: Target Mobile Engineer / Full-Stack Mobile Roles (Months 5–9)**
* Target mid-market product companies, digital agencies, or tech startups seeking engineers who can bridge mobile client development with backend API integration.
* Position past enterprise Java and backend architecture experience as a competitive advantage: Alex understands API contract design, microservices, serialization, and database limits far better than a pure client-side mobile developer.


* **Phase 3: Advance to Senior Mobile Engineer or Mobile Tech Lead (Years 2–4)**
* Own end-to-end client architecture, performance profiling (memory leaks, frame drops, battery consumption), and continuous delivery pipelines for mobile (Fastlane, CI/CD).
* Direct technical mobile design reviews and align mobile roadmaps with backend platform capabilities.



**Reasoning:**

Alex already possesses strong software engineering rigor, having led development on 70+ projects, authored 100+ design docs, and managed cross-functional teams. The pivot from enterprise backend Java to mobile development is a proven engineering path. Because hiring managers for mobile roles look for live, published applications rather than coursework certificates, building and shipping production apps that connect to complex backend services will validate mobile competency quickly.

## 2. Risk Analysis & Feasibility Flags

* **The "Coursework-Only" Mobile Risk:** Alex's mobile experience is currently limited to an online Coursera certificate in iOS development. Without published apps in the App Store/Play Store or professional production experience, recruiters will classify Alex as a junior candidate for mobile-specific roles.
* **Platform Divergence (Java vs. Swift/iOS):** Alex's core expertise is Java/J2EE, but the stated training is in iOS (Swift). Attempting to pitch as an iOS developer completely bypasses 7+ years of JVM depth. If targeting iOS, Alex must prove modern Swift/SwiftUI fluency; if targeting Android, Alex must modernize Java skills into Kotlin.
* **Legacy Stack Artifacts:** The resume lists legacy enterprise technologies (J2EE, SOAP, Sun Certified Java Programmer 2015, PHP, jQuery). While demonstrating enterprise longevity, these keywords can signal outdated development methodologies to modern mobile and product engineering teams.
* **Resume Timeline Discrepancies:** The education section lists Ohio State University (2010–2014) while also mentioning playing for the "CSU Cougars" (a different institution), along with an OCR/typo error on the IEEE certification ("2076"). These details create verification friction during executive or background screening.

## 3. Experience Analysis & Skills to Acquire

**Technical Skills to Acquire:**

* **Native Mobile Languages & Tooling:** Modern **Swift 5/6 & SwiftUI** (with Xcode) for iOS, or **Kotlin & Jetpack Compose** (with Android Studio) for Android.
* **Mobile Architecture Patterns:** MVVM, Clean Architecture, MVI (Model-View-Intent), dependency injection (Dagger/Hilt for Android, Swift Package Manager/Swinject for iOS), and reactive programming (Combine/Async-Await or Kotlin Coroutines/Flow).
* **Local Persistence & Networking:** Room/Core Data, SQLite, offline-first architectures, background task scheduling, and secure token/keychain storage.
* **Performance & Diagnostics:** Profiling memory allocations, fixing UI thread blocking, reducing app bundle sizes, and battery drain optimization via Xcode Instruments or Android Profiler.
* **Mobile DevOps:** Automated app building and signing using Fastlane, GitHub Actions, and deployment through TestFlight or Google Play Console internal testing tracks.

**Common Transition Hurdles:**

* **Unlearning Headless Backend Assumptions:** Transitioning from stateless, request-response server environments to stateful, lifecycle-sensitive client environments subject to OS-level background kills and memory pressures.
* **Navigating UI Thread Constraints:** Mastering concurrency on mobile devices, ensuring network calls and heavy database parsing never block the main rendering thread.
* **Salary or Leveling Calibration:** Transitioning fields often involves managing the risk of being down-leveled from a Mid/Senior Backend Developer to a Junior Mobile Developer unless the candidate can present full-stack ownership and architectural depth.

## 4. Mentor Discovery Strategy

Alex should target mentors with the following backgrounds:

* **Target Profiles & Job Titles:**
* **Lead Mobile Engineer / Staff Android or iOS Architect** who originally started their career as a backend Java or enterprise software engineer.
* **Mobile Engineering Manager** at a tech product company who oversees cross-functional mobile (iOS/Android) and backend integration teams.
* **Principal Mobile Consultant** at a mobile-first digital consultancy (e.g., Thoughtbot, WillowTree, Bottle Rocket) experienced in rapidly delivering client-facing mobile applications.


* **Strategic Value of These Mentors:**
* **Platform Selection Calibration:** Helping Alex decide whether to pursue the native Android route (leveraging deep Java fundamentals) or commit fully to native iOS / cross-platform.
* **Portfolio and Code Architecture Critique:** Reviewing mobile app repositories to ensure structure matches modern enterprise standards (e.g., modularization, UI testing, declarative views) rather than simple tutorial patterns.
* **Lateral Transition Strategy:** Coaching Alex on how to pitch internal transfers or full-stack mobile roles that reward backend expertise rather than competing against entry-level mobile bootcamp graduates.