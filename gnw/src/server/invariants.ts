import { canonicalize, sha256 } from "./security.js";

export interface TrajectoryStep {
  stepIndex: number;
  taskId: number;
  tool: string;
  parametersHash: string;
  outputHash?: string;
  exitCode?: number | null;
  success: boolean;
  durationMs: number;
  timestamp: number;
  metadata?: Record<string, unknown>;
}

export interface ProposedAction {
  taskId: number;
  tool: string;
  parameters: Record<string, unknown>;
  timestamp?: number;
}

export interface InvariantViolation {
  code: string;
  message: string;
  severity: "CRITICAL" | "HIGH" | "MEDIUM";
  recoveryAdvice: string;
  repeatedCount?: number;
  tool?: string;
}

export interface InvariantCheckResult {
  allowed: boolean;
  violation?: InvariantViolation;
}

export interface InvariantLimits {
  maxConsecutiveIdenticalFailures: number;
  maxTotalIdenticalFailures: number;
  maxStepsPerTask: number;
  maxCallsInWindow5s: number;
  maxCallsInWindow30s: number;
  maxFileThrashCount: number;
}

const DEFAULT_LIMITS: InvariantLimits = {
  maxConsecutiveIdenticalFailures: 2,
  maxTotalIdenticalFailures: 3,
  maxStepsPerTask: 50,
  maxCallsInWindow5s: 10,
  maxCallsInWindow30s: 30,
  maxFileThrashCount: 4,
};

export function computeActionHash(parameters: Record<string, unknown>): string {
  return sha256(canonicalize(parameters));
}

export class TrajectoryInvariantEngine {
  private trajectories = new Map<number, TrajectoryStep[]>();
  private fileWrites = new Map<number, Array<{ path: string; timestamp: number }>>();

  constructor(public readonly limits: InvariantLimits = DEFAULT_LIMITS) {}

  /**
   * Records an executed step into the task trajectory.
   */
  recordStep(
    step: Omit<TrajectoryStep, "stepIndex" | "parametersHash"> & {
      stepIndex?: number;
      parametersHash?: string;
      parameters?: Record<string, unknown>;
    }
  ): TrajectoryStep {
    const list = this.trajectories.get(step.taskId) ?? [];
    const stepIndex = step.stepIndex ?? list.length + 1;
    const parametersHash = step.parametersHash ?? (step.parameters ? computeActionHash(step.parameters) : "");
    const fullStep: TrajectoryStep = { ...step, parametersHash, stepIndex };
    list.push(fullStep);
    this.trajectories.set(step.taskId, list);

    // Track file writes for thrashing detection
    if (step.metadata?.filePath && typeof step.metadata.filePath === "string") {
      const writes = this.fileWrites.get(step.taskId) ?? [];
      writes.push({ path: step.metadata.filePath, timestamp: step.timestamp });
      this.fileWrites.set(step.taskId, writes);
    }

    return fullStep;
  }

  /**
   * Evaluates the proposed action against trajectory invariants BEFORE it runs.
   * Returns allowed: false with actionable invariant violation if a safety invariant trips.
   */
  checkInvariants(action: ProposedAction): InvariantCheckResult {
    const now = action.timestamp ?? Date.now();
    const history = this.trajectories.get(action.taskId) ?? [];
    const paramsHash = sha256(canonicalize(action.parameters));

    // Invariant 1: Total Steps Safeguard
    if (history.length >= this.limits.maxStepsPerTask) {
      return {
        allowed: false,
        violation: {
          code: "TASK_MAX_STEPS_EXCEEDED",
          message: `Task ${action.taskId} reached maximum permitted execution steps (${this.limits.maxStepsPerTask}).`,
          severity: "CRITICAL",
          recoveryAdvice: "Task halted to prevent runaway execution. Review agent plan or raise quota.",
          tool: action.tool,
        },
      };
    }

    // Invariant 2: Runaway Velocity Rate Limiting
    const callsIn5s = history.filter(s => now - s.timestamp <= 5000).length;
    if (callsIn5s >= this.limits.maxCallsInWindow5s) {
      return {
        allowed: false,
        violation: {
          code: "RATE_LIMIT_EXCEEDED: agent_runaway_velocity",
          message: `Agent velocity exceeded limit (${callsIn5s} calls in last 5s).`,
          severity: "HIGH",
          recoveryAdvice: "Agent is triggering rapid bursts of tool calls. Throttle execution rate.",
          tool: action.tool,
        },
      };
    }

    const callsIn30s = history.filter(s => now - s.timestamp <= 30000).length;
    if (callsIn30s >= this.limits.maxCallsInWindow30s) {
      return {
        allowed: false,
        violation: {
          code: "RATE_LIMIT_EXCEEDED: agent_runaway_velocity_30s",
          message: `Agent velocity exceeded limit (${callsIn30s} calls in last 30s).`,
          severity: "HIGH",
          recoveryAdvice: "Cool down execution to avoid provider denial or infinite looping.",
          tool: action.tool,
        },
      };
    }

    // Invariant 3: Repeated Identical Failure Circuit Breaker
    const identicalFailures = history.filter(
      s => s.tool === action.tool && s.parametersHash === paramsHash && !s.success
    );
    if (identicalFailures.length >= this.limits.maxTotalIdenticalFailures) {
      return {
        allowed: false,
        violation: {
          code: "CIRCUIT_BREAKER_TRIPPED: repeated_identical_failure",
          message: `Tool '${action.tool}' with identical arguments failed ${identicalFailures.length} times.`,
          severity: "CRITICAL",
          recoveryAdvice: "Agent must change strategy, fix arguments, or request human intervention. Retrying the identical failing call is prohibited.",
          repeatedCount: identicalFailures.length,
          tool: action.tool,
        },
      };
    }

    // Consecutive identical failure check
    let consecutiveIdenticalFails = 0;
    for (let i = history.length - 1; i >= 0; i--) {
      const s = history[i];
      if (s.tool === action.tool && s.parametersHash === paramsHash && !s.success) {
        consecutiveIdenticalFails++;
      } else {
        break;
      }
    }
    if (consecutiveIdenticalFails >= this.limits.maxConsecutiveIdenticalFailures) {
      return {
        allowed: false,
        violation: {
          code: "CIRCUIT_BREAKER_TRIPPED: consecutive_identical_failure",
          message: `Tool '${action.tool}' failed consecutively ${consecutiveIdenticalFails} times with identical arguments.`,
          severity: "CRITICAL",
          recoveryAdvice: "Repeated immediate failing retry detected. Modify plan or parameters before retrying.",
          repeatedCount: consecutiveIdenticalFails,
          tool: action.tool,
        },
      };
    }

    // Invariant 4: Ping-Pong Oscillation Detection (e.g. A -> B -> A -> B -> A)
    if (history.length >= 4) {
      const lastFour = history.slice(-4);
      const t0 = lastFour[0].tool;
      const t1 = lastFour[1].tool;
      const t2 = lastFour[2].tool;
      const t3 = lastFour[3].tool;

      if (t0 === t2 && t1 === t3 && t0 !== t1 && action.tool === t0) {
        return {
          allowed: false,
          violation: {
            code: "CIRCUIT_BREAKER_TRIPPED: tool_oscillation_detected",
            message: `Ping-pong oscillation detected alternating between '${t0}' and '${t1}'.`,
            severity: "HIGH",
            recoveryAdvice: "Agent is caught in a two-tool oscillation loop. Break the loop and synthesize a new approach.",
            tool: action.tool,
          },
        };
      }
    }

    // Invariant 5: File Thrashing Detection
    const filePath = typeof action.parameters?.path === "string" ? action.parameters.path : (typeof action.parameters?.file === "string" ? action.parameters.file : undefined);
    if (filePath) {
      const writes = this.fileWrites.get(action.taskId) ?? [];
      const recentWrites = writes.filter(w => w.path === filePath && now - w.timestamp <= 60000);
      if (recentWrites.length >= this.limits.maxFileThrashCount) {
        return {
          allowed: false,
          violation: {
            code: "INVARIANT_VIOLATION: file_thrashing_detected",
            message: `File '${filePath}' modified ${recentWrites.length} times within 60 seconds.`,
            severity: "HIGH",
            recoveryAdvice: "File thrashing detected. Validate the entire file state or run tests before further edits.",
            tool: action.tool,
          },
        };
      }
    }

    return { allowed: true };
  }

  getTrajectory(taskId: number): TrajectoryStep[] {
    return this.trajectories.get(taskId) ?? [];
  }

  reset(taskId: number) {
    this.trajectories.delete(taskId);
    this.fileWrites.delete(taskId);
  }
}
