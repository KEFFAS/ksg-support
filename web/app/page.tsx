"use client";

import { useEffect, useState } from "react";

export default function Home() {
  const API = process.env.NEXT_PUBLIC_API_BASE_URL || "";
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState<string>("");

  useEffect(() => {
    if (!API) {
      setErr("Missing NEXT_PUBLIC_API_BASE_URL. Check .env.local and restart dev server.");
      return;
    }
    fetch(`${API}/health`)
      .then((r) => r.json())
      .then(setData)
      .catch((e) => setErr(String(e)));
  }, [API]);

  return (
    <main style={{ maxWidth: 900, margin: "40px auto", fontFamily: "system-ui", padding: 16 }}>
      <h1>KSG Support (Fresh Frontend)</h1>
      <p><b>Backend:</b> {API || "(not set)"}</p>

      <h3>Health check</h3>
      {err && <pre style={{ color: "crimson" }}>{err}</pre>}
      {data ? <pre>{JSON.stringify(data, null, 2)}</pre> : <p>Loading…</p>}
    </main>
  );
}
