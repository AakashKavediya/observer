# Track 2 — Task Sequencer: RAG Knowledge Base Taxonomy & Provenance

## 1. Overview
The Task Sequencer does not invent authoritative strategies or fabricate psychological claims. Every recommendation is grounded in traceable, published literature and clinical guidance on executive dysfunction, ADHD activation, autism sensory overload, and academic pacing.

---

## 2. Curated Knowledge Taxonomy

### A. Task Initiation
- **INIT-001**: *Activation & The 2-Minute Physical Threshold*
  - **Source**: Ellen Littman, Ph.D. / ADDitude Magazine (2023)
  - **Core Strategy**: Shrink the first step below neurological resistance threshold. Adopt the physical posture of starting.
- **INIT-002**: *Decoupling Deciding from Doing*
  - **Source**: Job Accommodation Network (JAN), U.S. Dept of Labor (2022)
  - **Core Strategy**: Separate the planning/decision phase from the execution phase to eliminate blank-slate freeze.

### B. Task Decomposition
- **DECOMP-001**: *Atomic Task Decomposition & Progressive Granularity*
  - **Source**: CHADD National Resource Center (2023)
  - **Core Strategy**: Subdivide tasks until resistance reaches zero. Propose only ONE atomic step at a time.

### C. Cognitive Overload
- **OVERLOAD-001**: *Choice Reduction in Acute Cognitive Overload*
  - **Source**: Autistic Self Advocacy Network (ASAN) (2021)
  - **Core Strategy**: Remove competing choices during working-memory collapse; provide exactly one path or explicit rest.

### D. Energy-Aware Planning
- **ENERGY-001**: *Capacity-Responsive Pacing & Spoon Theory in Academics*
  - **Source**: University of Michigan Student Accessibility and Accommodation Services (2023)
  - **Core Strategy**: Match low-energy windows with low-synthesis administrative tasks; do not shame fluctuating daily spoons.

### E. Body Doubling & Social Support
- **BODY-001**: *Virtual Body Doubling & Parallel Accountability*
  - **Source**: ADHD Foundation UK (2022)
  - **Core Strategy**: Calm parallel presence anchors the nervous system without supervisory or evaluative pressure.

### F. Rest & Transitions
- **REST-001**: *Sensory Decompression & Guilt-Free Transitions to Rest*
  - **Source**: National Autistic Society (UK) (2022)
  - **Core Strategy**: Rest is an essential biological requirement for cognitive recovery, not a reward to be earned.

### G. Academic & Professional Workflows
- **ACAD-001**: *Overcoming the Blank Page in Academic Writing*
  - **Source**: Purdue University Online Writing Lab (OWL) (2023)
  - **Core Strategy**: Draft Zero / Junk Draft: write an intentionally flawed placeholder sentence to transition from creation to editing.
- **CODE-001**: *Micro-Debugging: The First Failing Assertion*
  - **Source**: Carnegie Mellon Software Engineering Institute (2022)
  - **Core Strategy**: Isolate the narrowest observable failure (run test once, inspect line number) rather than simulating the full graph.

---

## 3. Local Ingestion & Index Rebuilding
Knowledge documents are stored in JSON format at `observer/engine/observer_engine/sequencer/knowledge_base/curated_knowledge.json`.

To rebuild the vector index locally:
- Via UI: Click **Diagnostics** -> **Rebuild Index**.
- Via Python CLI:
  ```bash
  PYTHONPATH=observer/engine python3 -c "from observer_engine.sequencer.rag_engine import RagEngine; RagEngine().rebuild_index()"
  ```
Zero cloud API calls are made during ingestion, embedding, or retrieval.
