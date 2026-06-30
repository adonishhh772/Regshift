export function describeSystemIngestion(system: {
  connector: string;
  source_type: string;
  source_path: string | null;
  vendor: string;
}): { title: string; steps: string[] } {
  if (system.connector === "metadata_export") {
    return {
      title: "Metadata export ingestion",
      steps: [
        `Source folder: ${system.source_path ?? "not configured"}`,
        "Reads metadata-manifest.json plus export files (classes, objects, BAPIs, tables).",
        "Builds System → Package → Artifact/CodeFile nodes in the knowledge graph.",
        "Persisted to SQLite and Neo4j on ingest or API startup.",
      ],
    };
  }

  return {
    title: "Git repository ingestion",
    steps: [
      `Source repo: ${system.source_path ?? "not configured"}`,
      "Scans code files (.py, .ts, .tsx, .js, .json, …) under the repo root.",
      "Builds System → Package → CodeFile → Symbol (+ DocType artifacts for ERPNext).",
      "Persisted to SQLite and Neo4j on ingest or API startup.",
    ],
  };
}
