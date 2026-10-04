# OmniSift RAG Evaluation Results

**Date**: 2026-10-04 00:38:38
**Test Cases**: 27

## Summary Metrics (Average across all test cases)

| Metric | Baseline (Dense Only) | OmniSift (Hybrid + Rerank) | Improvement |
|--------|----------------------|---------------------------|-------------|
| faithfulness | 0.000 | 0.000 | +0.0% |
| answer_relevancy | 0.010 | 0.010 | +0.0% |
| context_recall | 0.000 | 0.000 | +0.0% |
| context_precision | 0.000 | 0.000 | +0.0% |
| latency_ms | 3096 | 2930 | -5.4% |

## Detailed Results

### Test Case 1: What is the revenue recognition policy under ASC 606?

- **Role**: finance
- **Expected Source**: q3_2024_financial_report.md

#### Baseline (Dense Only)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.033
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 4155ms

#### OmniSift (Hybrid + Rerank)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.033
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 3393ms

---

### Test Case 2: What was our ARR as of Q3 2024?

- **Role**: finance
- **Expected Source**: q3_2024_financial_report.md

#### Baseline (Dense Only)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.000
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 3883ms

#### OmniSift (Hybrid + Rerank)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.000
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 3430ms

---

### Test Case 3: What is the contract value for account ACC-2024-0042?

- **Role**: finance
- **Expected Source**: q3_2024_financial_report.md

#### Baseline (Dense Only)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.000
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 3393ms

#### OmniSift (Hybrid + Rerank)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.000
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 3985ms

---

### Test Case 4: What is the incident response protocol for PII breaches?

- **Role**: finance
- **Expected Source**: q3_2024_financial_report.md

#### Baseline (Dense Only)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.000
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 3877ms

#### OmniSift (Hybrid + Rerank)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.000
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 3339ms

---

### Test Case 5: What are the indemnification limits in the master services agreement?

- **Role**: legal
- **Expected Source**: vendor_master_services_agreement.md

#### Baseline (Dense Only)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.000
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 1112ms

#### OmniSift (Hybrid + Rerank)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.000
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 767ms

---

### Test Case 6: What are the NDA terms in the vendor MSA?

- **Role**: legal
- **Expected Source**: vendor_master_services_agreement.md

#### Baseline (Dense Only)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.038
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 860ms

#### OmniSift (Hybrid + Rerank)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.038
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 787ms

---

### Test Case 7: What jurisdiction governs the master services agreement?

- **Role**: legal
- **Expected Source**: vendor_master_services_agreement.md

#### Baseline (Dense Only)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.000
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 1320ms

#### OmniSift (Hybrid + Rerank)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.000
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 800ms

---

### Test Case 8: What is the remote work policy effective January 2024?

- **Role**: general
- **Expected Source**: company_policy_handbook.md

#### Baseline (Dense Only)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.043
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 3778ms

#### OmniSift (Hybrid + Rerank)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.043
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 3319ms

---

### Test Case 9: What are the data classification levels?

- **Role**: general
- **Expected Source**: company_policy_handbook.md

#### Baseline (Dense Only)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.000
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 3433ms

#### OmniSift (Hybrid + Rerank)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.000
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 3384ms

---

### Test Case 10: What are the expense reimbursement per diem rates?

- **Role**: general
- **Expected Source**: company_policy_handbook.md

#### Baseline (Dense Only)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.000
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 3431ms

#### OmniSift (Hybrid + Rerank)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.000
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 3379ms

---

### Test Case 11: What health insurance tiers are available?

- **Role**: hr
- **Expected Source**: employee_handbook_2024.md

#### Baseline (Dense Only)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.000
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 3387ms

#### OmniSift (Hybrid + Rerank)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.000
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 3369ms

---

### Test Case 12: What is the 401(k) matching policy?

- **Role**: hr
- **Expected Source**: employee_handbook_2024.md

#### Baseline (Dense Only)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.000
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 3916ms

#### OmniSift (Hybrid + Rerank)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.000
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 3821ms

---

### Test Case 13: What is the parental leave policy?

- **Role**: hr
- **Expected Source**: employee_handbook_2024.md

#### Baseline (Dense Only)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.000
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 3897ms

#### OmniSift (Hybrid + Rerank)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.000
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 3406ms

---

### Test Case 14: What were the key product milestones from the Q3 all-hands?

- **Role**: general
- **Expected Source**: company_all_hands_q3.md

#### Baseline (Dense Only)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.000
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 3370ms

#### OmniSift (Hybrid + Rerank)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.000
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 3347ms

---

### Test Case 15: What are the company values announced at the all-hands?

- **Role**: general
- **Expected Source**: company_all_hands_q3.md

#### Baseline (Dense Only)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.000
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 3907ms

#### OmniSift (Hybrid + Rerank)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.000
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 3396ms

---

### Test Case 16: What was the net runway as of Q3 2024?

- **Role**: finance
- **Expected Source**: q3_2024_financial_report.md

#### Baseline (Dense Only)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.000
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 3914ms

#### OmniSift (Hybrid + Rerank)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.000
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 3898ms

---

### Test Case 17: What is the termination for convenience clause in the MSA?

- **Role**: legal
- **Expected Source**: vendor_master_services_agreement.md

#### Baseline (Dense Only)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.000
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 1046ms

#### OmniSift (Hybrid + Rerank)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.000
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 734ms

---

### Test Case 18: What security awareness training is required?

- **Role**: general
- **Expected Source**: company_policy_handbook.md

#### Baseline (Dense Only)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.067
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 3619ms

#### OmniSift (Hybrid + Rerank)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.067
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 3317ms

---

### Test Case 19: What is the PTO policy for 2024?

- **Role**: hr
- **Expected Source**: employee_handbook_2024.md

#### Baseline (Dense Only)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.000
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 3588ms

#### OmniSift (Hybrid + Rerank)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.000
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 3911ms

---

### Test Case 20: What is the remote work stipend?

- **Role**: hr
- **Expected Source**: employee_handbook_2024.md

#### Baseline (Dense Only)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.000
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 3351ms

#### OmniSift (Hybrid + Rerank)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.000
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 3840ms

---

### Test Case 21: What was the Q3 2024 cash burn rate?

- **Role**: finance
- **Expected Source**: q3_2024_financial_report.md

#### Baseline (Dense Only)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.000
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 3866ms

#### OmniSift (Hybrid + Rerank)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.000
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 3316ms

---

### Test Case 22: What are the service level commitments in the MSA?

- **Role**: legal
- **Expected Source**: vendor_master_services_agreement.md

#### Baseline (Dense Only)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.000
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 1565ms

#### OmniSift (Hybrid + Rerank)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.000
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 787ms

---

### Test Case 23: What are the quarterly review cycles for employees?

- **Role**: hr
- **Expected Source**: employee_handbook_2024.md

#### Baseline (Dense Only)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.000
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 3609ms

#### OmniSift (Hybrid + Rerank)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.000
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 3431ms

---

### Test Case 24: What public announcements were made at the Q3 all-hands?

- **Role**: general
- **Expected Source**: company_all_hands_q3.md

#### Baseline (Dense Only)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.056
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 3373ms

#### OmniSift (Hybrid + Rerank)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.056
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 3863ms

---

### Test Case 25: What is the gross margin reported in Q3 2024?

- **Role**: finance
- **Expected Source**: q3_2024_financial_report.md

#### Baseline (Dense Only)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.000
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 3862ms

#### OmniSift (Hybrid + Rerank)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.000
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 3359ms

---

### Test Case 26: What is the force majeure clause in the MSA?

- **Role**: legal
- **Expected Source**: vendor_master_services_agreement.md

#### Baseline (Dense Only)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.037
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 1038ms

#### OmniSift (Hybrid + Rerank)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.037
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 1312ms

---

### Test Case 27: What is the NRR (Net Revenue Retention) as of Q3 2024?

- **Role**: finance
- **Expected Source**: q3_2024_financial_report.md

#### Baseline (Dense Only)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.000
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 3055ms

#### OmniSift (Hybrid + Rerank)
- **Answer**: Insufficient context to answer.
- **Contexts Retrieved**: 0
- **Faithfulness**: 0.000
- **Answer Relevancy**: 0.000
- **Context Recall**: 0.000
- **Context Precision**: 0.000
- **Latency**: 3407ms

---

