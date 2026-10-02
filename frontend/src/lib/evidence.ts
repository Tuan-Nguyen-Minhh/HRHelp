import type { AnswerView, CaseHandoff, CitationView, EvidenceItem, EvidenceKind } from "@/types/api";

function kindFromPolicy(policyType: string | null, layer: string): EvidenceKind {
  if (layer === "inspection_risk") return "ADMINISTRATIVE_PENALTY";
  if (layer === "precedent" || policyType === "PRECEDENT") return "PRECEDENT";
  if (layer === "internal_rule" || policyType === "INTERNAL_RULE") return "INTERNAL_RULE";
  if (policyType === "LAW") return "LAW";
  if (policyType === "DECREE" || policyType === "CIRCULAR") return "DECREE";
  if (layer === "legal_basis") return "DECREE";
  return "OTHER";
}

function fromCitation(item: CitationView, query: string | null, caseCode: string | null): EvidenceItem {
  return {
    id: item.citation_id,
    chunkId: item.chunk_id,
    kind: kindFromPolicy(item.policy_type, item.layer),
    policyType: item.policy_type,
    policyCode: item.policy_code,
    policyName: item.policy_name,
    article: item.article,
    clause: item.clause,
    point: item.point,
    content: item.quote,
    retrievedBecause: query,
    caseCode,
  };
}

/**
 * Evidence rows come from the answer layers the API already separated.
 * A handoff passage only fills in the longer chunk text for the same id.
 * Passage policy types are not reclassified here.
 */
export function evidenceItems(answer: AnswerView | null, handoff: CaseHandoff | null, caseCode: string | null): EvidenceItem[] {
  if (!answer) return itemsFromHandoff(handoff, caseCode);
  const query = handoff?.query?.trim() || null;
  const fullText = new Map((handoff?.passages ?? []).map((passage) => [passage.chunk_id, passage.content]));
  const citations = [
    ...answer.legal_basis,
    ...answer.internal_rule,
    ...answer.precedent,
    ...answer.inspection_risk,
  ];
  return citations.map((item) => {
    const row = fromCitation(item, query, caseCode);
    const longer = item.chunk_id ? fullText.get(item.chunk_id) : undefined;
    if (longer && longer.length > row.content.length) row.content = longer;
    return row;
  });
}

function itemsFromHandoff(handoff: CaseHandoff | null, caseCode: string | null): EvidenceItem[] {
  if (!handoff) return [];
  const query = handoff.query?.trim() || null;
  return handoff.passages.map((passage) => ({
    id: passage.chunk_id,
    chunkId: passage.chunk_id,
    kind: kindFromPolicy(passage.policy_type, ""),
    policyType: passage.policy_type,
    policyCode: passage.policy_code,
    policyName: passage.policy_name,
    article: passage.article,
    clause: passage.clause,
    point: passage.point,
    content: passage.content,
    retrievedBecause: query,
    caseCode,
  }));
}

export function countByKind(items: EvidenceItem[]): Record<EvidenceKind, number> {
  const counts: Record<EvidenceKind, number> = {
    LAW: 0,
    DECREE: 0,
    INTERNAL_RULE: 0,
    PRECEDENT: 0,
    ADMINISTRATIVE_PENALTY: 0,
    OTHER: 0,
  };
  for (const item of items) counts[item.kind] += 1;
  return counts;
}
