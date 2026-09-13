import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../api/client";
import { getJob, startAnalysis } from "../api/endpoints";
import type { Job } from "../api/types";

export function useAnalysisJob(onDone: (job: Job) => void) {
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<number | null>(null);
  const doneCb = useRef(onDone);
  doneCb.current = onDone;

  const stop = () => {
    if (timer.current) window.clearInterval(timer.current);
    timer.current = null;
  };

  useEffect(() => stop, []);

  const run = useCallback(async (aoiId: string) => {
    stop();
    setError(null);
    try {
      const started = await startAnalysis(aoiId);
      setJob(started);
      timer.current = window.setInterval(async () => {
        try {
          const s = await getJob(started.job_id);
          setJob(s);
          if (s.status === "done" || s.status === "failed") {
            stop();
            if (s.status === "done") doneCb.current(s);
            else setError(s.error ?? "The pipeline failed.");
          }
        } catch (e) {
          stop();
          setError(e instanceof Error ? e.message : "Lost contact with the job.");
        }
      }, 1500);
    } catch (e) {
      const msg =
        e instanceof ApiError && e.code === "JOB_ALREADY_RUNNING"
          ? "An analysis is already running for this user."
          : e instanceof ApiError && e.code === "FORBIDDEN_ROLE"
            ? "This role cannot start an analysis. Sign in as analyst or authority."
            : e instanceof Error
              ? e.message
              : "Could not start the analysis.";
      setError(msg);
    }
  }, []);

  const reset = useCallback(() => {
    stop();
    setJob(null);
    setError(null);
  }, []);

  return { job, error, run, reset };
}
