# Sectional Title AI Agent Platform — Solution Design Document

**Version**: 1.0
**Date**: 7 June 2026
**Author**: AI Solutions Architect
**Status**: Draft — Pending Peer Review by 2x Opus Models
**Purpose**: Complete solution design for an autonomous agentic property management platform. This document contains the original brief, full requirements interview, and proposed architecture for reviewer validation.

---

## Table of Contents

1. [Original Request & Vision](#1-original-request--vision)
2. [Requirements Interview — Questions & Answers](#2-requirements-interview--questions--answers)
3. [Interview Outcome Summary](#3-interview-outcome-summary)
4. [Key Design Tensions & Constraints](#4-key-design-tensions--constraints)
5. [Solution Architecture](#5-solution-architecture)
6. [Technology Stack](#6-technology-stack)
7. [Agent Design](#7-agent-design)
8. [Data Architecture](#8-data-architecture)
9. [Security & POPIA Compliance](#9-security--popia-compliance)
10. [Cost Projections](#10-cost-projections)
11. [Phased Delivery Plan](#11-phased-delivery-plan)
12. [Open Questions & Risks](#12-open-questions--risks)
13. [User Journeys & UX Specification](#13-user-journeys--ux-specification)
14. [Testing & Agent Evaluation Strategy](#14-testing--agent-evaluation-strategy)
15. [Reviewer Instructions](#15-reviewer-instructions)

---

## 1. Original Request & Vision

### Stakeholder Context

The client is the **Chairperson and Trustee** of a Sectional Title complex within **The Wilds Estate** in Pretoria, South Africa. They have a deep background in software engineering, ML services, cloud architecture (AWS/Azure), Python, and container security.

### The Vision (Verbatim)

> I need to build a system where a team of specialized AI agents acts as my property management proxy. Most communication flows through a dedicated email address. These agents must ingest emails from managing agents, homeowners, tenants, and other trustees; evaluate the requests against a dynamically updated repository of knowledge artifacts (CSOS guidelines, the Sectional Titles Act, estate rules, AGM minutes, financials); formulate legally and factually sound advice; and take action or draft responses on my behalf (pending my approval).

### Core System Requirements (As Stated)

1. **Agentic Workflow**: A multi-agent system (utilizing the ReAct pattern and advanced reasoning) capable of classifying intents, retrieving exact legal/financial context, and formulating decisions.

2. **Dynamic Knowledge Base (RAG)**: A robust system to maintain, version, and query complex PDF and text artifacts (audit statements, rules, minutes) using modern retrieval-augmented generation.

3. **Communication Layer**: Integration with a dedicated email server for inbound parsing and outbound communication.

4. **UI/Dashboard**: A world-class, intuitive web application for reviewing AI summaries, approving/rejecting agent actions, tracking compliance events, viewing communication histories, and managing knowledge artifacts.

5. **Self-Advancement**: The system must be context-aware, learning from past decisions and corrections to improve future recommendations.

### Technical Considerations Raised by Stakeholder

- **Model Context Protocol (MCP)**: For agents accessing local/cloud file stores securely.
- **Approval Loop**: The hardest part — agent pauses execution, surfaces proposed action to dashboard, resumes on approval/modification.
- **Data Residency**: Financial statements and personal homeowner data must comply with the POPI Act. RAG vector database and document storage must be secure within AWS/Azure.

---

## 2. Requirements Interview — Questions & Answers

### Domain 1: Agent Architecture & Orchestration

| #   | Question                                                                                                                                                                                | Answer                                                                                                                                                                                                                                                                                                       |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Q1  | Are you leaning toward a specific agentic framework (LangGraph, CrewAI, AutoGen, custom ReAct loops), or is this open for recommendation?                                               | **Open to recommendation**                                                                                                                                                                                                                                                                                   |
| Q2  | Preferred LLM provider?                                                                                                                                                                 | **Anthropic (Claude)** + open to recommendation                                                                                                                                                                                                                                                              |
| Q2b | Monthly cost ceiling for LLM inference?                                                                                                                                                 | **$20/month maximum**                                                                                                                                                                                                                                                                                        |
| Q3  | Proposed agent decomposition: (a) Email Classifier/Router, (b) Legal Analyst, (c) Financial Analyst, (d) Compliance Tracker, (e) Draft Composer, (f) Orchestrator. Add/remove/collapse? | **Add two more**: (g) Wilds Estate Specialist — specializes in all rules and regulations related to The Wilds Estate. (h) Maintenance Specialist — specializes in all topics related to maintaining the exterior of the complex, expert in balancing costs and quality within Pretoria. **Total: 8 agents.** |
| Q4  | Should certain request categories be fully autonomous, or does everything pause for approval?                                                                                           | **Low-risk items can be autonomous from day 1**                                                                                                                                                                                                                                                              |
| Q5  | Should the system ever escalate directly to external parties (managing agent, lawyer, CSOS)?                                                                                            | **No — everything flows through me only**                                                                                                                                                                                                                                                                    |
| Q6  | How should the system track multi-turn conversations that span weeks?                                                                                                                   | **Full case file per issue**                                                                                                                                                                                                                                                                                 |

### Domain 2: Knowledge Base & RAG

| #   | Question                                                              | Answer                                                                                            |
| --- | --------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| Q7  | How many documents in your current corpus?                            | **20–50 documents**                                                                               |
| Q7b | Which document formats?                                               | **All**: Text PDF, scanned/OCR PDF, Word (.docx), Excel (.xlsx), plain text/email exports, images |
| Q8  | How often do new documents arrive?                                    | **Ad-hoc / irregular**                                                                            |
| Q9  | Do you need historical document versioning (query by effective date)? | **Yes — need historical versions queryable by date**                                              |
| Q10 | Preference for retrieval strategy?                                    | **Agentic RAG** (agent decides what to retrieve and re-ranks)                                     |
| Q11 | Preference for embedding model?                                       | **Amazon Titan Embedding v2**                                                                     |
| Q12 | Preferred vector store?                                               | **Amazon Bedrock Knowledge Bases (managed)**                                                      |

### Domain 3: Communication Layer (Email)

| #   | Question                                              | Answer                                                                                                                     |
| --- | ----------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| Q13 | What email provider will the dedicated address use?   | **Google Workspace (Gmail)**                                                                                               |
| Q14 | What elements of inbound emails need to be parsed?    | **All**: Email body text, PDF/Word attachments, image attachments (OCR), calendar invites (.ics), multilingual (Afrikaans) |
| Q15 | Outbound email setup?                                 | **Same address**; DKIM/SPF/DMARC is unknown — needs setup                                                                  |
| Q16 | Should outbound replies maintain email threading?     | **Yes — proper threading is important**                                                                                    |
| Q17 | Are there other communication channels besides email? | **Email only — no other channels**                                                                                         |

### Domain 4: UI / Dashboard

| #   | Question                                      | Answer                                                                                                                                                                |
| --- | --------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Q18 | Preferred frontend framework?                 | **Open to recommendation**                                                                                                                                            |
| Q19 | Which additional dashboard views needed?      | **All**: Financial overview with levy arrears, trustee voting/resolution tracker, contractor/vendor management, maintenance request tracker, homeowner/unit directory |
| Q20 | Mobile access requirements?                   | **Mobile-responsive web first**, then native mobile app once production-ready                                                                                         |
| Q21 | Notification mechanism for pending approvals? | **Email notification + WhatsApp**                                                                                                                                     |
| Q22 | Multi-user access?                            | **Yes — other trustees will use it too (need RBAC)**                                                                                                                  |

### Domain 5: Human-in-the-Loop (Approval Workflow)

| #    | Question                                                   | Answer                                                                                               |
| ---- | ---------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Q23  | What should happen if you don't act on a pending approval? | **Reminder + auto holding response to requester**                                                    |
| Q23b | Reminder timing?                                           | **Configurable per priority level**                                                                  |
| Q24  | How to modify an agent's proposed draft?                   | **Both**: inline text edit AND natural-language feedback with regeneration                           |
| Q25  | Full audit trail needed?                                   | **Yes — full audit trail is essential** (every decision, context, draft, modification, final action) |
| Q26  | Batch approval for low-risk items?                         | **No — every item must be reviewed individually**                                                    |

### Domain 6: Data Privacy, Security & Compliance (POPIA)

| #    | Question                                         | Answer                                                 |
| ---- | ------------------------------------------------ | ------------------------------------------------------ |
| Q27  | Cloud region for hosting?                        | **AWS af-south-1 (Cape Town)**                         |
| Q27b | Existing AWS account?                            | **No — need to create one**                            |
| Q28  | How should PII be handled?                       | **Both encryption AND redaction** in logs/vector store |
| Q29  | Comfortable sending data to third-party LLM API? | **No — need AWS Bedrock (data stays in my account)**   |
| Q30  | Authentication method?                           | **Open to recommendation**                             |
| Q31  | Data retention period?                           | **Open to recommendation**                             |
| Q32  | Backup & disaster recovery?                      | **Best-effort (24–48 hours)**                          |

### Domain 7: Legal & Compliance Specifics

| #   | Question                                                 | Answer                                                                                                                 |
| --- | -------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| Q33 | Unilateral decision authority vs. trustee/BC resolution? | **Not sure — research required** based on CSOS rules, best practices, and SA law. System must encode these boundaries. |
| Q34 | Recurring compliance events to track?                    | **All listed** + legal disputes, legal events, expenditure and claims events                                           |
| Q35 | Should agent follow formal dispute escalation process?   | **Yes — encode the formal dispute process** from Management Rules                                                      |
| Q36 | AI disclosure in outbound emails?                        | **No disclaimer — appear as from me directly**                                                                         |

### Domain 8: Infrastructure & DevOps

| #   | Question                                       | Answer                                                   |
| --- | ---------------------------------------------- | -------------------------------------------------------- |
| Q37 | Hosting model?                                 | **Serverless (Lambda + Fargate) — minimal ops**          |
| Q38 | CI/CD pipeline?                                | **GitHub Actions**                                       |
| Q39 | Observability requirements?                    | **Basic CloudWatch is fine**, but **NEVER log PII data** |
| Q40 | Monthly infrastructure budget (excluding LLM)? | **$0–25/month**                                          |

### Domain 9: Self-Improvement & Learning

| #   | Question                                      | Answer                                                                                                         |
| --- | --------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| Q41 | How should the system learn from corrections? | **Few-shot examples** + **dynamic skill updating** — agents use skills, feedback updates the skill definitions |
| Q42 | Maintain a precedent database?                | **Yes** — remember past decisions for similar future cases                                                     |
| Q43 | Confidence scoring?                           | **Yes** — show scores, auto-flag low-confidence items for extra scrutiny                                       |

### Domain 10: MVP Scope & Prioritization

| #   | Question                                    | Answer                                                                                                                                                                          |
| --- | ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Q44 | Non-negotiable MVP capabilities (pick 3-5)? | **7 selected**: Email ingestion & classification, RAG knowledge base, draft response generation, approval workflow (HITL), dashboard UI, case file tracking, precedent database |
| Q45 | Historical data backlog?                    | **Yes — small backlog (< 50 items)**                                                                                                                                            |

---

## 3. Interview Outcome Summary

### Confirmed Architecture Profile

| Dimension      | Decision                      |
| -------------- | ----------------------------- |
| Cloud Provider | AWS (af-south-1 Cape Town)    |
| LLM Runtime    | AWS Bedrock (Claude models)   |
| Embedding      | Amazon Titan Embedding v2     |
| Vector Store   | Bedrock Knowledge Bases       |
| Compute        | Serverless (Lambda + Fargate) |
| Email          | Google Workspace / Gmail API  |
| Frontend       | TBD (recommendation below)    |
| Auth           | TBD (recommendation below)    |
| CI/CD          | GitHub Actions                |
| Budget         | ~$45/mo total                 |

### Agent Roster (10 Agents)

> Agents 1–8 are **backend pipeline agents** (event-driven, no direct human chat surface). Agent 9 is the **user-facing conversational front door** inside the dashboard. Agent 10 is a **scheduled** (non-interactive) auditor.

1. **Orchestrator** — Routes, prioritizes, manages workflow state
2. **Email Classifier/Router** — Parses inbound, classifies intent, extracts entities
3. **Legal Analyst** — CSOS, Sectional Titles Act, Management Rules expertise
4. **Financial Analyst** — Levy calculations, arrears, budget analysis
5. **Compliance Tracker** — Calendar events, deadlines, statutory requirements
6. **Draft Composer** — Generates email responses matching stakeholder's tone
7. **Wilds Estate Specialist** — Estate-specific rules, HOA regulations
8. **Maintenance Specialist** — Exterior maintenance, Pretoria contractor knowledge, cost optimization
9. **Trustee Copilot** — In-app conversational assistant. Answers "why/what" questions grounded on the Knowledge Base + case files, and can initiate actions (draft a reply, open a case, schedule a reminder) that are routed through the **same human-in-the-loop approval loop** as the pipeline agents
10. **Knowledge Auditor** — _Scheduled_ (monthly), not interactive. Audits the knowledge base for broken provenance, stale/superseded documents, contradictions between sources, and coverage gaps; emits an action-list report for human review. Never edits authoritative content automatically (§7.5, §8.5)

### Non-Functional Requirements

| Requirement    | Target                         |
| -------------- | ------------------------------ |
| Availability   | Best-effort (not 24/7 SLA)     |
| Recovery       | RPO/RTO: 24–48 hours           |
| Data Residency | South Africa (af-south-1)      |
| PII Protection | Encryption + redaction         |
| Audit          | Full trail, legally defensible |
| Multi-tenancy  | RBAC for multiple trustees     |
| Budget         | ≤ $45/mo total                 |

---

## 4. Key Design Tensions & Constraints

### 4.1 Budget vs. Ambition

**Tension**: $20/mo LLM + $25/mo infra for 8 agents, managed RAG, Fargate, Gmail integration, WhatsApp notifications, and a full RBAC dashboard.

**Mitigation Strategy**:

- Use **Claude 3 Haiku** ($0.25/MTok input, $1.25/MTok output) for classification, routing, and simple tasks
- Reserve **Claude 3.5 Sonnet** for complex legal reasoning and draft generation only
- Aggressive prompt caching (Bedrock supports this)
- Serverless = pay only for invocations; at low volume (~50-100 emails/month for a small complex), costs stay minimal
- Free-tier exploitation: Lambda (1M requests/mo free), DynamoDB (25GB free), S3 (5GB free), Cognito (50k MAU free)

### 4.2 Bedrock Availability in af-south-1

**Tension**: Not all Bedrock models/features are available in Cape Town region.

**Mitigation Strategy**:

- Verify current model availability at deployment time
- If Claude models unavailable in af-south-1: use **cross-region inference** (Bedrock supports this) with eu-west-1 as inference region while keeping all data storage in af-south-1
- Document storage, DynamoDB, S3, and the dashboard remain in af-south-1 for POPIA compliance
- Only the inference call transits to another region (stateless, no data persisted there)

### 4.3 Seven MVP Features

**Tension**: 7 non-negotiables is ambitious for a first release.

**Mitigation Strategy**: Phase the MVP internally into MVP-α (core loop) and MVP-β (enhanced features). See Section 11.

### 4.4 Dynamic Skill Updating

**Tension**: Agents that self-improve from feedback adds complexity to the framework.

**Mitigation Strategy**:

- Phase 1: Store corrections as structured few-shot examples in DynamoDB
- Phase 2: Introduce skill definitions as versioned prompt components that the orchestrator selects dynamically
- Phase 3: Automated skill mutation based on correction patterns

### 4.5 OCR & Multilingual Processing on a Budget

**Tension**: Scanned PDFs and Afrikaans emails require OCR and translation, which can be expensive.

**Mitigation Strategy**:

- Use **Amazon Textract** for OCR (pay-per-page, ~$1.50/1000 pages — well within budget for <50 docs)
- Claude handles Afrikaans natively — no separate translation service needed
- Pre-process documents once at ingestion time, store extracted text

---

## 5. Solution Architecture

### 5.1 High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              INTERNET                                         │
└─────────┬───────────────────────┬──────────────────────────┬────────────────┘
          │                       │                          │
          ▼                       ▼                          ▼
┌──────────────────┐   ┌──────────────────┐      ┌──────────────────┐
│  Google Gmail    │   │   Dashboard UI   │      │  WhatsApp Bus.   │
│  (Inbound/Out)  │   │  (CloudFront+S3) │      │  API (Notify)    │
└────────┬─────────┘   └────────┬─────────┘      └────────┬─────────┘
         │                      │                          │
         ▼                      ▼                          │
┌──────────────────────────────────────────────────────────┴──────────────────┐
│                        API GATEWAY (REST + WebSocket)                         │
└──────────┬──────────────────────┬──────────────────────┬────────────────────┘
           │                      │                      │
           ▼                      ▼                      ▼
┌────────────────┐    ┌────────────────────┐   ┌─────────────────────┐
│  Email Ingestion│    │  Dashboard API     │   │  Notification Svc   │
│  Lambda         │    │  Lambda/Fargate    │   │  Lambda             │
└───────┬────────┘    └────────┬───────────┘   └─────────────────────┘
        │                      │
        ▼                      ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                         ORCHESTRATOR (Step Functions)                          │
│                                                                               │
│  ┌─────────┐ ┌──────────┐ ┌───────────┐ ┌────────────┐ ┌─────────────────┐ │
│  │Classifier│ │Legal     │ │Financial  │ │Compliance  │ │Draft Composer   │ │
│  │/Router   │ │Analyst   │ │Analyst    │ │Tracker     │ │                 │ │
│  └─────────┘ └──────────┘ └───────────┘ └────────────┘ └─────────────────┘ │
│  ┌──────────────────┐ ┌────────────────────┐                                │
│  │Wilds Estate Spec.│ │Maintenance Spec.   │                                │
│  └──────────────────┘ └────────────────────┘                                │
└──────────────────────────────┬───────────────────────────────────────────────┘
                               │
        ┌──────────────────────┼──────────────────────────┐
        ▼                      ▼                          ▼
┌──────────────┐    ┌──────────────────┐       ┌──────────────────┐
│ Bedrock      │    │  DynamoDB        │       │  S3              │
│ (Claude +    │    │  (Cases, Audit,  │       │  (Documents,     │
│  Titan Emb.) │    │   Precedents,    │       │   Attachments)   │
│              │    │   Skills, State) │       │                  │
│ Knowledge    │    └──────────────────┘       └──────────────────┘
│ Bases (RAG)  │
└──────────────┘
```

### 5.2 Component Breakdown

> Stores shown are indicative. DynamoDB also holds the **Documents** catalogue/filing index (§8.4) and the **Tasks** Kanban board (§8.6). S3 holds a **single canonical copy** per document version (no WORM/Object Lock — §8.4). The KB has two data sources: a primary `SOURCE` corpus and a lower-priority `DERIVED` Wiki (§8.5).

#### Email Ingestion Pipeline

```
Gmail → Pub/Sub Push (or Poll via Lambda cron) → SQS → Email Processor Lambda
  → Parse body (text/html)
  → Extract attachments → S3
  → OCR if image/scanned PDF (Textract)
  → Detect language
  → Forward to Orchestrator
```

#### Orchestrator (AWS Step Functions)

```
Receive Parsed Email
  → Classify Intent (Classifier Agent via Bedrock)
  → Determine Required Agents
  → Fan-out to relevant specialists (parallel or sequential)
  → Aggregate responses
  → Draft Composer generates response
  → Confidence scoring
  → IF low-risk AND high-confidence → Auto-send (with audit log)
  → ELSE → Pause execution (wait state) → Notify user → Resume on approval
```

#### Approval Workflow (Human-in-the-Loop)

```
Step Functions Wait State (Task Token)
  → Store pending action in DynamoDB
  → Push notification (Email + WhatsApp)
  → Dashboard polls/subscribes for pending items
  → User approves/modifies via Dashboard
  → Callback to Step Functions with token
  → Resume: send email / take action
  → Log to audit trail

Timeout Handler:
  → Configurable per priority (e.g., High=2h, Medium=8h, Low=24h)
  → On timeout: send reminder + auto-send holding response
```

#### RAG Pipeline (Agentic)

```
Agent needs context
  → Formulates search query (may reformulate multiple times)
  → Queries Bedrock Knowledge Base
  → Evaluates relevance of results
  → If insufficient: reformulates and re-queries
  → If versioned doc needed: filters by effective_date metadata
  → Returns grounded answer with source citations
```

---

## 6. Technology Stack

### 6.1 Definitive Stack

| Layer                    | Technology                          | Justification                                                                    |
| ------------------------ | ----------------------------------- | -------------------------------------------------------------------------------- |
| **LLM (Reasoning)**      | Claude 3.5 Sonnet via Bedrock       | Best reasoning for legal/financial tasks; data stays in AWS                      |
| **LLM (Classification)** | Claude 3 Haiku via Bedrock          | 10x cheaper; sufficient for routing/classification                               |
| **Embeddings**           | Amazon Titan Embedding v2           | AWS-native, POPIA-compliant, no data leaves account                              |
| **RAG**                  | Bedrock Knowledge Bases             | Fully managed; handles chunking, indexing, retrieval                             |
| **OCR**                  | Amazon Textract                     | Pay-per-page, handles scanned PDFs and images                                    |
| **Orchestration**        | AWS Step Functions                  | Native wait states for HITL; visual workflow; serverless                         |
| **Compute**              | AWS Lambda + Fargate                | Lambda for event-driven; Fargate for dashboard API                               |
| **Database**             | DynamoDB                            | Serverless, free tier (25GB), flexible schema for case files                     |
| **Object Storage**       | S3                                  | Documents, attachments, static assets                                            |
| **Email**                | Gmail API (Google Workspace)        | Push notifications via Pub/Sub or polling                                        |
| **Frontend**             | Next.js (React) on S3 + CloudFront  | SSR capability, excellent mobile-responsive ecosystem, large component libraries |
| **Auth**                 | AWS Cognito                         | Free tier (50k MAU), RBAC via groups, MFA support                                |
| **Notifications**        | SES (email) + WhatsApp Business API | SES is pennies; WhatsApp via Meta Cloud API                                      |
| **CI/CD**                | GitHub Actions                      | Deploy to AWS via OIDC (no stored credentials)                                   |
| **IaC**                  | Terraform (or AWS CDK)              | Reproducible infrastructure                                                      |
| **Monitoring**           | CloudWatch (logs + metrics)         | Basic; PII-free logging with custom sanitizer                                    |
| **Queue**                | SQS                                 | Decouple email ingestion from processing                                         |

### 6.2 Recommendation: Agentic Framework

Given the constraints ($20/mo inference, 8 specialized agents, Step Functions as orchestrator), the recommendation is:

**Custom lightweight agent implementation using Bedrock Converse API + Step Functions**

Rationale:

- LangGraph/CrewAI add dependency overhead and are optimized for complex multi-turn within a single invocation — but we're using Step Functions for state management
- Each "agent" is actually a **Lambda function with a specialized system prompt, tool definitions, and access to Bedrock Knowledge Bases**
- Step Functions handles the orchestration graph (routing, fan-out, wait states)
- This minimizes token waste from framework overhead and keeps costs within $20/mo

Architecture:

```python
# Each agent is a Lambda with this core pattern:
def handler(event, context):
    system_prompt = load_agent_prompt("legal_analyst")
    tools = load_agent_tools("legal_analyst")  # e.g., query_knowledge_base, get_precedent
    few_shots = load_few_shot_examples("legal_analyst")

    response = bedrock.converse(
        modelId="anthropic.claude-3-5-sonnet-v2",
        system=system_prompt + few_shots,
        messages=event["messages"],
        toolConfig=tools
    )

    # Handle tool use loop (ReAct pattern)
    while response.stop_reason == "tool_use":
        tool_result = execute_tool(response.tool_calls)
        response = bedrock.converse(..., messages=[...previous, tool_result])

    return {"agent": "legal_analyst", "response": response, "confidence": score}
```

---

## 7. Agent Design

### 7.1 Agent Specifications

#### Agent 1: Email Classifier/Router

| Attribute | Value                                                                      |
| --------- | -------------------------------------------------------------------------- |
| Model     | Claude 3 Haiku (cheapest)                                                  |
| Purpose   | Parse inbound email, classify intent, extract entities, determine priority |
| Input     | Raw email (body + parsed attachments)                                      |
| Output    | `{intent, priority, entities, suggested_agents[], case_id}`                |
| Tools     | None (pure classification)                                                 |
| Autonomy  | Fully autonomous (classification doesn't require approval)                 |

**Intent Taxonomy** (expandable):

- `maintenance_request`
- `levy_query` / `levy_dispute`
- `rule_violation_report`
- `agm_notice`
- `financial_statement`
- `insurance_claim`
- `general_enquiry`
- `legal_notice`
- `vendor_quote`
- `trustee_resolution_request`
- `complaint`
- `acknowledgement_only`

#### Agent 2: Legal Analyst

| Attribute | Value                                                                                                           |
| --------- | --------------------------------------------------------------------------------------------------------------- |
| Model     | Claude 3.5 Sonnet (reasoning needed)                                                                            |
| Purpose   | Analyze legal implications, cite specific Act sections, determine authority boundaries                          |
| Input     | Classified email + case context                                                                                 |
| Output    | Legal analysis with citations, risk assessment, recommended action                                              |
| Tools     | `query_knowledge_base(topic, date_filter)`, `get_precedent(similar_case)`, `check_authority_scope(action_type)` |
| Autonomy  | Never autonomous — always feeds into Draft Composer for approval                                                |

#### Agent 3: Financial Analyst

| Attribute | Value                                                                               |
| --------- | ----------------------------------------------------------------------------------- |
| Model     | Claude 3.5 Sonnet                                                                   |
| Purpose   | Levy calculations, budget analysis, arrears assessment, expenditure evaluation      |
| Input     | Financial query + relevant documents                                                |
| Output    | Financial analysis with numbers, comparisons, recommendations                       |
| Tools     | `query_knowledge_base(financial)`, `get_levy_register()`, `calculate_arrears(unit)` |
| Autonomy  | Never autonomous                                                                    |

#### Agent 4: Compliance Tracker

| Attribute | Value                                                                                         |
| --------- | --------------------------------------------------------------------------------------------- |
| Model     | Claude 3 Haiku                                                                                |
| Purpose   | Monitor deadlines, trigger reminders, track statutory requirements                            |
| Input     | Calendar events, document dates, AGM schedules                                                |
| Output    | Compliance alerts, upcoming deadline notifications                                            |
| Tools     | `get_compliance_calendar()`, `create_reminder(event, date)`, `check_statutory_deadline(type)` |
| Autonomy  | Reminders are autonomous; compliance actions require approval                                 |

#### Agent 5: Draft Composer

| Attribute | Value                                                                                          |
| --------- | ---------------------------------------------------------------------------------------------- |
| Model     | Claude 3.5 Sonnet                                                                              |
| Purpose   | Generate email responses matching the chairperson's tone and incorporating specialist analysis |
| Input     | Aggregated analysis from other agents + case context + tone examples                           |
| Output    | Draft email ready for approval                                                                 |
| Tools     | `get_tone_examples()`, `get_email_template(type)`, `format_legal_citation()`                   |
| Autonomy  | Low-risk acknowledgements can be autonomous; substantive responses require approval            |

#### Agent 6: Orchestrator

| Attribute      | Value                                                         |
| -------------- | ------------------------------------------------------------- |
| Model          | Step Functions (not an LLM agent)                             |
| Purpose        | Route work, manage state, handle approvals, coordinate agents |
| Implementation | AWS Step Functions state machine                              |
| Autonomy       | Fully autonomous (it's the workflow engine)                   |

#### Agent 7: Wilds Estate Specialist

| Attribute | Value                                                                                                                    |
| --------- | ------------------------------------------------------------------------------------------------------------------------ |
| Model     | Claude 3.5 Sonnet                                                                                                        |
| Purpose   | Expert on Wilds Estate-specific rules, HOA regulations, estate-level governance                                          |
| Input     | Queries involving estate rules, common areas, estate levies, architectural guidelines                                    |
| Output    | Estate-specific guidance with rule citations                                                                             |
| Tools     | `query_knowledge_base(wilds_estate_rules)`, `get_estate_contacts()`, `check_architectural_guidelines(modification_type)` |
| Autonomy  | Never autonomous                                                                                                         |

#### Agent 8: Maintenance Specialist

| Attribute | Value                                                                                                                             |
| --------- | --------------------------------------------------------------------------------------------------------------------------------- |
| Model     | Claude 3.5 Sonnet                                                                                                                 |
| Purpose   | Exterior maintenance expertise, cost/quality optimization in Pretoria market                                                      |
| Input     | Maintenance requests, vendor quotes, inspection reports                                                                           |
| Output    | Maintenance recommendations, cost comparisons, vendor suggestions                                                                 |
| Tools     | `query_knowledge_base(maintenance)`, `get_vendor_history(category)`, `compare_quotes(items[])`, `estimate_cost(work_type, scope)` |
| Autonomy  | Never autonomous                                                                                                                  |

### 7.2 Agent Interaction Patterns

```
Example Flow: Homeowner reports a roof leak

1. Email arrives → Email Classifier
   → Intent: maintenance_request
   → Priority: HIGH (structural)
   → Suggested agents: [Maintenance Specialist, Financial Analyst]

2. Orchestrator dispatches in parallel:
   a. Maintenance Specialist: "Assess severity, recommend action, estimate cost range"
   b. Financial Analyst: "Check maintenance reserve, assess budget impact"
   c. Legal Analyst: "Confirm body corporate responsibility for roof (Section 3(1)(a))"

3. Results aggregated → Draft Composer:
   → Generates response acknowledging the issue
   → States body corporate responsibility
   → Proposes getting 3 quotes
   → Mentions timeline

4. Confidence: 0.87 (HIGH) → Still requires approval (maintenance expenditure)

5. Pending action surfaces in Dashboard + WhatsApp notification

6. User approves → Email sent → Case file updated → Precedent stored
```

### 7.3 Skill System Design

Skills are versioned prompt components stored in DynamoDB that agents load dynamically:

```json
{
  "skill_id": "draft_maintenance_acknowledgement",
  "agent": "draft_composer",
  "version": 3,
  "effective_date": "2026-06-01",
  "prompt_fragment": "When acknowledging a maintenance request, always: 1) Confirm receipt, 2) State the body corporate's responsibility if applicable, 3) Provide expected timeline for assessment, 4) Ask if emergency measures needed immediately.",
  "few_shot_examples": [
    {
      "input": "...",
      "output": "...",
      "correction_source": "user_feedback_2026-05-15"
    }
  ],
  "performance_metrics": {
    "times_used": 12,
    "times_modified": 2,
    "approval_rate": 0.83
  }
}
```

When user modifies a draft:

1. Store the correction as a new few-shot example
2. If modification pattern repeats 3+ times → auto-update skill prompt
3. Increment skill version
4. Log the evolution in audit trail

### 7.4 Agent 9: Trustee Copilot (User-Facing Assistant)

| Attribute | Value                                                                                                                                                                                                                   |
| --------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Model     | Claude 3 Haiku (default) → escalate to Claude 3.5 Sonnet for legal/financial reasoning                                                                                                                                  |
| Purpose   | In-app conversational assistant: answer the trustee's "why/what" questions about anything on screen, grounded on the Knowledge Base + case files; optionally initiate actions                                           |
| Input     | User message + active screen context (case/document/approval) + RBAC role                                                                                                                                               |
| Output    | Grounded answer **with inline citations**, and optionally a proposed action card                                                                                                                                        |
| Tools     | `query_knowledge_base(topic, date_filter)`, `get_case(case_id)`, `get_precedent(query)`, `propose_draft(case_id)`, `open_case(...)`, `create_reminder(...)`                                                             |
| Autonomy  | **Agentic but gated**: any action it proposes is created in a _pending/draft_ state and enters the standard human-in-the-loop approval loop. The Copilot never sends email or commits an irreversible action on its own |

**Why a separate agent**: Agents 1–8 are event-driven pipeline workers with no chat surface. The Copilot is the only agent a human converses with directly, so it has distinct requirements: RBAC-bounded retrieval, mandatory citations, a "no grounded source → say so" fallback (R10), and an audit tag of `via=copilot` on anything it initiates.

**Guardrails**:

- Read scope is bounded by the caller's RBAC role; it cannot surface PII the user isn't entitled to.
- It must not answer a legal/financial question without a retrieved citation (same anti-hallucination rule as R5).
- Every Copilot-initiated action is logged as `actor=USER#{id}` `via=copilot` and is subject to the same approval gate and confidence scoring as pipeline drafts.

### 7.5 Agent 10: Knowledge Auditor (Scheduled)

| Attribute | Value                                                                                                                                                                                              |
| --------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Model     | Claude 3 Haiku (bulk scan) → Claude 3.5 Sonnet only to adjudicate a flagged contradiction                                                                                                          |
| Purpose   | Monthly health-check of the knowledge base: broken provenance/citations, stale or superseded documents still being cited, SOURCE-vs-SOURCE and DERIVED-vs-SOURCE contradictions, and coverage gaps |
| Trigger   | EventBridge schedule (monthly); also on-demand from the Knowledge Base screen                                                                                                                      |
| Input     | `Documents` catalogue (§8.4), KB chunks, the derived Wiki (§8.5), recent `Precedents`/outputs                                                                                                      |
| Output    | An **audit report** with a prioritized **action list** (e.g., "Conduct Rules v1 still cited by Wiki page X — relink to v2"; "No document covers short-term-letting rules")                         |
| Tools     | `query_knowledge_base`, `list_catalogue(filter)`, `check_provenance(wiki_page)`, `find_contradictions(topic)`, `get_coverage_gaps()`                                                               |
| Autonomy  | **Read-only / advisory.** It _proposes_ actions; a human approves before any re-index, relink, supersede, or document request. It **never edits SOURCE content**                                   |

**Why scheduled, not pipeline.** Agents 1–8 are event-driven and Agent 9 (Copilot) is interactive; the Auditor is a periodic batch job. It implements the "monthly health-check" from the reviewed self-improving-KB pattern, adapted with provenance guardrails (§8.5) so a legal corpus is never silently rewritten. Its action list is executed only after human confirmation, feeding the compounding loop (§7.3, §8.5).

---

## 8. Data Architecture

### 8.1 DynamoDB Table Design

#### Table: `Cases`

```
PK: CASE#{case_id}
SK: META
  - status: OPEN | PENDING_APPROVAL | CLOSED
  - created_at, updated_at
  - priority: HIGH | MEDIUM | LOW
  - intent: maintenance_request | levy_query | ...
  - involved_parties: [{name, email, role}]
  - unit_number: string
  - summary: string (AI-generated)

SK: EMAIL#{timestamp}#{message_id}
  - direction: INBOUND | OUTBOUND
  - subject, from, to, cc
  - body_text (PII-redacted for logs; full in S3)
  - attachments: [{s3_key, filename, type}]
  - thread_id, in_reply_to

SK: ACTION#{timestamp}
  - agent: string
  - action_type: DRAFT | ANALYSIS | DECISION
  - content: string
  - confidence: number
  - status: PENDING | APPROVED | MODIFIED | REJECTED
  - approval_token: string (Step Functions task token)
  - modified_by: user_id
  - original_draft: string
  - final_draft: string

SK: AUDIT#{timestamp}
  - event_type: string
  - actor: SYSTEM | USER#{user_id}
  - details: object
  - context_retrieved: [{source, chunk, relevance_score}]
```

#### Table: `Precedents`

```
PK: PRECEDENT#{precedent_id}
SK: META
  - intent: string
  - keywords: string[]
  - case_ref: case_id
  - decision_summary: string
  - outcome: string
  - date: string
  - embedding_vector: (stored in Bedrock KB for similarity search)
```

#### Table: `Skills`

```
PK: SKILL#{skill_id}
SK: VERSION#{version_number}
  - agent: string
  - prompt_fragment: string
  - few_shot_examples: object[]
  - effective_date: string
  - performance_metrics: object
```

#### Table: `ComplianceCalendar`

```
PK: EVENT#{event_id}
SK: META
  - type: AGM | LEVY_INCREASE | INSURANCE | CSOS_RETURN | ...
  - due_date: string
  - status: UPCOMING | OVERDUE | COMPLETED
  - reminder_schedule: [{days_before, sent}]
  - linked_case: case_id (optional)
  - notes: string
```

#### Table: `Users`

```
PK: USER#{user_id}
SK: META
  - email: string
  - name: string
  - role: CHAIRPERSON | TRUSTEE | VIEWER
  - permissions: string[]
  - notification_preferences: object
```

### 8.2 S3 Bucket Structure

```
s3://sectional-title-platform-{account_id}/
├── documents/
│   ├── {document_id}/
│   │   ├── original/          # Original uploaded file
│   │   ├── extracted/         # OCR/text extraction output
│   │   └── metadata.json     # Version history, effective dates
├── emails/
│   ├── inbound/{year}/{month}/{message_id}/
│   │   ├── body.txt
│   │   ├── body.html
│   │   └── attachments/
│   └── outbound/{year}/{month}/{message_id}/
├── knowledge-base/
│   ├── sources/               # Processed docs for Bedrock KB ingestion
│   └── metadata/              # Bedrock KB data source configs
├── dashboard/
│   └── static/                # Next.js build output (if S3-hosted)
└── backups/
    └── dynamodb/              # Periodic DynamoDB exports
```

### 8.3 Document Versioning Model

```json
{
  "document_id": "doc_001",
  "title": "Body Corporate Conduct Rules",
  "versions": [
    {
      "version": 1,
      "effective_from": "2020-01-15",
      "effective_until": "2023-08-01",
      "s3_key": "documents/doc_001/original/conduct_rules_v1.pdf",
      "extracted_text_key": "documents/doc_001/extracted/v1.txt",
      "ingested_to_kb": true
    },
    {
      "version": 2,
      "effective_from": "2023-08-01",
      "effective_until": null,
      "s3_key": "documents/doc_001/original/conduct_rules_v2.pdf",
      "extracted_text_key": "documents/doc_001/extracted/v2.txt",
      "ingested_to_kb": true
    }
  ]
}
```

When an agent queries the knowledge base with a date context (e.g., "What rule applied in March 2022?"), the metadata filter ensures only the correct version is retrieved.

### 8.4 Document Catalogue & Filing System

Every document that enters the system is **catalogued** for historical and audit purposes. The catalogue is the queryable index over the S3 originals; it records classification, lifecycle, version lineage, KB-ingestion state, and an append-only audit log per document. This is the "filing system" and it is the same surface the RAG pipeline resolves citations through.

#### Table: `Documents` (Catalogue)

```
PK: DOC#{document_id}
SK: META
  - title, category (taxonomy below), tags[]
  - provenance: SOURCE | DERIVED        # SOURCE = authoritative; DERIVED = AI-generated (§8.5)
  - status: DRAFT | EXTRACTING | INDEXING | ACTIVE | SUPERSEDED | FAILED
  - origin: UPLOAD | EMAIL_ATTACHMENT | MINUTES_EXTRACTION | AI_GENERATED
  - current_version: number
  - s3_key_original, extracted_text_key
  - kb_ingested: bool, kb_data_source_id
  - effective_from, effective_until      # for the current version
  - linked_case, linked_event (optional)
  - uploaded_by, uploaded_at

SK: VERSION#{n}
  - effective_from, effective_until
  - s3_key, extracted_text_key, ingested_to_kb
  - supersedes: version
  - ocr_confidence, page_count

SK: AUDIT#{timestamp}
  - event: UPLOADED | RECLASSIFIED | VERSION_ADDED | INGESTED | SUPERSEDED | ERASED
  - actor, details
```

**Classification taxonomy** (an agent assigns category + tags + effective date on ingest; human-overridable per the agreed decision):
`Statutory/Legal` · `Estate Rules` · `Financials` · `Minutes` · `Insurance` · `Maintenance/Contractors` · `Correspondence` · `Other`.

**Filing/storage decision (cost-sensitive).** A **single canonical copy** of each document version is stored in S3, with this DynamoDB catalogue as the queryable index. There is **no S3 Object Lock/WORM and no bucket-level object versioning** — legal versioning is modelled explicitly as `VERSION#{n}` records (§8.3). Tamper-evidence comes from the **append-only `AUDIT#` records + restrictive IAM**, not storage-level locking. This keeps the filing system inside the S3/DynamoDB free tier (greenfield §13.1). _Upgrade path:_ enable S3 Object Lock later if audit-grade WORM ever becomes a hard requirement.

**RAG linkage.** Each `ACTIVE`, `SOURCE` document version is the unit of KB ingestion; every retrieval citation resolves through the catalogue to the exact S3 version + effective-date range. `DERIVED` documents are ingested into a separate, lower-priority KB data source and can never outrank a `SOURCE` citation (§8.5).

**Retention.** Records are kept **indefinitely** (body-corporate/statutory record-keeping). POPIA erasure is handled **case-by-case** via the DSAR flow (§13.10): it writes an `ERASED` audit event and removes only the personal-data document(s) for which no statutory retention applies.

### 8.5 Self-Improving Knowledge Base (Provenance-Gated)

Adapts the public RAW → WIKI → OUTPUTS + monthly-audit pattern (reviewed by the stakeholder), **hardened for a legal/financial corpus** where accuracy is load-bearing.

| Layer            | Role                                                                | Where it lives                                     | Authority                                    |
| ---------------- | ------------------------------------------------------------------- | -------------------------------------------------- | -------------------------------------------- |
| **RAW** (ingest) | Everything in, unorganised                                          | S3 originals + email attachments                   | n/a                                          |
| **SOURCE**       | Authoritative ground truth (Act, rules, minutes, financials)        | KB **primary** data source; `provenance=SOURCE`    | **Highest** — cited verbatim, version-pinned |
| **DERIVED Wiki** | AI-compiled topic pages with cross-links + citations back to SOURCE | KB **secondary** data source; `provenance=DERIVED` | Navigational only — never overrides SOURCE   |
| **OUTPUTS**      | AI answers/briefings/precedents fed back to compound                | `Precedents`/`Skills` (§7.3) + DERIVED             | Advisory; gated promotion                    |

**Provenance rule (hard).** Retrieval always prefers `SOURCE`; a `DERIVED` chunk may add context but can **never be the sole citation** for a legal/financial assertion (extends R5). `DERIVED` is **never auto-promoted** to `SOURCE`.

**Derived Wiki layer.** Unlike the video's "never hand-edit" wiki, ours is a _derived, citation-linked navigation layer_ a human **can** correct. It is regenerated from SOURCE, always links back to the exact source version, and is visibly labelled DERIVED in the UI.

**Compounding loop.** Confirmed corrections/precedents (§7.3) and useful briefings are saved back as `DERIVED`/Skills, deepening the corpus over time — but only **human-confirmed** items can influence authoritative interpretation (extends R7).

**Monthly health-check.** The **Knowledge Auditor** (Agent 10, §7.5) scans for broken provenance, stale/superseded docs still being cited, SOURCE-vs-SOURCE and DERIVED-vs-SOURCE contradictions, and coverage gaps, then emits a prioritized **action list** (§13.13) — the audit step from the video, made **advisory + human-gated**.

**Anti-model-collapse.** AI-generated `DERIVED` content is tagged and excluded from being treated as SOURCE; re-ingestion of AI output as ground truth is prohibited, and the auditor flags any DERIVED that contradicts SOURCE for repair/removal (R11).

### 8.6 Kanban Task Board

A lightweight, Jira-style board for the day-to-day running of the complex (maintenance, governance, compliance, finance). Tasks are a **separate entity** from `Cases` (which are email-driven issue files): a task need not originate from an email, and can optionally link to a Case, a Compliance event, or a Document.

#### Table: `Tasks` (Kanban Board)

```
PK: TASK#{task_id}
SK: META
  - title, description
  - column: BACKLOG | TODO | IN_PROGRESS | BLOCKED | DONE
  - rank: number                         # ordering within a column
  - category: Maintenance | Financial | Compliance | Governance | General   # swimlane
  - priority: HIGH | MEDIUM | LOW
  - assignee: USER#{id} | UNASSIGNED      # trustees
  - labels: string[]
  - due_date (optional)
  - origin: MANUAL | AGENT_SUGGESTED | FROM_CASE | FROM_MINUTES | FROM_COMPLIANCE
  - suggestion_state: PROPOSED | ACCEPTED # agent-suggested cards start PROPOSED
  - linked_case, linked_event, linked_document (optional)
  - created_by, created_at, updated_at

SK: COMMENT#{timestamp}
  - actor, body

SK: AUDIT#{timestamp}
  - event: CREATED | MOVED | ASSIGNED | EDITED | CLOSED
  - from_column, to_column, actor
```

**Board model.** A single board with columns **Backlog → To&nbsp;Do → In&nbsp;Progress → Blocked → Done** and optional swimlanes by category. Two creation paths, both reconciled with the human-in-the-loop principle:

1. **Agent-suggested** — pipeline agents (e.g., the Maintenance Specialist detecting "get 3 quotes") create a card in `PROPOSED` state; it sits in a **Suggested** tray and only enters the board when a trustee **accepts** it (mirrors the approval model; mitigates task-injection, R12).
2. **Trustee-created** — a trustee creates a card directly in the UI. The card is written to the `Tasks` store, which agents read as a tool, so the **agents become aware of it** once created and the Copilot/specialists can reference, comment on, or help progress it.

**RBAC.** `CHAIRPERSON`/`TRUSTEE` can create, move, assign, and close; `VIEWER` is read-only. External contractors/managing agents are **out of board scope** in this iteration — they continue to interact via email/Cases only.

---

## 9. Security & POPIA Compliance

### 9.1 POPIA Compliance Measures

| POPIA Principle                | Implementation                                                                                 |
| ------------------------------ | ---------------------------------------------------------------------------------------------- |
| **Accountability**             | Full audit trail; designated Information Officer (the chairperson)                             |
| **Processing Limitation**      | Only process data necessary for body corporate management                                      |
| **Purpose Specification**      | Data used solely for sectional title administration                                            |
| **Information Quality**        | RAG ensures responses are grounded in actual documents                                         |
| **Openness**                   | Privacy notice on dashboard; data subjects informed of processing                              |
| **Security Safeguards**        | Encryption at rest (AES-256) + in transit (TLS 1.3); PII redaction in logs                     |
| **Data Subject Participation** | Homeowners can request their data via the chairperson                                          |
| **Retention**                  | Indefinite for body corporate records (statutory requirement); personal data reviewed annually |

### 9.2 Security Architecture

```
┌─────────────────────────────────────────────────┐
│                 Security Layers                   │
├─────────────────────────────────────────────────┤
│ 1. Network: VPC, Security Groups, WAF on API GW │
│ 2. Identity: Cognito + MFA, IAM roles (least    │
│    privilege), service-linked roles              │
│ 3. Data at Rest: S3 (SSE-S3), DynamoDB (AWS     │
│    managed encryption), Bedrock KB (encrypted)   │
│ 4. Data in Transit: TLS 1.3 everywhere           │
│ 5. Application: PII redaction middleware,        │
│    input validation, rate limiting               │
│ 6. Logging: CloudWatch with PII filter Lambda    │
│    (strips names, emails, ID numbers before log) │
│ 7. Secrets: SSM Parameter Store (SecureString,   │
│    KMS-encrypted) for Gmail API credentials,     │
│    WhatsApp tokens — free vs Secrets Manager     │
└─────────────────────────────────────────────────┘
```

### 9.3 PII Redaction Strategy

```python
# PII Redaction middleware applied BEFORE any logging
import re

PII_PATTERNS = {
    "sa_id_number": r"\b\d{13}\b",
    "email": r"\b[\w.-]+@[\w.-]+\.\w+\b",
    "phone": r"\b0[0-9]{9}\b",
    "unit_number": r"\bUnit\s+\d+\b",  # Context-dependent
}

def redact_for_logging(text: str) -> str:
    """Redact PII before writing to CloudWatch logs."""
    for pii_type, pattern in PII_PATTERNS.items():
        text = re.sub(pattern, f"[REDACTED_{pii_type.upper()}]", text)
    return text
```

**Important**: PII is only redacted in **logs and observability**. The actual data in DynamoDB and S3 retains full PII (encrypted at rest) because it's needed for the system to function.

### 9.4 Authentication & Authorization

| Component    | Implementation                                                                        |
| ------------ | ------------------------------------------------------------------------------------- |
| User Auth    | AWS Cognito User Pool with MFA (TOTP)                                                 |
| RBAC Roles   | `CHAIRPERSON` (full access), `TRUSTEE` (view + limited approve), `VIEWER` (read-only) |
| API Auth     | Cognito JWT tokens validated at API Gateway                                           |
| Service Auth | IAM roles for Lambda/Fargate (no stored credentials)                                  |
| Gmail API    | OAuth 2.0 refresh token stored in SSM Parameter Store (SecureString)                  |
| WhatsApp     | API key in SSM Parameter Store (SecureString)                                         |

---

## 10. Cost Projections

### 10.1 Monthly Cost Estimate (Steady State)

Assumptions: ~80 emails/month, ~50 agent invocations/month, 5 active users, 50 documents in KB.

| Service                                            | Usage                                                        | Estimated Cost                   |
| -------------------------------------------------- | ------------------------------------------------------------ | -------------------------------- |
| **Bedrock - Claude 3 Haiku**                       | ~200K input + 50K output tokens/mo (classification)          | ~$0.10                           |
| **Bedrock - Claude 3.5 Sonnet**                    | ~500K input + 150K output tokens/mo (reasoning + drafting)   | ~$4.50                           |
| **Bedrock Knowledge Bases**                        | Storage + queries                                            | ~$2.00                           |
| **Titan Embedding v2**                             | ~100K tokens/mo (re-indexing)                                | ~$0.01                           |
| **Amazon Textract**                                | ~20 pages/mo (new doc ingestion)                             | ~$0.03                           |
| **Lambda**                                         | ~5000 invocations/mo                                         | Free tier                        |
| **Step Functions**                                 | ~500 state transitions/mo                                    | Free tier (4000/mo free)         |
| **DynamoDB**                                       | < 5GB, < 25 WCU/RCU                                          | Free tier                        |
| **S3**                                             | < 5GB storage + requests                                     | Free tier                        |
| **API Gateway**                                    | ~10K requests/mo                                             | Free tier (1M/mo free)           |
| **CloudFront**                                     | ~5GB transfer                                                | Free tier                        |
| **Cognito**                                        | < 50 users                                                   | Free tier                        |
| **SES**                                            | ~100 emails/mo                                               | Free tier (62K/mo free from EC2) |
| **SSM Parameter Store**                            | 3 SecureString params (Gmail, WhatsApp)                      | Free (standard tier)             |
| **CloudWatch**                                     | Basic logs                                                   | ~$1.00                           |
| **WhatsApp Business API**                          | ~100 messages/mo                                             | ~$5.00 (Meta conversation fees)  |
| **SQS**                                            | ~500 messages/mo                                             | Free tier                        |
| **Route 53**                                       | 1 hosted zone                                                | ~$0.50                           |
| **Bedrock - Trustee Copilot (mixed Haiku/Sonnet)** | ~300K input + 80K output tokens/mo (interactive Q&A)         | ~$2.50                           |
| **Bedrock - Knowledge Auditor (monthly batch)**    | ~150K input + 20K output tokens/mo (Haiku scan, rare Sonnet) | ~$0.30                           |
| **DynamoDB - Documents catalogue + Tasks board**   | within 25 GB free tier                                       | Free tier                        |
|                                                    |                                                              |                                  |
| **TOTAL ESTIMATED**                                |                                                              | **~$15.94/mo**                   |

> Copilot cost assumes prompt caching of system prompts and Haiku-first routing (escalate to Sonnet only for legal/financial reasoning). Interactive usage is the most variable line item; a per-user monthly token budget with graceful degradation keeps it bounded (see R2).

### 10.2 Cost Optimization Strategies

1. **Prompt caching** (Bedrock supports cached prompts): System prompts for each agent are cached, reducing input token costs by ~90% for repeated invocations
2. **Haiku for everything possible**: Only escalate to Sonnet when classification confidence is low or task requires complex reasoning
3. **Batch document processing**: Process new documents in bulk rather than one-at-a-time to minimize Textract calls
4. **Free tier maximization**: Stay within Lambda, DynamoDB, S3, API Gateway, Cognito, and SES free tiers
5. **Reserved capacity**: Not needed at this volume

### 10.3 Cost Scaling Triggers

| Trigger                | Impact                     | Action                               |
| ---------------------- | -------------------------- | ------------------------------------ |
| > 200 emails/month     | LLM costs increase         | Review autonomous handling expansion |
| > 100 documents        | KB costs increase slightly | Acceptable within budget             |
| > 50 users             | Cognito costs begin        | Unlikely for a single body corporate |
| Complex legal disputes | Sonnet token usage spikes  | Monitor per-case costs               |

---

## 11. Phased Delivery Plan

### Phase 1: MVP-α (Weeks 1–3) — Core Loop

**Goal**: Email in → AI processes → Human approves → Email out

| Week   | Deliverable                                                                                                                                                    |
| ------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Week 1 | AWS account setup, IaC foundation (Terraform), Gmail API OAuth, S3 + DynamoDB tables, Bedrock access enabled                                                   |
| Week 2 | Email ingestion Lambda (Gmail → SQS → parse → classify), Bedrock KB with 10 seed documents, Step Functions workflow (classify → analyze → draft → wait → send) |
| Week 3 | Minimal dashboard (Next.js): pending approvals list, approve/modify/reject buttons, basic case view. Cognito auth. Deploy via GitHub Actions.                  |

**Phase 1 delivers**: Q44 items 1, 3, 4, 5 (email ingestion, draft generation, approval workflow, dashboard UI)

### Phase 2: MVP-β (Weeks 4–6) — Intelligence Layer

**Goal**: Full RAG, case management, precedent learning

| Week   | Deliverable                                                                                                                                                    |
| ------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Week 4 | Full Bedrock KB ingestion pipeline (all 50 docs, OCR via Textract, versioning metadata), Agentic RAG implementation (multi-hop retrieval)                      |
| Week 5 | Case file system (DynamoDB design, case timeline view in dashboard, email threading), Precedent database (store decisions, similarity search for future cases) |
| Week 6 | All 8 agent prompts tuned, confidence scoring, holding response automation, reminder system (configurable SLA timers)                                          |

**Phase 2 delivers**: Q44 items 2, 6, 7 (RAG knowledge base, case file tracking, precedent database)

### Phase 3: Production Hardening (Weeks 7–9)

| Week   | Deliverable                                                                                                           |
| ------ | --------------------------------------------------------------------------------------------------------------------- |
| Week 7 | RBAC implementation (multi-trustee access), WhatsApp notification integration, DKIM/SPF/DMARC setup on Gmail domain   |
| Week 8 | Full dashboard views: compliance calendar, financial overview, maintenance tracker, unit directory, vendor management |
| Week 9 | Skill system v1 (few-shot storage from corrections), audit trail UI, historical backlog ingestion, end-to-end testing |

### Phase 4: Self-Improvement & Polish (Weeks 10–12)

| Week    | Deliverable                                                                                                                  |
| ------- | ---------------------------------------------------------------------------------------------------------------------------- |
| Week 10 | Dynamic skill updating (auto-evolve prompts from correction patterns), confidence calibration, performance metrics dashboard |
| Week 11 | Compliance calendar automation (auto-detect deadlines from ingested documents), dispute workflow encoding                    |
| Week 12 | Mobile optimization, load testing, security review, documentation, handover                                                  |

### Phase 5: Future (Post-MVP)

- Native mobile app (React Native or Flutter)
- Voice memo transcription for maintenance inspections
- Automated vendor quote comparison pipeline
- Integration with accounting software
- Trustee voting system with quorum tracking
- Annual CSOS return auto-generation

---

## 12. Open Questions & Risks

### Open Questions (Require Resolution)

| #   | Question                                                                      | Impact                | Suggested Resolution                                                                                         |
| --- | ----------------------------------------------------------------------------- | --------------------- | ------------------------------------------------------------------------------------------------------------ |
| OQ1 | Is Bedrock Knowledge Bases available in af-south-1?                           | Core architecture     | Verify; if not, use cross-region inference with data residency in af-south-1                                 |
| OQ2 | What is the exact Wilds Estate governance structure?                          | Agent 7 design        | Ingest estate constitution and rules as priority documents                                                   |
| OQ3 | What Gmail plan is in use (personal vs. Workspace)?                           | API access method     | Workspace needed for Pub/Sub push; personal requires polling                                                 |
| OQ4 | WhatsApp Business API — personal number or business number?                   | Notification setup    | Meta requires business verification for API access                                                           |
| OQ5 | How many units in the complex? How many trustees?                             | Scale assumptions     | Affects RBAC design and notification volume                                                                  |
| OQ6 | Is there an existing managing agent software system?                          | Potential integration | May need to parse reports from their system                                                                  |
| OQ7 | What constitutes "low-risk" for autonomous handling?                          | Autonomy rules        | Need explicit list: e.g., acknowledgements, meeting confirmations                                            |
| OQ8 | Legal opinion on AI-drafted correspondence without disclosure?                | Legal risk            | Consider consulting an attorney on liability implications                                                    |
| OQ9 | Which exact intents qualify for WhatsApp one-tap approval vs. dashboard-only? | Approval UX & risk    | Derive from the same low-risk list as OQ7; default everything to dashboard-only until the list is signed off |

### Risks

| #   | Risk                                                                                | Probability | Impact   | Mitigation                                                                                                                                                                             |
| --- | ----------------------------------------------------------------------------------- | ----------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| R1  | Bedrock service limitations in af-south-1                                           | Medium      | High     | Cross-region inference fallback                                                                                                                                                        |
| R2  | $20/mo LLM budget exceeded during high-activity periods (e.g., pre-AGM)             | Medium      | Medium   | Usage alerts, aggressive Haiku routing, monthly cap with graceful degradation                                                                                                          |
| R3  | Gmail API rate limits or push notification reliability                              | Low         | High     | SQS buffer, exponential backoff, periodic polling as fallback                                                                                                                          |
| R4  | Legal liability for AI-generated responses without disclosure                       | Medium      | High     | Full audit trail; chairperson reviews everything; consider legal opinion                                                                                                               |
| R5  | Hallucinated legal citations in agent responses                                     | Medium      | Critical | Agentic RAG with mandatory source grounding; confidence threshold; never cite without retrieval                                                                                        |
| R6  | POPIA complaint if homeowner data is mishandled                                     | Low         | High     | Encryption + redaction; data minimization; retention policy                                                                                                                            |
| R7  | Skill drift — agents evolve in undesirable directions                               | Low         | Medium   | Version control on skills; approval gate on skill mutations; rollback capability                                                                                                       |
| R8  | WhatsApp Business API approval delayed                                              | Medium      | Low      | Email notifications as primary; WhatsApp as enhancement                                                                                                                                |
| R9  | WhatsApp one-tap approval misused/spoofed for a substantive action                  | Medium      | High     | Restrict WhatsApp taps to the low-risk intent list only; substantive actions require authenticated dashboard; signed deep-links with short TTL and single-use token                    |
| R10 | Trustee Copilot answers confidently from stale/un-ingested documents                | Medium      | High     | Copilot retrieves with citations only; "I don't have a source for that" fallback; date-aware retrieval; never answers legal questions without a grounded citation                      |
| R11 | AI-maintained Wiki contradicts source / model collapse (self-improving KB degrades) | Medium      | High     | SOURCE vs DERIVED provenance (§8.5); DERIVED never sole citation and never auto-promoted; monthly Knowledge Auditor flags contradictions; AI output excluded from SOURCE re-ingestion  |
| R12 | Prompt-injection via inbound email creates spurious tasks/actions                   | Medium      | Medium   | Agent-suggested cards start `PROPOSED` and require trustee acceptance (§8.6); Suggested tray shows originating Case for verification; no agent action bypasses the human approval gate |

---

## 13. User Journeys & UX Specification

> This section closes the largest gap in the original design: the system was specified backend-first, but the MVP (Q44) lists the **dashboard UI** as non-negotiable. Below are the end-to-end human journeys. Each journey lists the **goal (the decision it drives)**, the **happy path**, and the **edge/empty/error states** so the UI can be built against an explicit contract rather than assumptions.

### 13.0 Information Architecture

Primary navigation (left rail), ordered by daily frequency of use:

1. **Inbox / Approval Queue** (default landing) — pending items needing a decision
2. **Cases** — full case files, searchable timeline view
3. **Board** — Kanban for day-to-day tasks (maintenance, governance, compliance, finance); includes the **Suggested** tray for agent-proposed cards
4. **Copilot** — conversational assistant (also available as a docked panel on every screen)
5. **Knowledge Base** — documents, versions, ingestion status, and the derived **Knowledge Wiki** (labelled DERIVED)
6. **Compliance Calendar** — deadlines, AGM, statutory returns
7. **Financials** — levy arrears, budget overview
8. **Maintenance** — request tracker, vendors/quotes
9. **Directory** — units, owners, trustees
10. **Audit Log** — immutable event history (read-only)
11. **Settings** — profile, notifications, trustees/RBAC, integrations

A persistent **global search** (cases, documents, people) and a **Copilot launcher** (`?` shortcut) are available on every screen.

### 13.1 Journey: First-Run Onboarding

**Goal**: Get a brand-new tenant from zero to a working approval loop, without an engineer.

**Happy path** (one-time setup wizard, gated to `CHAIRPERSON`):

1. Accept invite email → set password → enrol MFA (TOTP) in Cognito.
2. **Step 1 — Complex profile**: name, scheme number, number of units, registered address.
3. **Step 2 — Connect Gmail**: OAuth consent for the dedicated address (read + send scopes). System verifies and shows green "Connected".
4. **Step 3 — Seed the Knowledge Base**: drag-and-drop the founding documents (MR/CR, STSMA, latest financials). The KB ingestion journey (13.6) runs; the wizard shows live ingestion progress.
5. **Step 4 — Invite trustees**: add emails + assign roles (`TRUSTEE`/`VIEWER`).
6. **Step 5 — Autonomy & notifications**: confirm the low-risk intent list (OQ7), set per-priority SLA timers, choose notification channels (email always on; WhatsApp opt-in).
7. Finish → land on an **empty Approval Queue** with a guided empty state ("You're set up. New emails to _<address>_ will appear here for review.").

**Edge/empty states**:

- Gmail OAuth fails/expires → red banner on every screen with a one-click "Reconnect Gmail"; ingestion and sending pause, inbound buffered in SQS.
- KB seeded with zero documents → agents run in "low-confidence, no-grounding" mode and **every** draft is forced to manual review regardless of confidence (cold-start guard, see Appendix B note).

### 13.2 Journey: Daily Login & Triage

**Goal**: Let the chairperson clear the day's decisions in minutes.

**Happy path**:

1. Login (email + password + MFA). Session is short-lived JWT; "remember this device" reduces MFA prompts within policy.
2. Land on **Approval Queue**, sorted by priority then SLA-remaining. Each card shows: sender, unit, intent badge, one-line AI summary, **confidence chip** (colour-coded), and SLA countdown.
3. Low-confidence items (<0.50) are visually flagged at the top ("Needs your attention").
4. Click a card → **Approval Detail** (13.3).

**Edge states**:

- Empty queue → "All caught up" state with quick links to Cases and Compliance Calendar.
- An item's SLA is about to expire → amber/red countdown; if it expires while viewing, an inline notice explains the auto holding-response was sent (Appendix C) and the item moves to "Awaiting substantive reply".

### 13.3 Journey: Reviewing & Editing a Proposed Email

**Goal**: Approve, modify, or reject an agent-drafted action with a legally defensible trail. This makes Q24 concrete.

**Layout** (Approval Detail screen, three panes):

- **Left — Context**: the inbound email thread, parsed attachments, and the case timeline.
- **Centre — Proposed draft**: the editable response.
- **Right — Rationale**: which agents contributed, the **cited KB sources** (clickable, opens the exact document version), matched precedents, and the confidence breakdown (Appendix B).

**Actions on the draft**:

1. **Approve as-is** → send; case + audit updated; precedent stored.
2. **Inline edit** → rich-text editor; on save, a **diff** (original vs. edited) is captured. The edit is stored as a correction signal feeding the skill system (§7.3).
3. **Natural-language regenerate** → a feedback box ("Make this firmer and cite the 30-day arrears rule"); Draft Composer regenerates; the new draft is shown as a version with a version switcher. No silent overwrite.
4. **Reject** → requires a reason (dropdown + free text); the reason is a correction signal and is logged. Optionally "reject and take over manually" (13.5).
5. **Ask Copilot about this** → opens the docked Copilot pre-loaded with this case context (13.4).

**Guardrails**:

- Send is **disabled** until at least one source citation is present for any draft containing a legal/financial assertion (anti-hallucination, R5).
- Every approve/modify/reject writes an `ACTION` + `AUDIT` record (§8.1) including the original draft, final draft, editor identity, and timestamp.

### 13.4 Journey: Asking the Trustee Copilot

**Goal**: Resolve uncertainty about anything on screen without leaving the app. Directly answers your "how to engage a chatbot if I'm uncertain" requirement.

**Entry points**: dedicated **Copilot** nav item; docked panel on any screen (`?` shortcut); "Ask Copilot about this" from a case/approval/document.

**Happy path**:

1. User types a question ("Can the trustees approve this R45k repair without an AGM resolution?").
2. Copilot retrieves grounded context (KB + case files + precedents) and answers **with inline citations** to the exact document version.
3. Copilot can **propose an action** ("Draft a reply to the owner", "Open a maintenance case", "Add a reminder for the AGM"). Per the agreed scope, the Copilot is **agentic** — but any action it initiates is created in a **pending/draft state and enters the standard approval loop**; it never sends or commits irreversibly on its own.
4. Each proposed action appears as a confirmation card ("I'll create a draft reply — review it?") with Approve/Adjust/Cancel.

**Guardrails & edge states**:

- Read scope is bounded by the user's RBAC role (a `VIEWER` Copilot cannot surface another unit's PII beyond policy).
- If retrieval finds no grounded source → Copilot explicitly says so and offers to search the KB or flag a missing document, rather than guessing (R10).
- All Copilot-initiated actions are tagged `actor=USER#…via=copilot` in the audit trail.

### 13.5 Journey: Manual Override ("Take Over")

**Goal**: Let a human bypass the agents entirely while preserving the audit trail.

**Happy path**: From any case, **"Compose manually"** opens a blank/seeded editor; the human writes and sends directly. The action is logged as `actor=USER`, `action_type=MANUAL_DRAFT`, flagged as not AI-generated. Optionally "teach the agents" attaches the manual reply as a positive few-shot example (§7.3).

### 13.6 Journey: Managing the Knowledge Base

**Goal**: Keep the corpus current and **date-versioned** (Q9) via self-service. Per the agreed decision, **Chairperson + Trustees** can upload; re-index auto-triggers after effective-date tagging.

**Happy path**:

1. **Knowledge Base** → **Upload**: drag files (PDF/scanned/Word/Excel/text/image).
2. System detects type; scanned/image files are sent to **Textract**; extracted text is previewed for the user to sanity-check OCR quality.
3. **Tag metadata**: document title, category (rules, financials, minutes, insurance, correspondence…), and **effective-from / effective-until** dates. New versions of an existing document are linked into its version chain (§8.3).
4. On save, ingestion to Bedrock KB **auto-triggers**; the document shows a status pill: `Queued → Extracting → Indexing → Active` (or `Failed`).
5. Superseded versions remain queryable by date but are excluded from "current" retrieval.

**Edge/error states**:

- Low OCR confidence → document flagged "Review extraction"; user can correct text before indexing.
- Ingestion failure → actionable error + "Retry"; document stays `Draft`, never silently dropped.
- Overlapping effective-date ranges for the same document → validation error forces resolution (prevents ambiguous retrieval).

### 13.7 Journey: Adding Trustee Meeting Minutes

**Goal**: Turn minutes into queryable governance facts. Per the agreed decision, minutes get **special processing** beyond a normal KB document.

**Happy path**:

1. **Knowledge Base → Add Minutes** (or **Compliance Calendar → meeting → Attach minutes**).
2. Upload the minutes file; set meeting date, type (trustee/AGM/SGM), and attendees/quorum.
3. The pipeline (a) ingests the document as a versioned KB artifact, and (b) runs an **extraction pass** that proposes a structured list of **resolutions** and **action items** (owner, due date) for human confirmation — nothing is committed automatically.
4. User confirms/edits the extracted resolutions. Confirmed resolutions are written as **precedent/authority records** (linked to OQ7/Q33 authority boundaries) and action items create **compliance-calendar entries** with reminders.
5. Future agent decisions can cite "Resolution 2026-03 (AGM)" with a link back to the source minutes.

**Edge states**:

- Extraction finds no clear resolutions → user can add them manually.
- A resolution conflicts with an existing authority rule → flagged for review rather than auto-applied.

### 13.8 Journey: Notifications → Action (incl. WhatsApp)

**Goal**: Get the chairperson back to a decision quickly and safely.

**Happy path**:

1. New pending item → email (always) + WhatsApp (opt-in) notification.
2. **WhatsApp**: for items on the **low-risk intent list only**, an interactive button allows one-tap approval via a **signed, single-use, short-TTL deep-link** that still resolves the Step Functions task token server-side. Substantive items contain **no approve button** — only a deep-link that opens the authenticated dashboard (R9).
3. Email notifications always deep-link to the Approval Detail screen.

### 13.9 Cross-cutting UX states

| State                    | Required treatment                                                                                                    |
| ------------------------ | --------------------------------------------------------------------------------------------------------------------- |
| **Empty (cold start)**   | Guided empty states on every primary screen; cold-start guard forces manual review until KB + precedents exist        |
| **Loading**              | Skeleton screens; agent processing shows a live step indicator (Classifying → Analysing → Drafting)                   |
| **Error**                | Human-readable cause + a recovery action; never a dead-end; inbound work is buffered, never lost                      |
| **Offline/degraded LLM** | Banner + queue continues to accept email; drafting resumes when Bedrock is available                                  |
| **Permission denied**    | RBAC-aware hiding + explicit "you don't have access" rather than a blank screen                                       |
| **Accessibility**        | WCAG 2.1 AA: keyboard nav, focus order, colour-contrast on confidence chips (never colour-only), screen-reader labels |

### 13.10 POPIA Data-Subject-Access-Request (DSAR) flow

**Goal**: Honour the Section 9.1 promise that owners can request their data. From **Directory → owner → "Export/Erase data"**, the chairperson generates a PII bundle (cases, emails, documents referencing the subject) or initiates a logged erasure where no statutory retention applies. Every DSAR action is audited.

### 13.11 Wireframe-Level Component Specifications

> Screen-by-screen component lists for the two highest-value surfaces (Approval Detail, §13.3; and the Trustee Copilot panel, §13.4). These define the build contract for the frontend; each component lists its data source and key states. ASCII layouts are indicative, not pixel-precise.

#### 13.11.1 Approval Detail Screen

**Layout (desktop, three-pane; collapses to stacked tabs on mobile per Q20):**

```
┌───────────────────────────────────────────────────────────────────────────────┐
│  TopBar: ‹Back to Queue │ Case #1042 · Roof leak · Unit 14 │ [HIGH] [SLA 1h42m] │
│          {global search}                              {user avatar / role}       │
├──────────────────────┬───────────────────────────────┬────────────────────────┤
│  LEFT — Context       │  CENTRE — Proposed Draft       │  RIGHT — Rationale      │
│ ┌──────────────────┐ │ ┌───────────────────────────┐ │ ┌────────────────────┐ │
│ │ Thread viewer     │ │ │ Subject (editable)         │ │ │ Confidence 0.87 ▓▓░ │ │
│ │  inbound ▸ prior  │ │ │ ─────────────────────────  │ │ │  breakdown ▸        │ │
│ │  replies          │ │ │ Rich-text body editor       │ │ ├────────────────────┤ │
│ ├──────────────────┤ │ │  (inline edit, tracked)     │ │ │ Contributing agents │ │
│ │ Attachments        │ │ │                            │ │ │  • Maintenance Spec │ │
│ │  • quote.pdf (OCR) │ │ │                            │ │ │  • Financial Analyst│ │
│ ├──────────────────┤ │ │                            │ │ │  • Legal Analyst    │ │
│ │ Case timeline      │ │ └───────────────────────────┘ │ ├────────────────────┤ │
│ │  (collapsible)     │ │ Draft version: ‹ v2/3 ›        │ │ Cited sources       │ │
│ └──────────────────┘ │ ┌───────────────────────────┐ │ │  • CR Rule 29 (2023)│ │
│                       │ │ [Approve & Send]           │ │ │  • Fin Stmt FY25 p4 │ │
│                       │ │ [Regenerate…] [Reject]     │ │ ├────────────────────┤ │
│                       │ │ [Compose manually]         │ │ │ Matched precedents  │ │
│                       │ │ [Ask Copilot about this]   │ │ │  • PR-2025-08 (0.81)│ │
│                       │ └───────────────────────────┘ │ └────────────────────┘ │
└──────────────────────┴───────────────────────────────┴────────────────────────┘
```

**Component inventory:**

| #   | Component                                                   | Data source                  | Key states / notes                                                     |
| --- | ----------------------------------------------------------- | ---------------------------- | ---------------------------------------------------------------------- |
| A1  | TopBar (case id, intent badge, priority, **SLA countdown**) | `Cases` META                 | SLA chip: green/amber/red; expired → "Holding response sent"           |
| A2  | Global search                                               | search index                 | keyboard `/` focus                                                     |
| A3  | Thread viewer (inbound + prior replies, threaded)           | `Cases` EMAIL#\* + S3 bodies | quoted-text collapse; Afrikaans badge if detected                      |
| A4  | Attachment list (filename, type, OCR badge)                 | `Cases` attachments / S3     | click → preview; "Review extraction" if low OCR confidence             |
| A5  | Case timeline (collapsible)                                 | `Cases` AUDIT#_/ACTION#_     | newest-first; filter by event type                                     |
| A6  | Subject field (editable)                                    | current ACTION draft         | dirty-state indicator                                                  |
| A7  | Rich-text body editor (**inline edit**, tracked diff)       | current ACTION draft         | autosave to draft; diff captured on save (§7.3)                        |
| A8  | Draft version switcher `‹ v/n ›`                            | ACTION versions              | regenerate adds a version; no silent overwrite                         |
| A9  | **Approve & Send**                                          | —                            | **disabled** until ≥1 citation present for legal/financial claims (R5) |
| A10 | **Regenerate…** (NL feedback box)                           | Draft Composer               | opens modal: free-text instruction → new version                       |
| A11 | **Reject** (reason dropdown + free text)                    | —                            | reason required; logged as correction signal                           |
| A12 | **Compose manually**                                        | —                            | manual override (§13.5); tags `MANUAL_DRAFT`                           |
| A13 | **Ask Copilot about this**                                  | Copilot                      | opens docked panel pre-loaded with case context                        |
| A14 | Confidence widget (score + breakdown)                       | Appendix B                   | expandable: rag/source/precedent/self weights                          |
| A15 | Contributing-agents list                                    | ACTION metadata              | per-agent expand → its analysis                                        |
| A16 | **Cited sources** (clickable, version-aware)                | `context_retrieved`          | opens exact document version; relevance score shown                    |
| A17 | Matched precedents (with similarity)                        | `Precedents`                 | click → precedent detail                                               |

**Empty/error states:** no citations yet → A9 disabled with tooltip ("Add a source to enable sending"); regenerate failure → inline retry, prior version preserved; concurrent-edit conflict (two trustees) → optimistic-lock warning, last-writer-must-merge.

#### 13.11.2 Trustee Copilot Panel

**Layout (docked right-rail, ~380px; full-screen on mobile):**

```
┌─────────────────────────────────────┐
│ Copilot            context: Case#1042│  ← C1 header + context chip
│  scope: Maintenance · Unit 14    ✕   │
├─────────────────────────────────────┤
│  ▸ Conversation transcript           │  ← C3 message list
│   ┌─────────────────────────────────┐│
│   │ You: Can we approve R45k repair  ││  ← user bubble
│   │ without an AGM resolution?       ││
│   └─────────────────────────────────┘│
│   ┌─────────────────────────────────┐│
│   │ Copilot: Trustees may authorise  ││  ← assistant bubble
│   │ this under MR 29(...)  [1][2]    ││     with citation chips
│   │                                  ││
│   │  ▸ Proposed action card          ││  ← C5 action card
│   │   "Draft reply to owner"         ││
│   │   [Review draft] [Adjust] [Cancel]│
│   └─────────────────────────────────┘│
│   ▸ Sources [1] CR Rule 29 (2023)    │  ← C4 citations
│            [2] Fin Stmt FY25 p4      │
├─────────────────────────────────────┤
│  [ Ask anything…            ] [Send] │  ← C6 composer
│  suggested: "Show levy arrears" …    │  ← C7 suggestion chips
└─────────────────────────────────────┘
```

**Component inventory:**

| #   | Component                                           | Data source                                       | Key states / notes                                                                               |
| --- | --------------------------------------------------- | ------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| C1  | Header + **context chip**                           | active screen                                     | chip shows what the Copilot can "see" (case/doc/none); removable                                 |
| C2  | Scope/RBAC indicator                                | Cognito role                                      | reflects read-scope bound to the user's role                                                     |
| C3  | Conversation transcript                             | session (ephemeral)                               | streaming tokens; per-turn copy; not persisted as PII beyond policy                              |
| C4  | **Citation chips / sources list**                   | `query_knowledge_base` results                    | each links to exact document version; **no answer to legal/financial Q without ≥1 source** (R10) |
| C5  | **Proposed action card** (Review / Adjust / Cancel) | `propose_draft` / `open_case` / `create_reminder` | action created in **pending/draft**, enters approval loop; never auto-commits                    |
| C6  | Composer (input + send)                             | —                                                 | `?` global shortcut focuses it                                                                   |
| C7  | Suggested prompts                                   | context-aware                                     | seeded by current screen (e.g., "Why this recommendation?")                                      |
| C8  | "No grounded source" fallback notice                | retrieval miss                                    | offers "Search KB" or "Flag missing document" instead of guessing                                |
| C9  | Audit indicator                                     | audit service                                     | subtle note that Copilot-initiated actions are logged `via=copilot`                              |

**States:** thinking (skeleton + step hint); retrieval-miss (C8 fallback); permission-denied (explains role limit, no blank); offline LLM (banner, input disabled, queued question retried).

#### 13.11.3 Knowledge Base Management Screen

**Layout (list + slide-over upload drawer; maps to journeys §13.6 and §13.7):**

```
┌───────────────────────────────────────────────────────────────────────────────┐
│  Knowledge Base            {global search}        [ + Upload ] [ + Add Minutes ] │
│  Filters: [Category ▾] [Status ▾] [Effective on: date ▾]   23 documents          │
├───────────────────────────────────────────────────────────────────────────────┤
│  Title                     Category     Version  Effective range    Status       │
│  ───────────────────────────────────────────────────────────────────────────── │
│  Conduct Rules             rules        v2       2023-08 → current  ● Active      │
│  Management Rules          rules        v1       2020-01 → current  ● Active      │
│  Financial Stmt FY25       financials   v1       2025-03 → current  ◐ Indexing    │
│  AGM Minutes 2026-03       minutes      v1       2026-03 → —        ● Active   ⚖  │
│  Insurance Schedule        insurance    v3       2026-01 → current  ⚠ Review OCR  │
│  Roof Quote (Acme)         correspond.  v1       2026-06 → —        ✕ Failed  ↻    │
│  …                                                                               │
├──────────────────────────────────────────┬────────────────────────────────────┤
│  SLIDE-OVER: Upload / Edit document        │  (opens on +Upload or row click)   │
│ ┌────────────────────────────────────────┐│                                     │
│ │ Drop files or browse  (PDF/docx/xlsx/img)││  D3 dropzone                       │
│ │ ───────────────────────────────────────││                                     │
│ │ OCR preview (scanned/img)   confidence ▓││  D4 extraction preview (editable)  │
│ │  "…extracted text shown here…"          ││                                     │
│ │ ───────────────────────────────────────││                                     │
│ │ Title  [__________]  Category [rules ▾] ││  D5 metadata form                  │
│ │ Effective from [____]  until [____/none]││  D6 effective-date range           │
│ │ New version of: [existing doc ▾ / none] ││  D7 version-chain linker           │
│ │ ───────────────────────────────────────││                                     │
│ │ [ Save & Ingest ]   [ Save as Draft ]   ││  D8 actions                        │
│ └────────────────────────────────────────┘│                                     │
└──────────────────────────────────────────┴────────────────────────────────────┘
```

**Component inventory:**

| #   | Component                                                                   | Data source                 | Key states / notes                                                                                                                       |
| --- | --------------------------------------------------------------------------- | --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | Toolbar (**+Upload**, **+Add Minutes**)                                     | —                           | +Add Minutes opens the minutes variant (§13.7) with attendees/quorum + resolution-extraction step; both gated to `CHAIRPERSON`/`TRUSTEE` |
| D2  | Filters (category, status, **effective-on date**)                           | document index              | "Effective on" date filter previews which version was live on a chosen date (Q9)                                                         |
| D3  | Document table (title, category, version, effective range, **status pill**) | `documents/*/metadata.json` | status: `Draft / Queued / Extracting / Indexing / Active / Failed`; ⚖ badge marks minutes with extracted resolutions; row click → edit  |
| D4  | Dropzone (multi-file)                                                       | —                           | type-detects; routes scanned/image to Textract                                                                                           |
| D5  | **OCR/extraction preview** (editable text + confidence bar)                 | Textract output             | low confidence → "Review extraction" gate before ingest; user can correct text                                                           |
| D6  | Metadata form (title, category)                                             | —                           | category drives retrieval routing                                                                                                        |
| D7  | **Effective-from / -until** range picker                                    | —                           | validates against the version chain; overlapping ranges → hard validation error (prevents ambiguous retrieval)                           |
| D8  | **Version-chain linker** ("new version of…")                                | `documents`                 | links into §8.3 version model; auto-sets predecessor's `effective_until`                                                                 |
| D9  | **Save & Ingest**                                                           | KB ingestion pipeline       | auto-triggers re-index; row shows live status pills; never silently drops on failure → `Retry` (↻)                                       |
| D10 | Save as Draft                                                               | —                           | stores without indexing; excluded from retrieval until ingested                                                                          |
| D11 | Version history drawer (per document)                                       | `documents` versions        | shows all versions, who uploaded, ingest state; supersede/rollback                                                                       |
| D12 | Minutes extras (attendees, quorum, **resolutions/action-items table**)      | extraction pass             | confirm/edit extracted resolutions → precedent/authority records + calendar reminders (§13.7)                                            |

**Empty/error states:** empty corpus → guided "Seed your Knowledge Base" CTA (ties to onboarding §13.1 cold-start guard); ingestion failure → inline error + `Retry`, document stays `Draft`; overlapping effective dates → blocking validation; Textract low confidence → `Review OCR` flag must be cleared before `Save & Ingest` is enabled.

### 13.12 Journey: Day-to-Day Task Board (Kanban)

**Goal**: Run the complex's operational to-do list in a familiar Jira-style Kanban, with agents and trustees working the same board (§8.6).

**Happy path**:

1. **Board** → a single board with columns **Backlog · To Do · In Progress · Blocked · Done**; optional swimlanes by category (Maintenance/Financial/Compliance/Governance/General).
2. **Create a task** (trustee): `+ New task` → title, description, category, priority, assignee, optional due date and links (Case/Compliance event/Document). On save it appears in the chosen column and is immediately **visible to the agents** (they read the `Tasks` store as a tool), so the Copilot can reference or help progress it.
3. **Accept a suggested task** (agent → human): cards proposed by pipeline agents land in a **Suggested** tray as `PROPOSED`. The trustee reviews and **Accepts** (card enters Backlog/To Do) or **Dismisses** (logged). Nothing an agent proposes appears on the board proper until accepted.
4. **Progress work**: drag a card across columns; each move writes a `MOVED` audit record (from/to column, actor). Assign, comment, relabel, set due date.
5. **Close**: move to **Done**; closing a task linked to a Case/Compliance event posts a back-reference on that record.

**Edge/empty states**:

- Empty board → guided empty state ("Add your first task, or review agent suggestions").
- A `BLOCKED` card requires a short blocker reason (surfaced on the card).
- A suggested task whose source email looks like prompt injection (R12) is still inert until a human accepts it; the Suggested tray shows the originating Case for verification.
- `VIEWER` role sees a read-only board (no drag, no create).

### 13.13 Journey: Monthly Knowledge Audit Review

**Goal**: Keep the corpus trustworthy via the scheduled Knowledge Auditor (Agent 10, §7.5) without letting AI silently rewrite authoritative content.

**Happy path**:

1. On schedule (monthly) the Auditor runs and produces an **audit report** with a prioritized **action list**; the chairperson is notified.
2. **Knowledge Base → Audit** shows the report grouped by finding type: **Broken provenance**, **Stale/superseded but still cited**, **Contradictions** (SOURCE-vs-SOURCE, DERIVED-vs-SOURCE), **Coverage gaps**.
3. Each finding is an actionable row with a **proposed fix** (relink to current version, supersede, regenerate a Wiki page, request a missing document) and **Approve / Edit / Dismiss** controls.
4. **Approving** a fix executes it under the human's identity (re-index, relink, supersede) and logs it; approving a "request missing document" creates a **Board** task (§13.12).
5. Confirmed outcomes feed the compounding loop (§8.5): the Wiki improves, gaps become tasks, and DERIVED-vs-SOURCE contradictions are repaired.

**Guardrails & edge states**:

- The Auditor is **advisory**: no SOURCE document is ever edited automatically; every fix is human-approved.
- A flagged contradiction between two SOURCE documents is escalated for human/legal judgement, never auto-resolved.
- On-demand re-run is available (e.g., right after a big document drop), bounded by the same token caps as other agents.

---

## 14. Testing & Agent Evaluation Strategy

> Added to satisfy the hard guardrail that no behaviour ships without verification, and to directly mitigate R5 (hallucinated citations), rated _Critical_. "Good" is defined **before** implementation per the Verifier layer.

### 14.1 Test Pyramid

| Layer           | Scope                                                                                                               | Tooling                                           | Gate                                                        |
| --------------- | ------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------- | ----------------------------------------------------------- |
| **Unit**        | Pure functions: PII redaction (§9.3), confidence scoring (App. B), date-version selection, intent schema validation | `pytest` (Lambdas), `vitest`/Jest (Next.js)       | Block merge on fail; coverage threshold on critical modules |
| **Integration** | Email parse → classify → KB retrieve → draft; Step Functions task-token approve/timeout; Gmail send threading       | LocalStack / Step Functions Local; mocked Bedrock | Required in CI                                              |
| **Contract**    | API Gateway ↔ dashboard request/response schemas; agent input/output JSON contracts                                | schema snapshot tests                             | Required in CI                                              |
| **End-to-end**  | Seeded inbox → approval in dashboard → outbound email; KB upload → queryable by date                                | Playwright against an ephemeral stack             | Pre-release                                                 |
| **Security**    | IAM least-privilege checks, dependency scan, secret scan, container scan                                            | `tfsec`/`checkov`, SCA, Trivy                     | Required in CI                                              |

### 14.2 Agent Evaluation Harness (the critical addition)

A dedicated **golden-set eval** runs in CI on every change to an agent prompt, skill, or retrieval config:

- **Golden dataset**: a versioned set of representative emails (maintenance, levy dispute, AGM notice, legal notice, Afrikaans sample, scanned-PDF sample) with **expected intents, expected source documents, and acceptable answer rubrics**.
- **Grounding / faithfulness metric**: every legal/financial assertion in an output must map to a retrieved source. Outputs that assert without a citation **fail the build** (enforces R5).
- **Citation-accuracy metric**: cited Act sections / clauses must exist in the retrieved chunk (no fabricated section numbers).
- **Classification accuracy**: intent + priority vs. labels; regression alert if it drops.
- **Date-correctness**: time-scoped questions must retrieve the version effective on that date.
- **LLM-as-judge** (Bedrock, separate model) scores tone/helpfulness against the rubric; low scores flagged, not auto-blocking.
- **Skill-mutation gate**: when the skill system (§7.3) proposes an auto-update, it must pass the golden-set eval **before** the new skill version becomes active (mitigates R7 skill drift).

### 14.3 Pre-Execution "Definition of Good"

| Dimension                                       | Threshold (initial)       |
| ----------------------------------------------- | ------------------------- |
| Intent classification accuracy                  | ≥ 90% on golden set       |
| Grounded-citation rate (legal/financial claims) | 100% (hard gate)          |
| Fabricated-citation rate                        | 0% (hard gate)            |
| Date-version retrieval correctness              | 100% on date-scoped cases |
| P95 email-to-draft latency                      | < 60s                     |
| Unit-test coverage (PII, scoring, versioning)   | ≥ 90%                     |

### 14.4 Production verification (external signals)

- **Human-correction rate** per intent/skill is tracked; a rising correction rate auto-opens a review task (the system grading itself against reality).
- **Confidence calibration**: periodically compare predicted confidence vs. actual approval/modification outcomes; recalibrate weights in Appendix B.
- **Shadow mode** for new agents/skills: run in parallel without sending, compare against the human decision, promote only when within tolerance.

---

## 15. Reviewer Instructions

### For Opus Reviewers

This document is submitted for peer review by two independent Claude Opus instances. Please evaluate against the following criteria:

#### Review Checklist

1. **Completeness**: Are there gaps in the requirements that weren't addressed? Missing edge cases?
2. **Consistency**: Do any architectural decisions contradict the stated constraints (especially the $45/mo budget)?
3. **Feasibility**: Is the phased plan realistic? Are there technical impossibilities or near-impossibilities?
4. **Security**: Are there POPIA compliance gaps? Security vulnerabilities in the proposed architecture?
5. **Scalability**: Will this architecture handle growth (more units, more documents, more trustees)?
6. **Legal Risk**: Are there concerns about the AI-without-disclosure approach? Authority boundaries?
7. **Cost Accuracy**: Are the cost projections realistic? Any hidden costs not accounted for?
8. **Agent Design**: Are 8 agents appropriate, or is there over/under-decomposition? Will the skill system work within budget?
9. **Ambiguity**: Flag any areas where the requirements are unclear or could be interpreted multiple ways.
10. **Alternative Approaches**: Where a better approach exists for the same constraint profile, suggest it.

#### Review Format

Please structure your review as:

```
## [DOMAIN]: [Finding Title]
**Severity**: Critical | Major | Minor | Suggestion
**Finding**: [Description of the issue]
**Recommendation**: [Proposed fix or alternative]
```

#### Key Constraints to Validate Against

- Total budget: ≤ $45/month (LLM + infra)
- Data residency: South Africa (af-south-1) for all stored data
- LLM data: Must not leave AWS account (Bedrock only)
- Approval: Every substantive action requires individual human approval
- Audit: Full trail for legal defensibility
- PII: Never in logs; encrypted at rest in storage

---

## Appendix A: Gmail Integration Technical Detail

### Option 1: Google Workspace with Pub/Sub Push (Recommended)

```
Gmail → Google Cloud Pub/Sub → Push to HTTPS endpoint (API Gateway)
  → Lambda ingestion handler
```

Requirements:

- Google Workspace account (not personal Gmail)
- Google Cloud project for Pub/Sub
- Domain verification
- OAuth 2.0 service account or user consent

### Option 2: Polling (Fallback)

```
EventBridge Scheduler (every 5 min) → Lambda
  → Gmail API: list messages since last check
  → Process new messages
```

Simpler but adds 0–5 min latency.

### DKIM/SPF/DMARC Setup

For the sending domain:

1. **SPF**: Add `include:_spf.google.com` to DNS TXT record
2. **DKIM**: Generate in Google Admin → add TXT record to DNS
3. **DMARC**: Add `_dmarc` TXT record with policy (start with `p=none` for monitoring)

---

## Appendix B: Confidence Scoring Model

````python
def calculate_confidence(agent_response: dict) -> float:
    """
    Confidence is derived from:
    1. RAG retrieval relevance scores (0-1)
    2. Number of sources found vs. expected
    3. Precedent similarity score (if precedent exists)
    4. Agent self-assessment (prompted to rate 1-10)
    """
    rag_score = agent_response.get("avg_retrieval_relevance", 0.5)
    source_coverage = min(agent_response.get("sources_found", 0) / 3, 1.0)
    precedent_score = agent_response.get("precedent_similarity", 0.0)
    self_assessment = agent_response.get("self_confidence", 5) / 10

    # Weighted combination
    confidence = (
        0.35 * rag_score +
        0.25 * source_coverage +
        0.20 * precedent_score +
        0.20 * self_assessment
    )

    return round(confidence, 2)

# Thresholds
AUTONOMOUS_THRESHOLD = 0.85  # Can auto-send if low-risk AND above this
FLAG_THRESHOLD = 0.50        # Below this, prominently flagged in dashboard```

**Cold-start guard**: precedent similarity is `0.0` until the precedent database is populated, which depresses confidence on day 1. While the Knowledge Base or precedent set is empty (first-run, see §13.1), the system **forces manual review for every item regardless of computed confidence** and never auto-sends. The autonomous path activates only once grounding sources and a minimum precedent count exist.

---

## Appendix C: Holding Response Template

When approval SLA expires, the system auto-sends:

````

Subject: Re: {original_subject}

Dear {sender_name},

Thank you for your correspondence dated {date}.

This is to confirm that your {intent_friendly_name} has been received and is being reviewed by the trustees. We will respond substantively within {expected_sla} business days.

If this matter is urgent, please indicate so in a reply to this email.

Kind regards,
{chairperson_name}
Chairperson — {body_corporate_name}

```

---

*End of Document*
```
