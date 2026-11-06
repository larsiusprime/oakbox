# Oakbox — OpenAVMKit in a Box

**Status:** v1.11 draft. Project setup is being redesigned one feature at a time to mirror OpenAVMKit (D41, §3.0);
agreed features go in §3.0 before any code. Earlier revisions followed a full read of the OpenAVMKit docs, checked
against its code (§6.3). Decisions are in §2; open items are in §10. How the code is built, as it stands:
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

The spec is in [docs/spec/](docs/spec/), one file per area. Its sections keep their numbers (§3.5, F9, D21): code
and the docs cite them, and the table below says where each one is.

## 1. Purpose

A desktop app that lets a non-technical assessor run OpenAVMKit on their own parcels, with no command line and no
hand-edited config. Download, double-click, work.

**Primary user:** a 50-year-old, tech-averse assessor at a small, underfunded office, on an old Windows PC, often
without admin rights.

**Success test:** that user can go from "downloaded" to "a PDF ratio study of my current values" with no outside help.

## The spec, by area

- [Decisions](docs/spec/decisions.md)
- [Project setup: the Data tab and before it](docs/spec/setup.md)
- [Step 1, Inputs: Bring in data](docs/spec/step-1-inputs.md)
- [Step 2, Model groups](docs/spec/step-2-model-groups.md)
- [Step 3, Sales: Check sales](docs/spec/step-3-sales.md)
- [Step 4, Evaluate: Check my values](docs/spec/step-4-evaluate.md)
- [Steps 5 and 6, Variables and Models](docs/spec/step-5-6-variables-and-models.md)
- [Step 7, Report, and what goes in and out](docs/spec/step-7-report.md)
- [Across the app: screens, rules, help and menus](docs/spec/app.md)
- [Going online, and enrichment](docs/spec/online-and-enrichment.md)
- [Platform: hardware, architecture, stack](docs/spec/platform.md)
- [Engine: OpenAVMKit changes](docs/spec/engine.md)
- [Milestones, scope and open items](docs/spec/roadmap.md)

## Where each section is

| Section | File | Heading |
|---|---|---|
| 2 | [decisions.md](docs/spec/decisions.md) | 2. Decisions |
| 3.0 | [setup.md](docs/spec/setup.md) | 3.0 Project setup, feature by feature |
| F1 | [setup.md](docs/spec/setup.md) | F1. New project |
| F1b | [setup.md](docs/spec/setup.md) | F1b. Project actions on the home screen |
| F2 | [setup.md](docs/spec/setup.md) | F2. Add a data file |
| F3 | [setup.md](docs/spec/setup.md) | F3. The project view: one tabbed panel |
| F3b | [setup.md](docs/spec/setup.md) | F3b. The input file list: show, rename, remove |
| F3c | [setup.md](docs/spec/setup.md) | F3c. Choosing a file's fields |
| F3d | [setup.md](docs/spec/setup.md) | F3d. The Fields tab: a guided wizard over all the files |
| F3e | [setup.md](docs/spec/setup.md) | F3e. Data › Enrichments: public data about each parcel (built) |
| F3f | [setup.md](docs/spec/setup.md) | F3f. Data › Deeds (built) |
| F3g | [setup.md](docs/spec/setup.md) | F3g. Data › Permits (built) |
| F4 | [step-1-inputs.md](docs/spec/step-1-inputs.md) | F4. Step 1, Inputs: Bring in data (its own tab, **1. Inputs**) |
| F5 | [step-2-model-groups.md](docs/spec/step-2-model-groups.md) | F5. Step 2, Model groups (its own tab, **2. Model groups**; §3.5 as built so far) |
| 3.5 | [step-2-model-groups.md](docs/spec/step-2-model-groups.md) | 3.5 Model group builder |
| F6 | [step-3-sales.md](docs/spec/step-3-sales.md) | F6. Step 3, Sales: Check sales (its own tab, **3. Sales**; notebook 2, clean) (built, but for the parts listed under "Not built yet") |
| 3.6 | [step-3-sales.md](docs/spec/step-3-sales.md) | 3.6 Sales review and overrides |
| F8 | [step-4-evaluate.md](docs/spec/step-4-evaluate.md) | F8. Step 4, Evaluate: Check my values (its own tab, **4. Evaluate**; built, but for the parts under "Not built yet") |
| 4.2 | [step-4-evaluate.md](docs/spec/step-4-evaluate.md) | 4.2 Ratio study report and standards profiles |
| F7 | [step-5-6-variables-and-models.md](docs/spec/step-5-6-variables-and-models.md) | F7. Step 5, Variables: Prepare the fields (its own tab, **5. Variables**; the tests, lists and models are F9) |
| F9 | [step-5-6-variables-and-models.md](docs/spec/step-5-6-variables-and-models.md) | F9. Steps 5 and 6, Variables and Models: the variable tests and lists, and the models (tab **6. Models**; slices 1 and 2 built, slice 3 in part: see As built) |
| 3.10 | [step-5-6-variables-and-models.md](docs/spec/step-5-6-variables-and-models.md) | 3.10 Building model values (steps 5 and 6) |
| F10 | [step-7-report.md](docs/spec/step-7-report.md) | F10. Step 7, Report (its own tab, **7. Report**; built 2026-11-01, `report.py`, `ReportTab.tsx`) |
| 4 | [step-7-report.md](docs/spec/step-7-report.md) | 4. Inputs, outputs and reports |
| 4.1 | [step-7-report.md](docs/spec/step-7-report.md) | 4.1 Import and export |
| 4.3 | [step-7-report.md](docs/spec/step-7-report.md) | 4.3 Reports and customization |
| 3.1 | [app.md](docs/spec/app.md) | 3.1 Home screen |
| 3.2 | [app.md](docs/spec/app.md) | 3.2 The guided build |
| 3.3 | [app.md](docs/spec/app.md) | 3.3 Project screen: the steps |
| 3.4 | [app.md](docs/spec/app.md) | 3.4 Plain-language rules |
| 3.7 | [app.md](docs/spec/app.md) | 3.7 Tax years |
| 3.8 | [app.md](docs/spec/app.md) | 3.8 Help |
| 3.9 | [app.md](docs/spec/app.md) | 3.9 Data health and Field profile |
| 3.13 | [app.md](docs/spec/app.md) | 3.13 Transforms and corrections (`calc` / `tweak`) |
| 3.14 | [app.md](docs/spec/app.md) | 3.14 Menus and window |
| 3.11 | [online-and-enrichment.md](docs/spec/online-and-enrichment.md) | 3.11 Online features and the map background |
| 3.12 | [online-and-enrichment.md](docs/spec/online-and-enrichment.md) | 3.12 Enrichment |
| 3.12.1 | [online-and-enrichment.md](docs/spec/online-and-enrichment.md) | 3.12.1 The enrichments |
| 3.12.2 | [online-and-enrichment.md](docs/spec/online-and-enrichment.md) | 3.12.2 Two different ways of filling blanks |
| 3.12.3 | [online-and-enrichment.md](docs/spec/online-and-enrichment.md) | 3.12.3 Modeling-time context (step 5) |
| 5 | [platform.md](docs/spec/platform.md) | 5. Hardware targets |
| 6 | [platform.md](docs/spec/platform.md) | 6. Architecture |
| 6.1 | [platform.md](docs/spec/platform.md) | 6.1 Cross-platform: Linux now, macOS possible |
| 6.2 | [platform.md](docs/spec/platform.md) | 6.2 Licensing |
| 6.3 | [platform.md](docs/spec/platform.md) | 6.3 Engine facts that shape the design |
| 6.4 | [platform.md](docs/spec/platform.md) | 6.4 Staleness and re-runs |
| 6.5 | [platform.md](docs/spec/platform.md) | 6.5 Frontend and build stack |
| 6.6 | [platform.md](docs/spec/platform.md) | 6.6 Wording: the catalog and live editing |
| 7 | [engine.md](docs/spec/engine.md) | 7. Engine: OpenAVMKit changes |
| A | [engine.md](docs/spec/engine.md) | A. Needed for M1 ("Check my values") |
| B | [engine.md](docs/spec/engine.md) | B. Needed for M2 (enrichment, model groups, sales) |
| C | [engine.md](docs/spec/engine.md) | C. Needed for M3 (model values) and later |
| D | [engine.md](docs/spec/engine.md) | D. Documentation fixes found during review |
| 8 | [roadmap.md](docs/spec/roadmap.md) | 8. Milestones |
| 9 | [roadmap.md](docs/spec/roadmap.md) | 9. Out of scope for v1 |
| 10 | [roadmap.md](docs/spec/roadmap.md) | 10. Open items |

Decisions D1 to D47 are in [decisions.md](docs/spec/decisions.md).
