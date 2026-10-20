import type { FileUse, StageId, StepId } from "./api/client";

const n = (x: number) => x.toLocaleString();
const pct = (x: number) => `${(x * 100).toFixed(x >= 0.995 || x < 0.005 ? 0 : 1)}%`;

/** Every user-facing string lives here (SPEC D13), so a missing key is a type error. */
export const t = {
  appName: { strong: "OAK", light: "box" },
  appTitle: "OAK box",
  tagline: "OpenAVMKit in a box",
  n,
  pct,

  home: {
    projectsTitle: "Projects",
    noProjects: "No projects yet. Start a new one, or try the sample county.",
    open: "Open",
    taxYear: (year: number | null) => (year ? `Tax year ${year}` : "Tax year not set"),
    progress: (done: number, total: number) => `${done} of ${total} done`,
    newProject: "New project",
    newProjectName: "Name, e.g. the county or city",
    create: "Create",
    sampleTitle: "Sample county",
    sampleNotice: "Downloads about 7 MB of public data from OpenAVMKit. Nothing is uploaded.",
    sampleButton: "Download and open",
    sampleDownloading: "Downloading…",
  },

  project: {
    back: "Projects",
    taxYear: (year: number | null) => (year ? `Tax year ${year}` : ""),
    setUp: "Set up",
    run: "Run",
    working: "Working…",
    walkthrough: "Sample walkthrough",
  },

  stages: {
    basics: { title: "Basics", what: "Where this is, and the date everything is valued as of." },
    files: { title: "Your files", what: "Add the files you have, and say what each one is." },
    stitch: {
      title: "Stitch",
      what: "How your files fit together into one table of parcels and one of sales.",
    },
    columns: { title: "Columns", what: "Match your columns to OpenAVMKit's standard fields." },
    sales_basics: { title: "Sales basics", what: "Which sales are valid, and when each sale happened." },
  } satisfies Record<StageId, { title: string; what: string }>,

  steps: {
    bring_in_data: { title: "Bring in data", what: "Stitch the files and load them into OpenAVMKit." },
    model_groups: { title: "Model groups", what: "Properties valued together. This version uses one group." },
    check_sales: {
      title: "Check sales",
      what: "Keeps arm's-length sales, adjusts for market trend, flags outliers.",
    },
    check_values: { title: "Check my values", what: "Your current values against recent sales." },
  } satisfies Record<StepId, { title: string; what: string }>,

  stageState: { todo: "To do", done: "Done", stale: "Out of date" },
  state: { not_run: "Not run", running: "Running", done: "Done", failed: "Failed", stale: "Out of date" },

  frame: {
    decide: "Decide",
    check: "Check",
    receipt: "What happened",
    looksRight: "Looks right",
    confirmed: "Confirmed",
    runCheck: "Check",
    checkAgain: "Check again",
    checkOutdated: "Your decisions changed since this check. Check again before confirming.",
    noCheckYet: "Nothing checked yet.",
    underTheHood: "Under the hood",
    underTheHoodNote: "What this stage writes for OpenAVMKit. You never need to edit it.",
    stop: "Stop",
    stopping: "Stopping…",
    technicalDetails: "Technical details",
    staleBecause: (reason: string) => `Out of date: ${reason}`,
    saved: "Saved",
  },

  basics: {
    name: "Name",
    state: "State",
    stateHelp: "Two letters, e.g. TX",
    taxYear: "Tax year",
    units: "Units",
    imperial: "Square feet and acres",
    metric: "Square metres and hectares",
    valuationDate: "Valuation date",
    valuationHelp: "Everything is valued as of this date. To check an existing roll, use that roll's date.",
    slug: (slug: string) => `OpenAVMKit locality: ${slug}`,
  },

  files: {
    empty: "No files yet.",
    add: "Add a file",
    pathLabel: "File or folder",
    pathHelp: "Paste the full path, or browse.",
    browse: "Browse…",
    browseFolder: "Folder…",
    lookInside: "Look inside",
    cancel: "Cancel",
    addThis: "Add this file",
    addChosen: (k: number) => `Add ${k} file${k === 1 ? "" : "s"}`,
    remove: "Remove",
    whatIsIt: "What's in it?",
    idColumn: "Parcel ID column",
    chooseId: "Choose a column",
    preview: (rows: number | null) => (rows === null ? "First rows" : `First rows of ${n(rows)}`),
    exportTitle: (name: string) => `${name}: choose the files to use`,
    exportNote: "Files ticked are the ones modeling uses. Owner names and mailing addresses are left out.",
    records: (k: number) => `${n(k)} records`,
    notInLayout: (names: string) => `Also in the zip, not read: ${names}`,
    uses: {
      parcel_map: "Parcel map",
      parcels: "Parcel details",
      sales: "Sales",
      points: "Points (latitude and longitude)",
      map_layer: "Map layer",
    } satisfies Record<FileUse, string>,
    usesLater: "Points and map layers are attached in a later version.",
    columnsKept: (k: number, total: number) => `${n(k)} of ${n(total)} columns kept`,
    keepRows: (col: string, values: string) => `Only rows where ${col} is ${values}`,
    imported: "Imported",
    notImported: "Not imported yet",
    profile: (rows: number, ids: number) => `${n(rows)} rows, ${n(ids)} parcel IDs`,
    severalRows: (rows: number, ids: number) =>
      `${n(rows)} rows for ${n(ids)} IDs: several rows per parcel. Stitch decides how they become one.`,
    blankIds: (k: number) => `${n(k)} rows have no ID`,
    noMap: "One file must be the parcel map.",
    checkWhat: "Check imports each file into the project and measures it. Your originals are never changed.",
  },

  stitch: {
    spine: "Everything attaches to",
    noMap: "Add a parcel map in Your files first.",
    mergePolygons: "Merge polygons that share an ID into one shape",
    idFixes: "Fix IDs before matching",
    fixes: {
      trim: "Remove spaces at the ends",
      strip_leading_zeros: "Remove leading zeros",
      remove_non_alnum: "Remove dashes, dots and spaces",
      upper: "Use capital letters",
      pad_zeros: "Pad with zeros",
    } satisfies Record<IdFixOpKey, string>,
    severalRows: "Several rows per parcel",
    keepFirst: (by: string) => `Keep the row with the ${by}`,
    keepFileOrder: "Keep the first row in the file",
    aggregations: (k: number) => `${k} column${k === 1 ? "" : "s"} combined: `,
    agg: { first: "first", sum: "sum", max: "largest", min: "smallest", count: "count" },
    highest: (col: string) => `highest ${col}`,
    lowest: (col: string) => `lowest ${col}`,
    checkWhat: "Check measures how the files match, without changing anything.",
    map: "Parcel map",
    mapLine: (rows: number, out: number) => `${n(rows)} polygons → ${n(out)} parcels`,
    blankDropped: (k: number) => `${n(k)} with no ID left out`,
    merged: (k: number) => `${n(k)} extra polygons merged into their parcel`,
    filtered: (k: number, desc: string) => `${n(k)} rows left out: ${desc}`,
    matchedOf: (m: number, total: number) =>
      `${n(m)} of ${n(total)} IDs found on the map (${pct(total ? m / total : 0)})`,
    onlyHere: (k: number) => `${n(k)} not on the map`,
    onlyOnMap: (k: number) => `${n(k)} map parcels have no row here`,
    collapsed: (rows: number, out: number) => `${n(rows)} rows became ${n(out)} parcels`,
    examples: "Examples",
    suggestion: (desc: string, gain: number) => `Try: ${desc}. ${n(gain)} more would match.`,
    applySuggestion: "Apply to all files",
    breakdownTitle: (col: string) => `The ones not on the map, by ${col}`,
    breakdownRow: (value: string, count: number, un: number, m: number) =>
      `${value}: ${n(count)} (${pct(un)} of those not on the map; ${pct(m)} of those that are)`,
    total: (parcels: number, sales: number, unmatched: number) =>
      `${n(parcels)} parcels and ${n(sales)} sales records` +
      (unmatched ? `; ${n(unmatched)} sales records left out because their parcel isn't on the map` : ""),
    mapOnly: (k: number) => `${n(k)} map parcels have no details in any parcel table, so they are left out`,
    columnsTitle: (k: number) => `${n(k)} columns in the stitched parcel table`,
  },

  later: {
    title: "Arrives in the next version",
    body: "This screen comes in the next version of OAK box. For now, only the sample can continue; its answers are below.",
  },

  receipt: {
    predicted: "Stitched",
    engine: "OpenAVMKit loaded",
    parcels: "Parcels",
    sales: "Sales",
    salesNote:
      "OpenAVMKit removes sales your office codes mark invalid, so it loads fewer sales than were stitched.",
  },

  step: {
    run: "Run",
    runAgain: "Run again",
    cancel: "Stop",
    stopping: "Stopping…",
    working: "Working…",
    needsSetup: "Finish setting up first",
    needsEarlier: "Run the step above first",
    showDetails: "Technical details",
  },

  results: {
    title: "Current values vs. sales",
    window: (start: string, end: string, k: number) => `${n(k)} sales, ${start} to ${end}`,
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

type IdFixOpKey = "trim" | "strip_leading_zeros" | "remove_non_alnum" | "upper" | "pad_zeros";
