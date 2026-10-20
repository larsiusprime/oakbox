import type { StepId } from "./api/client";

/** Every user-facing string lives here (SPEC D13), so a missing key is a type error. */
export const t = {
  appName: { strong: "OAK", light: "box" },
  appTitle: "OAK box",
  tagline: "OpenAVMKit in a box",

  home: {
    projectsTitle: "Projects",
    noProjects: "No projects yet. Start with the sample county.",
    open: "Open",
    taxYear: (year: number) => `Tax year ${year}`,
    stepsDone: (done: number, total: number) => `${done} of ${total} steps done`,
    sampleTitle: "Sample county",
    sampleNotice: "Downloads about 7 MB of public data from OpenAVMKit. Nothing is uploaded.",
    sampleButton: "Download and open",
    sampleDownloading: "Downloading…",
  },

  project: {
    back: "Projects",
    taxYear: (year: number) => `Tax year ${year}`,
    stepsTitle: "Steps",
    run: "Run",
    runAgain: "Run again",
    cancel: "Stop",
    stopping: "Stopping…",
    working: "Working…",
    needsEarlier: "Run the step above first",
    showDetails: "Technical details",
  },

  steps: {
    bring_in_data: { title: "Bring in data", what: "Parcel map, parcel details and sales, joined together." },
    model_groups: { title: "Model groups", what: "Properties valued together. This sample uses one group." },
    check_sales: {
      title: "Check sales",
      what: "Keeps arm's-length sales, adjusts for market trend, flags outliers.",
    },
    check_values: { title: "Check my values", what: "Your current values against recent sales." },
  } satisfies Record<StepId, { title: string; what: string }>,

  state: {
    not_run: "Not run",
    running: "Running",
    done: "Done",
    failed: "Failed",
    stale: "Out of date",
  },

  results: {
    title: "Current values vs. sales",
    window: (start: string, end: string, n: number) => `${n.toLocaleString()} sales, ${start} to ${end}`,
    group: "Group",
    overall: "Whole jurisdiction",
    sales: "Sales",
    medianRatio: "Median ratio",
    cod: "COD",
    prd: "PRD",
    prb: "PRB",
    vei: "VEI",
    target: "Target",
    meets: "Meets",
    outside: "Outside",
    notEnough: "Too few sales",
    targetsNote: "IAAO default targets. Small numbers are 90% confidence ranges.",
    targets: {
      medianRatio: "0.90 to 1.10",
      cod: "15 or less",
      prd: "0.98 to 1.03",
      prb: "−0.05 to 0.05",
      vei: "none yet",
    },
    explain: {
      medianRatio: "Value ÷ sale price, middle of all sales. 1.00 means values match sales on average.",
      cod: "How spread out the ratios are. Lower means more uniform values.",
      prd: "Above 1.03 suggests cheaper properties are over-valued relative to expensive ones.",
      prb: "Fairness across price levels. Negative means cheaper properties carry relatively higher values.",
      vei: "Vertical equity indicator from the IAAO draft standard. Near zero is fair.",
    },
  },
};
