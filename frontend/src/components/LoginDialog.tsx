import { useState } from "react";
import { ApiError } from "../api/client";
import { login } from "../api/endpoints";
import type { LoginResponse } from "../api/types";

export function LoginDialog({ onSuccess }: { onSuccess: (r: LoginResponse) => void }) {
  const [username, setUsername] = useState("officer");
  const [password, setPassword] = useState("officer");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      onSuccess(await login(username, password));
    } catch (e) {
      const m =
        e instanceof ApiError && e.code === "INVALID_CREDENTIALS"
          ? "Incorrect username or password."
          : e instanceof Error
            ? e.message
            : "Login failed.";
      setErr(m);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="modal-back">
      <form className="modal" onSubmit={submit}>
        <h2>Bharat EarthShield</h2>
        <p className="sub">Satellite change detection and forward risk monitoring</p>

        <div className="field">
          <label htmlFor="u">Username</label>
          <input id="u" value={username} onChange={(e) => setUsername(e.target.value)} autoFocus />
        </div>
        <div className="field">
          <label htmlFor="p">Password</label>
          <input
            id="p"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>

        <p className="err">{err}</p>

        <button className="btn primary" style={{ width: "100%" }} disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>

        <p className="hint">viewer · analyst · authority</p>
      </form>
    </div>
  );
}
