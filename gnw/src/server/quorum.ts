import { randomUUID } from "node:crypto";
import { canonicalize, sha256 } from "./security.js";

export type QuorumRole = "coder_proposer" | "security_auditor" | "chief_justice";

export interface QuorumProposal {
  proposalId: string;
  taskId: number;
  actorUserId: number;
  tool: string;
  operation: string;
  parameters: Record<string, unknown>;
  justification: string;
  isDestructive?: boolean;
  timestamp: number;
  digest: string;
}

export interface QuorumVote {
  proposalId: string;
  role: QuorumRole;
  agentId: string;
  approve: boolean;
  veto?: boolean;
  reason: string;
  signature: string;
  timestamp: number;
}

export type QuorumStatus = "APPROVED" | "REJECTED" | "VETOED" | "PENDING";

export interface QuorumResult {
  proposalId: string;
  status: QuorumStatus;
  approvals: number;
  totalVotes: number;
  consensusRatio: number;
  requiredConsensusRatio: number;
  vetoAgent?: string;
  vetoReason?: string;
  votes: QuorumVote[];
  consensusDigest: string;
  adjudicatedAt: number;
}

/** Dangerous commands and patterns prohibited unless explicitly audited and allowed */
const FORBIDDEN_SECURITY_PATTERNS = [
  /rm\s+(-rf|-fr|--force\s+-r|-r\s+--force)\s+[/~]/i,
  /mkfs/i,
  /dd\s+if=.*of=\/dev/i,
  /:(){ :\|:& };:/, // Fork bomb
  />\s*\/etc\/(passwd|shadow|hosts)/i,
  /curl\s+.*\|\s*(bash|sh|zsh)/i,
  /wget\s+.*\|\s*(bash|sh|zsh)/i,
  /process\.env\.(SESSION_SECRET|DATABASE_URL|LLM_API_KEY)/i,
  /eval\(|Function\(/i,
  /DROP\s+TABLE|DROP\s+DATABASE|TRUNCATE/i,
];

export function computeProposalDigest(proposal: Omit<QuorumProposal, "digest">): string {
  return sha256(canonicalize({
    proposalId: proposal.proposalId,
    taskId: proposal.taskId,
    actorUserId: proposal.actorUserId,
    tool: proposal.tool,
    operation: proposal.operation,
    parameters: proposal.parameters,
    justification: proposal.justification,
    isDestructive: Boolean(proposal.isDestructive),
    timestamp: proposal.timestamp,
  }));
}

export function computeVoteSignature(proposalDigest: string, vote: Omit<QuorumVote, "signature">): string {
  return sha256(canonicalize({
    proposalDigest,
    proposalId: vote.proposalId,
    role: vote.role,
    agentId: vote.agentId,
    approve: vote.approve,
    veto: Boolean(vote.veto),
    reason: vote.reason,
    timestamp: vote.timestamp,
  }));
}

export class MultiAgentQuorumEngine {
  private proposals = new Map<string, QuorumProposal>();
  private votes = new Map<string, Map<QuorumRole, QuorumVote>>();
  private results = new Map<string, QuorumResult>();

  constructor(public readonly requiredConsensusRatio = 0.66) {}

  /**
   * Registers a new high-risk action proposal from the proposing agent.
   */
  createProposal(input: {
    taskId: number;
    actorUserId: number;
    tool: string;
    operation: string;
    parameters: Record<string, unknown>;
    justification: string;
    isDestructive?: boolean;
    proposalId?: string;
  }): QuorumProposal {
    const proposalId = input.proposalId ?? `prop-${input.taskId}-${randomUUID().slice(0, 8)}`;
    const timestamp = Date.now();
    const raw = {
      proposalId,
      taskId: input.taskId,
      actorUserId: input.actorUserId,
      tool: input.tool,
      operation: input.operation,
      parameters: input.parameters,
      justification: input.justification,
      isDestructive: input.isDestructive,
      timestamp,
    };
    const digest = computeProposalDigest(raw);
    const proposal: QuorumProposal = { ...raw, digest };

    this.proposals.set(proposalId, proposal);
    this.votes.set(proposalId, new Map());
    return proposal;
  }

  /**
   * Casts a cryptographic vote by a specialized judicial agent.
   */
  submitVote(voteInput: Omit<QuorumVote, "signature">): QuorumVote {
    const proposal = this.proposals.get(voteInput.proposalId);
    if (!proposal) {
      throw new Error(`Quorum proposal '${voteInput.proposalId}' not found.`);
    }

    const signature = computeVoteSignature(proposal.digest, voteInput);
    const vote: QuorumVote = { ...voteInput, signature };

    const proposalVotes = this.votes.get(voteInput.proposalId)!;
    proposalVotes.set(voteInput.role, vote);
    return vote;
  }

  /**
   * Automated Security Auditor Agent analysis:
   * Inspects parameters and command payloads against high-risk security patterns.
   */
  auditSecurity(proposalId: string, agentId = "sec-auditor-v4"): QuorumVote {
    const proposal = this.proposals.get(proposalId);
    if (!proposal) {
      throw new Error(`Quorum proposal '${proposalId}' not found.`);
    }

    const serializedParams = JSON.stringify(proposal.parameters);
    const violations: string[] = [];

    for (const pattern of FORBIDDEN_SECURITY_PATTERNS) {
      if (pattern.test(serializedParams) || pattern.test(proposal.justification)) {
        violations.push(pattern.source);
      }
    }

    if (violations.length > 0) {
      return this.submitVote({
        proposalId,
        role: "security_auditor",
        agentId,
        approve: false,
        veto: true,
        reason: `VETO: Security audit detected prohibited high-risk pattern(s): ${violations.join(", ")}`,
        timestamp: Date.now(),
      });
    }

    return this.submitVote({
      proposalId,
      role: "security_auditor",
      agentId,
      approve: true,
      veto: false,
      reason: "Security audit passed: no prohibited patterns or unauthorized sandbox escapes detected.",
      timestamp: Date.now(),
    });
  }

  /**
   * Automated Chief Justice Agent analysis:
   * Evaluates constitutional alignment and task purpose before voting.
   */
  adjudicateChiefJustice(proposalId: string, agentId = "chief-justice-v4"): QuorumVote {
    const proposal = this.proposals.get(proposalId);
    if (!proposal) {
      throw new Error(`Quorum proposal '${proposalId}' not found.`);
    }

    // Chief Justice requires clear justification and valid task association
    if (!proposal.justification || proposal.justification.trim().length < 10) {
      return this.submitVote({
        proposalId,
        role: "chief_justice",
        agentId,
        approve: false,
        reason: "Chief Justice rejection: Insufficient justification provided for high-risk operation.",
        timestamp: Date.now(),
      });
    }

    return this.submitVote({
      proposalId,
      role: "chief_justice",
      agentId,
      approve: true,
      reason: "Chief Justice approval: Operation justified under governed task authority.",
      timestamp: Date.now(),
    });
  }

  /**
   * Evaluates the collective consensus of the quorum.
   * Requires >= 66.7% approval and zero auditor VETOs.
   */
  adjudicate(proposalId: string): QuorumResult {
    const proposal = this.proposals.get(proposalId);
    if (!proposal) {
      throw new Error(`Quorum proposal '${proposalId}' not found.`);
    }

    const votesMap = this.votes.get(proposalId) ?? new Map();
    const votesList = Array.from(votesMap.values());
    const totalVotes = votesList.length;

    // Check for explicit VETO first
    const vetoVote = votesList.find(v => v.veto === true || (!v.approve && v.role === "security_auditor"));
    if (vetoVote) {
      const result: QuorumResult = {
        proposalId,
        status: "VETOED",
        approvals: votesList.filter(v => v.approve).length,
        totalVotes,
        consensusRatio: totalVotes > 0 ? votesList.filter(v => v.approve).length / totalVotes : 0,
        requiredConsensusRatio: this.requiredConsensusRatio,
        vetoAgent: vetoVote.agentId,
        vetoReason: vetoVote.reason,
        votes: votesList,
        consensusDigest: sha256(`VETO:${proposal.digest}:${vetoVote.signature}`),
        adjudicatedAt: Date.now(),
      };
      this.results.set(proposalId, result);
      return result;
    }

    const approvals = votesList.filter(v => v.approve).length;
    const consensusRatio = totalVotes > 0 ? approvals / totalVotes : 0;
    const requiredRatio = proposal.isDestructive ? 1.0 : this.requiredConsensusRatio;
    const passed = totalVotes >= 3 && consensusRatio >= requiredRatio;

    const status: QuorumStatus = passed ? "APPROVED" : (totalVotes < 3 ? "PENDING" : "REJECTED");
    const consensusDigest = sha256(canonicalize({
      proposalDigest: proposal.digest,
      status,
      approvals,
      totalVotes,
      votes: votesList.map(v => v.signature),
    }));

    const result: QuorumResult = {
      proposalId,
      status,
      approvals,
      totalVotes,
      consensusRatio,
      requiredConsensusRatio: this.requiredConsensusRatio,
      votes: votesList,
      consensusDigest,
      adjudicatedAt: Date.now(),
    };

    this.results.set(proposalId, result);
    return result;
  }

  getProposal(proposalId: string): QuorumProposal | undefined {
    return this.proposals.get(proposalId);
  }

  getResult(proposalId: string): QuorumResult | undefined {
    return this.results.get(proposalId);
  }
}
