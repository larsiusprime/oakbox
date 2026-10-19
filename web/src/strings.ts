import type { StepId } from "./api/client";

/** Every user-facing string lives here (SPEC D13), so a missing key is a type error. */
export const t = {
  appName: "Oakbox",
  tagline: "OpenAVMKit in a box",

  home: {
    projectsTitle: "My projects",
    noProjects: "No projects yet. Try the sample county below to see how Oakbox works.",
    open: "Open",
    taxYear: (year: number) => `Tax year ${year}`,
    stepsDone: (done: number, total: number) => `${done} of ${total} steps done`,
    sampleTitle: "Try a sample county",
    sampleIntro:
      "Download a real, public county and run every step on it. Nothing from your own office is used or sent anywhere.",
    sampleNotice: "This downloads about 7 MB of public data from OpenAVMKit's server. Nothing is uploaded.",
    sampleButton: "Download and open",
    sampleDownloading: "Downloading the sample county…",
    newProject: "New project from my own data",
    newProjectSoon: "Coming next: the step-by-step wizard for your own files.",
  },

  project: {
    back: "All projects",
    taxYear: (year: number) => `Tax year ${year}`,
    run: "Run",
    runAgain: "Run again",
    cancel: "Stop",
    stopping: "Stopping…",
    working: "Working…",
    needsEarlier: "Finish the step above first.",
    showDetails: "Show technical details",
  },

  steps: {
    bring_in_data: {
      title: "Bring in data",
      what: "Reads your parcel map, parcel details and sales, and joins them together.",
    },
    model_groups: {
      title: "Model groups",
      what: "Groups of properties that are valued together. For now this sample uses one group: all properties.",
    },
    check_sales: {
      title: "Check sales",
      what: "Keeps the sales that are fair market sales, adjusts for market trends, and flags suspicious ones.",
    },
    check_values: {
      title: "Check my values",
      what: "Compares your current values to recent sales: how accurate, how uniform, and how fair across price levels.",
    },
  } satisfies Record<StepId, { title: string; what: string }>,

  state: {
    not_run: "Not run yet",
    running: "Running",
    done: "Done",
    failed: "Problem",
    stale: "Needs re-run",
  },

  results: {
    title: "Results: how your current values compare to sales",
    window: (start: string, end: string) => `Sales from ${start} to ${end}.`,
    group: "Group",
    overall: "Whole jurisdiction",
    sales: "Sales",
    medianRatio: "Median ratio",
    cod: "COD",
    prd: "PRD",
    prb: "PRB",
    vei: "VEI",
    meets: "Meets target",
    outside: "Outside target",
    notEnough: "Not enough sales",
    targetsNote:
      "Targets shown are the IAAO defaults. The smaller numbers under each value are its 90% confidence range. Your state's standards may differ; adjustable targets are coming.",
    explain: {
      medianRatio:
        "Your value divided by the sale price, middle of all sales. 1.00 means values match sales on average. IAAO target: 0.90 to 1.10.",
      cod: "How spread out the ratios are. Lower means more uniform values. IAAO target: 15 or less for most property types.",
      prd: "Whether expensive and cheap properties are valued alike. Above 1.03 suggests cheaper homes are over-valued. IAAO target: 0.98 to 1.03.",
      prb: "Another measure of fairness across price levels. Near zero is fair. IAAO target: between -0.05 and 0.05.",
      vei: "The newest fairness measure (IAAO draft). Near zero is fair. Shown for reference; no target yet.",
    },
  },
};
