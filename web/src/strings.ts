/** Every user-facing string lives here (SPEC D13), so a missing key is a type error. */
export const t = {
  appName: { strong: "OAK", light: "box" },
  appTitle: "OAK box",
  tagline: "OpenAVMKit in a box",

  home: {
    projectsTitle: "Projects",
    noProjects: "No projects yet.",
    newProject: "New project",
    open: "Open",
    showInFolder: "Show in folder",
    delete: "Delete",
    taxYear: (year: number) => `Tax year ${year}`,
    storageTitle: "Where projects are kept",
    storageNote: "New projects go here. Existing projects stay where they are.",
    change: "Change…",
    useDefault: "Use the default",
    save: "Save",
    cancel: "Cancel",
    folderLabel: "Folder",
  },

  newProject: {
    title: "New project",
    intro: "Tell OAK box which jurisdiction and tax year this is. You'll add data files next.",
    name: "Project name",
    nameHelp: "Your name for it, e.g. Travis County 2026. It also names the project's folder.",
    country: "Country",
    state: "State",
    region: "State, province or region",
    jurisdiction: "Jurisdiction",
    jurisdictionHelp: "What your office calls itself, e.g. Travis County. It appears on reports.",
    taxYear: "Tax year",
    valuationDate: "Valuation date",
    valuationHelp:
      "Everything is valued as of this date. To check an existing roll, use that roll's valuation date.",
    units: "Units",
    imperial: "Imperial (square feet, acres)",
    metric: "Metric (square metres, hectares)",
    create: "Create project",
    cancel: "Cancel",
    where: (folder: string) => `It will be kept in ${folder}`,
  },

  inputFiles: {
    none: "No input files yet.",
    add: "Add a file",
    path: "File",
    pathHelp: "Paste the file's full path, or browse.",
    browse: "Browse…",
    check: "Check",
    cancel: "Cancel",
    format: (format: string, size: string) => `${format}, ${size}`,
    together: (names: string) => `These move or copy together: ${names}`,
    layer: "Layer",
    name: "Name",
    nameHelp: "What this file is called in OAK box and in settings.json (data.load).",
    newFilename: "New file name",
    newFilenameHelp: (taken: string) =>
      `The project already has a file called ${taken}. Give this one another name.`,
    already: "This file is already in the project folder, so it stays where it is.",
    how: "Bring it into the project by",
    copy: "Copying it (the original stays where it is)",
    move: "Moving it (it leaves its original folder)",
    addButton: "Add file",
    adding: (mode: "move" | "copy") => (mode === "move" ? "Moving…" : "Copying…"),
    file: (filename: string, layer: string | null) => (layer ? `${filename} (layer: ${layer})` : filename),
    missing: "Missing from the project folder",
  },

  deleteProject: {
    title: (name: string) => `Delete ${name}?`,
    body: (size: string, files: number) =>
      `Its folder (${size}, ${files.toLocaleString()} files) goes to the Recycle Bin. You can restore it from there.`,
    measuring: "Measuring the folder…",
    confirm: "Move to Recycle Bin",
    cancel: "Cancel",
  },

  tabs: {
    metadata: "Metadata",
    inputFiles: "Input files",
    later: "Not available yet",
  },

  metadata: {
    jurisdiction: "Jurisdiction",
    region: "Region",
    taxYear: "Tax year",
    valuationDate: "Valuation date",
    units: "Units",
    folder: "Project folder",
    showInFolder: "Show in folder",
  },

  project: {
    back: "Projects",
    taxYear: (year: number) => `Tax year ${year}`,
    loading: "Loading…",
  },
};
