import { useState, useRef, useCallback } from "react";
import { CLOUD_FUNCTION_URL } from "@/lib/api";
import type { PendingCreateWorkflow, PendingWorkflowAction, PendingEdit } from "@/lib/types";
import type { Workflow } from "@/app/components/WorkflowCanvas";

export function useWorkflows() {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [activeWorkflow, setActiveWorkflow] = useState<{ id: string; name: string; description: string; detail: string } | null>(null);

  const [_pendingDeleteWorkflow, _setPendingDeleteWorkflow] = useState<string | null>(null);
  const pendingDeleteWorkflowRef = useRef<string | null>(null);
  const setPendingDeleteWorkflow = (v: string | null) => { pendingDeleteWorkflowRef.current = v; _setPendingDeleteWorkflow(v); };

  const [pendingCreateWorkflow, _setPendingCreateWorkflow] = useState<PendingCreateWorkflow>(null);
  const pendingCreateWorkflowRef = useRef<PendingCreateWorkflow>(null);
  const setPendingCreateWorkflow = (v: PendingCreateWorkflow) => { pendingCreateWorkflowRef.current = v; _setPendingCreateWorkflow(v); };

  const [pendingWorkflowAction, _setPendingWorkflowAction] = useState<PendingWorkflowAction>(null);
  const pendingWorkflowActionRef = useRef<PendingWorkflowAction>(null);
  const setPendingWorkflowAction = (v: PendingWorkflowAction) => { pendingWorkflowActionRef.current = v; _setPendingWorkflowAction(v); };

  const [pendingEditWorkflow, _setPendingEditWorkflow] = useState<PendingEdit>(null);
  const pendingEditWorkflowRef = useRef<PendingEdit>(null);
  const setPendingEditWorkflow = (v: PendingEdit) => { pendingEditWorkflowRef.current = v; _setPendingEditWorkflow(v); };

  const fetchWorkflows = useCallback(async () => {
    try {
      const res = await fetch(`${CLOUD_FUNCTION_URL}/list_workflows`);
      if (res.ok) {
        const data = await res.json();
        setWorkflows(data.workflows || []);
      }
    } catch { /* silent */ }
  }, []);

  return {
    workflows, setWorkflows, fetchWorkflows,
    activeWorkflow, setActiveWorkflow,
    pendingDeleteWorkflow: _pendingDeleteWorkflow,
    pendingDeleteWorkflowRef, setPendingDeleteWorkflow,
    pendingCreateWorkflow, pendingCreateWorkflowRef, setPendingCreateWorkflow,
    pendingWorkflowAction, pendingWorkflowActionRef, setPendingWorkflowAction,
    pendingEditWorkflow, pendingEditWorkflowRef, setPendingEditWorkflow,
  };
}
