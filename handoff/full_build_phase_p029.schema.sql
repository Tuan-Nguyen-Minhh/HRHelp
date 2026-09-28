--
-- PostgreSQL database dump
--

\restrict QLi0tv0kBb287fVgTmRVu9NRhBRiYRPW1XpUnP2ezsU9lkNTxM1U1v52JuhK2CQ

-- Dumped from database version 16.15 (Debian 16.15-1.pgdg12+2)
-- Dumped by pg_dump version 16.15 (Debian 16.15-1.pgdg12+2)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: btree_gist; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS btree_gist WITH SCHEMA public;


--
-- Name: EXTENSION btree_gist; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION btree_gist IS 'support for indexing common datatypes in GiST';


--
-- Name: vector; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;


--
-- Name: EXTENSION vector; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION vector IS 'vector data type and ivfflat and hnsw access methods';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: agent_retrievals; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.agent_retrievals (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    agent_run_id uuid NOT NULL,
    chunk_id uuid NOT NULL,
    score double precision,
    rank integer NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT ck_agent_retrievals_rank CHECK ((rank > 0))
);


ALTER TABLE public.agent_retrievals OWNER TO postgres;

--
-- Name: agent_runs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.agent_runs (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    conversation_id uuid NOT NULL,
    message_id uuid NOT NULL,
    output_message_id uuid,
    status character varying(50) DEFAULT 'PENDING'::character varying NOT NULL,
    model character varying(100),
    model_version character varying(100),
    prompt_tokens integer,
    completion_tokens integer,
    started_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    completed_at timestamp without time zone,
    error text,
    CONSTRAINT ck_agent_runs_status CHECK (((status)::text = ANY ((ARRAY['PENDING'::character varying, 'RUNNING'::character varying, 'SUCCEEDED'::character varying, 'FAILED'::character varying])::text[])))
);


ALTER TABLE public.agent_runs OWNER TO postgres;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


ALTER TABLE public.alembic_version OWNER TO postgres;

--
-- Name: case_access; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.case_access (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    case_id uuid NOT NULL,
    user_id uuid NOT NULL,
    access_level character varying(50) NOT NULL,
    granted_by uuid,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT ck_case_access_access_level CHECK (((access_level)::text = ANY ((ARRAY['VIEW'::character varying, 'REVIEW'::character varying])::text[])))
);


ALTER TABLE public.case_access OWNER TO postgres;

--
-- Name: case_drafts; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.case_drafts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    case_id uuid NOT NULL,
    recommendation_id uuid,
    draft_type character varying(50) NOT NULL,
    title character varying(255) NOT NULL,
    content text NOT NULL,
    status character varying(50) DEFAULT 'DRAFT'::character varying NOT NULL,
    created_by uuid NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT ck_case_drafts_draft_type CHECK (((draft_type)::text = ANY ((ARRAY['MINUTES'::character varying, 'EXPLANATION_REQUEST'::character varying, 'DECISION'::character varying, 'TICKET'::character varying])::text[]))),
    CONSTRAINT ck_case_drafts_status CHECK (((status)::text = ANY ((ARRAY['DRAFT'::character varying, 'PENDING_REVIEW'::character varying, 'APPROVED'::character varying, 'REJECTED'::character varying, 'ISSUED'::character varying])::text[])))
);


ALTER TABLE public.case_drafts OWNER TO postgres;

--
-- Name: case_facts; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.case_facts (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    case_id uuid NOT NULL,
    fact_key character varying(100) NOT NULL,
    fact_value text,
    source_message_id uuid,
    confirmed boolean DEFAULT false NOT NULL,
    confirmed_by uuid,
    confirmed_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT ck_case_facts_confirmed CHECK ((((confirmed = false) AND (confirmed_by IS NULL) AND (confirmed_at IS NULL)) OR ((confirmed = true) AND (confirmed_by IS NOT NULL) AND (confirmed_at IS NOT NULL))))
);


ALTER TABLE public.case_facts OWNER TO postgres;

--
-- Name: case_violations; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.case_violations (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    case_id uuid NOT NULL,
    violation_type_id uuid NOT NULL,
    evidence text,
    severity character varying(50),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT ck_case_violations_severity CHECK (((severity IS NULL) OR ((severity)::text = ANY ((ARRAY['LOW'::character varying, 'MEDIUM'::character varying, 'HIGH'::character varying, 'CRITICAL'::character varying])::text[]))))
);


ALTER TABLE public.case_violations OWNER TO postgres;

--
-- Name: cases; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.cases (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    case_code character varying(100) NOT NULL,
    created_by uuid NOT NULL,
    employee_code character varying(100),
    employee_name character varying(255),
    description text,
    incident_date date,
    status character varying(50) DEFAULT 'OPEN'::character varying NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT ck_cases_status CHECK (((status)::text = ANY ((ARRAY['OPEN'::character varying, 'NEED_INFO'::character varying, 'ANALYZED'::character varying, 'PENDING_LEGAL'::character varying, 'APPROVED'::character varying, 'REJECTED'::character varying, 'DECIDED'::character varying, 'CLOSED'::character varying])::text[])))
);


ALTER TABLE public.cases OWNER TO postgres;

--
-- Name: conversations; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.conversations (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    case_id uuid,
    title character varying(255),
    status character varying(50) DEFAULT 'ACTIVE'::character varying NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT ck_conversations_status CHECK (((status)::text = ANY ((ARRAY['ACTIVE'::character varying, 'CLOSED'::character varying])::text[])))
);


ALTER TABLE public.conversations OWNER TO postgres;

--
-- Name: disciplinary_decisions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.disciplinary_decisions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    case_id uuid NOT NULL,
    draft_id uuid,
    decision_code character varying(100) NOT NULL,
    sanction_type character varying(50) NOT NULL,
    summary text NOT NULL,
    legal_basis text,
    storage_path character varying(1000),
    issued_by uuid NOT NULL,
    issued_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    is_precedent boolean DEFAULT false NOT NULL,
    precedent_summary text,
    embedding public.vector(1024),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT ck_disciplinary_decisions_precedent_summary CHECK (((NOT is_precedent) OR (precedent_summary IS NOT NULL))),
    CONSTRAINT ck_disciplinary_decisions_sanction_type CHECK (((sanction_type)::text = ANY ((ARRAY['WARNING'::character varying, 'REPRIMAND'::character varying, 'WAGE_POSTPONEMENT'::character varying, 'DEMOTION'::character varying, 'DISMISSAL'::character varying, 'TERMINATION'::character varying])::text[])))
);


ALTER TABLE public.disciplinary_decisions OWNER TO postgres;

--
-- Name: document_chunks; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.document_chunks (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    document_id uuid NOT NULL,
    chunk_index integer NOT NULL,
    content text NOT NULL,
    page_number integer,
    section character varying(255),
    section_title character varying(255),
    article character varying(50),
    clause character varying(50),
    point character varying(50),
    metadata jsonb,
    embedding public.vector(1024),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


ALTER TABLE public.document_chunks OWNER TO postgres;

--
-- Name: documents; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.documents (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    policy_version_id uuid NOT NULL,
    file_name character varying(255) NOT NULL,
    file_type character varying(100),
    storage_path character varying(1000),
    source character varying(255),
    content_hash character varying(64),
    page_count integer,
    ingest_status character varying(50) DEFAULT 'UPLOADED'::character varying NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT ck_documents_ingest_status CHECK (((ingest_status)::text = ANY ((ARRAY['UPLOADED'::character varying, 'CHUNKED'::character varying, 'EMBEDDED'::character varying, 'FAILED'::character varying])::text[])))
);


ALTER TABLE public.documents OWNER TO postgres;

--
-- Name: legal_chunk_embeddings; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.legal_chunk_embeddings (
    chunk_id character varying(128) NOT NULL,
    content_sha256 character(64) NOT NULL,
    model character varying(64) NOT NULL,
    dimensions integer NOT NULL,
    header_context text,
    text text NOT NULL,
    embedding public.vector(1024) NOT NULL,
    search_tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple'::regconfig, ((COALESCE(header_context, ''::text) || ' '::text) || COALESCE(text, ''::text)))) STORED,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_legal_chunk_embeddings_dimensions CHECK ((dimensions = 1024)),
    CONSTRAINT ck_legal_chunk_embeddings_model_not_empty CHECK (((model)::text <> ''::text))
);


ALTER TABLE public.legal_chunk_embeddings OWNER TO postgres;

--
-- Name: legal_chunk_references; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.legal_chunk_references (
    ref_id integer NOT NULL,
    source_chunk_id character varying(128) NOT NULL,
    target_chunk_id character varying(128),
    target_doc character varying(128) NOT NULL,
    article integer NOT NULL,
    clause integer,
    point character varying(16),
    rule character varying(64) NOT NULL,
    confidence character varying(16) NOT NULL,
    needs_review boolean DEFAULT false NOT NULL,
    needs_reason character varying(16),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_legal_chunk_references_confidence CHECK (((confidence)::text = ANY ((ARRAY['HIGH'::character varying, 'LOW'::character varying])::text[]))),
    CONSTRAINT ck_legal_chunk_references_needs_reason CHECK (((needs_reason)::text = ANY ((ARRAY['BOUNDARY'::character varying, 'UNRESOLVED'::character varying])::text[])))
);


ALTER TABLE public.legal_chunk_references OWNER TO postgres;

--
-- Name: legal_chunk_references_ref_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.legal_chunk_references_ref_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.legal_chunk_references_ref_id_seq OWNER TO postgres;

--
-- Name: legal_chunk_references_ref_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.legal_chunk_references_ref_id_seq OWNED BY public.legal_chunk_references.ref_id;


--
-- Name: legal_chunks; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.legal_chunks (
    chunk_id character varying(128) NOT NULL,
    document_id character varying(64) NOT NULL,
    parent_chunk_id character varying(128),
    header_context text,
    text text NOT NULL,
    article_number integer NOT NULL,
    clause_number integer,
    point_letter character varying(16),
    chunk_level character varying(16) NOT NULL,
    meta jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_legal_chunks_chunk_level CHECK (((chunk_level)::text = ANY ((ARRAY['ARTICLE'::character varying, 'CLAUSE'::character varying, 'POINT'::character varying])::text[])))
);


ALTER TABLE public.legal_chunks OWNER TO postgres;

--
-- Name: legal_documents; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.legal_documents (
    document_id character varying(64) NOT NULL,
    doc_code character varying(32) NOT NULL,
    document_type character varying(32) NOT NULL,
    document_form character varying(32) NOT NULL,
    title character varying(512) NOT NULL,
    status character varying(32) DEFAULT 'ACTIVE'::character varying NOT NULL,
    amended_by jsonb,
    article_count integer DEFAULT 0 NOT NULL,
    chunk_count integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_legal_documents_status CHECK (((status)::text = ANY ((ARRAY['ACTIVE'::character varying, 'PARTIALLY_AMENDED'::character varying, 'INACTIVE'::character varying, 'SUPERSEDED'::character varying])::text[])))
);


ALTER TABLE public.legal_documents OWNER TO postgres;

--
-- Name: messages; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.messages (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    conversation_id uuid NOT NULL,
    role character varying(50) NOT NULL,
    content text NOT NULL,
    metadata jsonb,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT ck_messages_role CHECK (((role)::text = ANY ((ARRAY['USER'::character varying, 'ASSISTANT'::character varying, 'SYSTEM'::character varying, 'TOOL'::character varying])::text[])))
);


ALTER TABLE public.messages OWNER TO postgres;

--
-- Name: policies; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.policies (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    code character varying(100) NOT NULL,
    name character varying(255) NOT NULL,
    description text,
    policy_type character varying(100),
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT ck_policies_policy_type CHECK (((policy_type IS NULL) OR ((policy_type)::text = ANY ((ARRAY['LAW'::character varying, 'DECREE'::character varying, 'CIRCULAR'::character varying, 'INTERNAL_RULE'::character varying, 'PRECEDENT'::character varying])::text[]))))
);


ALTER TABLE public.policies OWNER TO postgres;

--
-- Name: policy_versions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.policy_versions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    policy_id uuid NOT NULL,
    version character varying(50) NOT NULL,
    effective_from date NOT NULL,
    effective_to date,
    status character varying(50) DEFAULT 'ACTIVE'::character varying NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT ck_policy_versions_effective_range CHECK (((effective_to IS NULL) OR (effective_to >= effective_from))),
    CONSTRAINT ck_policy_versions_status CHECK (((status)::text = ANY ((ARRAY['DRAFT'::character varying, 'ACTIVE'::character varying, 'ARCHIVED'::character varying])::text[])))
);


ALTER TABLE public.policy_versions OWNER TO postgres;

--
-- Name: recommendation_citations; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.recommendation_citations (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    recommendation_id uuid NOT NULL,
    chunk_id uuid,
    quote text NOT NULL,
    article character varying(50),
    clause character varying(50),
    point character varying(50),
    score double precision,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


ALTER TABLE public.recommendation_citations OWNER TO postgres;

--
-- Name: recommendations; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.recommendations (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    case_id uuid NOT NULL,
    agent_run_id uuid,
    recommendation text NOT NULL,
    rationale text,
    sanction_type character varying(50),
    process_steps jsonb,
    risk_level character varying(50),
    status character varying(50) DEFAULT 'DRAFT'::character varying NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT ck_recommendations_risk_level CHECK (((risk_level IS NULL) OR ((risk_level)::text = ANY ((ARRAY['LOW'::character varying, 'MEDIUM'::character varying, 'HIGH'::character varying, 'CRITICAL'::character varying])::text[])))),
    CONSTRAINT ck_recommendations_sanction_type CHECK (((sanction_type IS NULL) OR ((sanction_type)::text = ANY ((ARRAY['WARNING'::character varying, 'REPRIMAND'::character varying, 'WAGE_POSTPONEMENT'::character varying, 'DEMOTION'::character varying, 'DISMISSAL'::character varying, 'TERMINATION'::character varying])::text[])))),
    CONSTRAINT ck_recommendations_status CHECK (((status)::text = ANY ((ARRAY['DRAFT'::character varying, 'PENDING_REVIEW'::character varying, 'APPROVED'::character varying, 'REJECTED'::character varying, 'SUPERSEDED'::character varying])::text[])))
);


ALTER TABLE public.recommendations OWNER TO postgres;

--
-- Name: reviews; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.reviews (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    case_id uuid NOT NULL,
    recommendation_id uuid,
    draft_id uuid,
    reviewer_id uuid NOT NULL,
    decision character varying(50) NOT NULL,
    comment text,
    decided_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT ck_reviews_decision CHECK (((decision)::text = ANY ((ARRAY['APPROVE'::character varying, 'REJECT'::character varying])::text[])))
);


ALTER TABLE public.reviews OWNER TO postgres;

--
-- Name: tool_calls; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.tool_calls (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    agent_run_id uuid NOT NULL,
    tool_name character varying(255) NOT NULL,
    input jsonb,
    output jsonb,
    status character varying(50) DEFAULT 'PENDING'::character varying NOT NULL,
    started_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    completed_at timestamp without time zone,
    error text,
    CONSTRAINT ck_tool_calls_status CHECK (((status)::text = ANY ((ARRAY['PENDING'::character varying, 'RUNNING'::character varying, 'SUCCEEDED'::character varying, 'FAILED'::character varying])::text[])))
);


ALTER TABLE public.tool_calls OWNER TO postgres;

--
-- Name: users; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.users (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    email character varying(255) NOT NULL,
    password_hash character varying(255) NOT NULL,
    full_name character varying(255),
    role character varying(50) DEFAULT 'HR'::character varying NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT ck_users_role CHECK (((role)::text = ANY ((ARRAY['HR'::character varying, 'MANAGER'::character varying, 'LEGAL'::character varying])::text[])))
);


ALTER TABLE public.users OWNER TO postgres;

--
-- Name: violation_types; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.violation_types (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    code character varying(100) NOT NULL,
    name character varying(255) NOT NULL,
    description text,
    default_severity character varying(50),
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT ck_violation_types_default_severity CHECK (((default_severity IS NULL) OR ((default_severity)::text = ANY ((ARRAY['LOW'::character varying, 'MEDIUM'::character varying, 'HIGH'::character varying, 'CRITICAL'::character varying])::text[]))))
);


ALTER TABLE public.violation_types OWNER TO postgres;

--
-- Name: legal_chunk_references ref_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.legal_chunk_references ALTER COLUMN ref_id SET DEFAULT nextval('public.legal_chunk_references_ref_id_seq'::regclass);


--
-- Name: agent_retrievals agent_retrievals_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.agent_retrievals
    ADD CONSTRAINT agent_retrievals_pkey PRIMARY KEY (id);


--
-- Name: agent_runs agent_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.agent_runs
    ADD CONSTRAINT agent_runs_pkey PRIMARY KEY (id);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: case_access case_access_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.case_access
    ADD CONSTRAINT case_access_pkey PRIMARY KEY (id);


--
-- Name: case_drafts case_drafts_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.case_drafts
    ADD CONSTRAINT case_drafts_pkey PRIMARY KEY (id);


--
-- Name: case_facts case_facts_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.case_facts
    ADD CONSTRAINT case_facts_pkey PRIMARY KEY (id);


--
-- Name: case_violations case_violations_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.case_violations
    ADD CONSTRAINT case_violations_pkey PRIMARY KEY (id);


--
-- Name: cases cases_case_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cases
    ADD CONSTRAINT cases_case_code_key UNIQUE (case_code);


--
-- Name: cases cases_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cases
    ADD CONSTRAINT cases_pkey PRIMARY KEY (id);


--
-- Name: conversations conversations_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.conversations
    ADD CONSTRAINT conversations_pkey PRIMARY KEY (id);


--
-- Name: disciplinary_decisions disciplinary_decisions_case_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.disciplinary_decisions
    ADD CONSTRAINT disciplinary_decisions_case_id_key UNIQUE (case_id);


--
-- Name: disciplinary_decisions disciplinary_decisions_decision_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.disciplinary_decisions
    ADD CONSTRAINT disciplinary_decisions_decision_code_key UNIQUE (decision_code);


--
-- Name: disciplinary_decisions disciplinary_decisions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.disciplinary_decisions
    ADD CONSTRAINT disciplinary_decisions_pkey PRIMARY KEY (id);


--
-- Name: document_chunks document_chunks_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.document_chunks
    ADD CONSTRAINT document_chunks_pkey PRIMARY KEY (id);


--
-- Name: documents documents_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_pkey PRIMARY KEY (id);


--
-- Name: policy_versions ex_policy_versions_no_overlap; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.policy_versions
    ADD CONSTRAINT ex_policy_versions_no_overlap EXCLUDE USING gist (policy_id WITH =, daterange(effective_from,
CASE
    WHEN (effective_to IS NULL) THEN NULL::date
    ELSE (effective_to + 1)
END, '[)'::text) WITH &&);


--
-- Name: legal_chunk_embeddings legal_chunk_embeddings_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.legal_chunk_embeddings
    ADD CONSTRAINT legal_chunk_embeddings_pkey PRIMARY KEY (chunk_id);


--
-- Name: legal_chunk_references legal_chunk_references_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.legal_chunk_references
    ADD CONSTRAINT legal_chunk_references_pkey PRIMARY KEY (ref_id);


--
-- Name: legal_chunks legal_chunks_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.legal_chunks
    ADD CONSTRAINT legal_chunks_pkey PRIMARY KEY (chunk_id);


--
-- Name: legal_documents legal_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.legal_documents
    ADD CONSTRAINT legal_documents_pkey PRIMARY KEY (document_id);


--
-- Name: messages messages_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_pkey PRIMARY KEY (id);


--
-- Name: policies policies_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.policies
    ADD CONSTRAINT policies_code_key UNIQUE (code);


--
-- Name: policies policies_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.policies
    ADD CONSTRAINT policies_pkey PRIMARY KEY (id);


--
-- Name: policy_versions policy_versions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.policy_versions
    ADD CONSTRAINT policy_versions_pkey PRIMARY KEY (id);


--
-- Name: recommendation_citations recommendation_citations_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.recommendation_citations
    ADD CONSTRAINT recommendation_citations_pkey PRIMARY KEY (id);


--
-- Name: recommendations recommendations_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.recommendations
    ADD CONSTRAINT recommendations_pkey PRIMARY KEY (id);


--
-- Name: reviews reviews_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.reviews
    ADD CONSTRAINT reviews_pkey PRIMARY KEY (id);


--
-- Name: tool_calls tool_calls_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tool_calls
    ADD CONSTRAINT tool_calls_pkey PRIMARY KEY (id);


--
-- Name: agent_retrievals uq_agent_retrievals_run_chunk; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.agent_retrievals
    ADD CONSTRAINT uq_agent_retrievals_run_chunk UNIQUE (agent_run_id, chunk_id);


--
-- Name: agent_retrievals uq_agent_retrievals_run_rank; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.agent_retrievals
    ADD CONSTRAINT uq_agent_retrievals_run_rank UNIQUE (agent_run_id, rank);


--
-- Name: case_access uq_case_access_case_user; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.case_access
    ADD CONSTRAINT uq_case_access_case_user UNIQUE (case_id, user_id);


--
-- Name: case_facts uq_case_facts_case_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.case_facts
    ADD CONSTRAINT uq_case_facts_case_key UNIQUE (case_id, fact_key);


--
-- Name: document_chunks uq_document_chunk_index; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.document_chunks
    ADD CONSTRAINT uq_document_chunk_index UNIQUE (document_id, chunk_index);


--
-- Name: legal_chunk_references uq_legal_chunk_references; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.legal_chunk_references
    ADD CONSTRAINT uq_legal_chunk_references UNIQUE NULLS NOT DISTINCT (source_chunk_id, target_chunk_id, target_doc, article, clause, point, rule);


--
-- Name: policy_versions uq_policy_version; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.policy_versions
    ADD CONSTRAINT uq_policy_version UNIQUE (policy_id, version);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: violation_types violation_types_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.violation_types
    ADD CONSTRAINT violation_types_code_key UNIQUE (code);


--
-- Name: violation_types violation_types_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.violation_types
    ADD CONSTRAINT violation_types_pkey PRIMARY KEY (id);


--
-- Name: idx_agent_retrievals_chunk_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_agent_retrievals_chunk_id ON public.agent_retrievals USING btree (chunk_id);


--
-- Name: idx_agent_runs_conversation_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_agent_runs_conversation_id ON public.agent_runs USING btree (conversation_id);


--
-- Name: idx_agent_runs_message_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_agent_runs_message_id ON public.agent_runs USING btree (message_id);


--
-- Name: idx_agent_runs_output_message_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_agent_runs_output_message_id ON public.agent_runs USING btree (output_message_id);


--
-- Name: idx_case_access_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_case_access_user_id ON public.case_access USING btree (user_id);


--
-- Name: idx_case_drafts_case_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_case_drafts_case_id ON public.case_drafts USING btree (case_id);


--
-- Name: idx_case_drafts_recommendation_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_case_drafts_recommendation_id ON public.case_drafts USING btree (recommendation_id);


--
-- Name: idx_case_violations_case_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_case_violations_case_id ON public.case_violations USING btree (case_id);


--
-- Name: idx_case_violations_violation_type_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_case_violations_violation_type_id ON public.case_violations USING btree (violation_type_id);


--
-- Name: idx_cases_created_by; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_cases_created_by ON public.cases USING btree (created_by);


--
-- Name: idx_cases_employee_code; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_cases_employee_code ON public.cases USING btree (employee_code);


--
-- Name: idx_cases_incident_date; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_cases_incident_date ON public.cases USING btree (incident_date);


--
-- Name: idx_cases_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_cases_status ON public.cases USING btree (status);


--
-- Name: idx_conversations_case_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_conversations_case_id ON public.conversations USING btree (case_id);


--
-- Name: idx_conversations_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_conversations_user_id ON public.conversations USING btree (user_id);


--
-- Name: idx_disciplinary_decisions_embedding_hnsw; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_disciplinary_decisions_embedding_hnsw ON public.disciplinary_decisions USING hnsw (embedding public.vector_cosine_ops) WITH (m='16', ef_construction='64') WHERE (is_precedent AND (embedding IS NOT NULL));


--
-- Name: idx_disciplinary_decisions_issued_by; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_disciplinary_decisions_issued_by ON public.disciplinary_decisions USING btree (issued_by);


--
-- Name: idx_disciplinary_decisions_precedent; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_disciplinary_decisions_precedent ON public.disciplinary_decisions USING btree (is_precedent) WHERE is_precedent;


--
-- Name: idx_document_chunks_document_article; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_document_chunks_document_article ON public.document_chunks USING btree (document_id, article);


--
-- Name: idx_document_chunks_embedding_hnsw; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_document_chunks_embedding_hnsw ON public.document_chunks USING hnsw (embedding public.vector_cosine_ops) WITH (m='16', ef_construction='64') WHERE (embedding IS NOT NULL);


--
-- Name: idx_documents_content_hash; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_documents_content_hash ON public.documents USING btree (content_hash);


--
-- Name: idx_documents_ingest_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_documents_ingest_status ON public.documents USING btree (ingest_status);


--
-- Name: idx_documents_policy_version_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_documents_policy_version_id ON public.documents USING btree (policy_version_id);


--
-- Name: idx_messages_conversation_id_created_at; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_messages_conversation_id_created_at ON public.messages USING btree (conversation_id, created_at);


--
-- Name: idx_policies_policy_type; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_policies_policy_type ON public.policies USING btree (policy_type);


--
-- Name: idx_policy_versions_effective_from; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_policy_versions_effective_from ON public.policy_versions USING btree (effective_from);


--
-- Name: idx_policy_versions_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_policy_versions_status ON public.policy_versions USING btree (status);


--
-- Name: idx_recommendation_citations_chunk_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_recommendation_citations_chunk_id ON public.recommendation_citations USING btree (chunk_id);


--
-- Name: idx_recommendation_citations_recommendation_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_recommendation_citations_recommendation_id ON public.recommendation_citations USING btree (recommendation_id);


--
-- Name: idx_recommendations_agent_run_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_recommendations_agent_run_id ON public.recommendations USING btree (agent_run_id);


--
-- Name: idx_recommendations_case_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_recommendations_case_id ON public.recommendations USING btree (case_id);


--
-- Name: idx_recommendations_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_recommendations_status ON public.recommendations USING btree (status);


--
-- Name: idx_reviews_case_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_reviews_case_id ON public.reviews USING btree (case_id);


--
-- Name: idx_reviews_draft_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_reviews_draft_id ON public.reviews USING btree (draft_id);


--
-- Name: idx_reviews_recommendation_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_reviews_recommendation_id ON public.reviews USING btree (recommendation_id);


--
-- Name: idx_reviews_reviewer_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_reviews_reviewer_id ON public.reviews USING btree (reviewer_id);


--
-- Name: idx_tool_calls_agent_run_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_tool_calls_agent_run_id ON public.tool_calls USING btree (agent_run_id);


--
-- Name: ix_legal_chunk_embeddings_search_tsv; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_legal_chunk_embeddings_search_tsv ON public.legal_chunk_embeddings USING gin (search_tsv);


--
-- Name: ix_legal_chunk_references_target_source; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_legal_chunk_references_target_source ON public.legal_chunk_references USING btree (target_chunk_id, source_chunk_id) NULLS NOT DISTINCT;


--
-- Name: ix_legal_chunks_article_number; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_legal_chunks_article_number ON public.legal_chunks USING btree (article_number);


--
-- Name: ix_legal_chunks_chunk_level; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_legal_chunks_chunk_level ON public.legal_chunks USING btree (chunk_level);


--
-- Name: ix_legal_chunks_clause_number; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_legal_chunks_clause_number ON public.legal_chunks USING btree (clause_number);


--
-- Name: ix_legal_chunks_document_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_legal_chunks_document_id ON public.legal_chunks USING btree (document_id);


--
-- Name: ix_legal_chunks_point_letter; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_legal_chunks_point_letter ON public.legal_chunks USING btree (point_letter);


--
-- Name: ix_legal_documents_doc_code; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX ix_legal_documents_doc_code ON public.legal_documents USING btree (doc_code);


--
-- Name: ix_legal_embeddings_hnsw; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_legal_embeddings_hnsw ON public.legal_chunk_embeddings USING hnsw (embedding public.vector_cosine_ops) WITH (m='16', ef_construction='64');


--
-- Name: uq_policy_versions_one_active; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX uq_policy_versions_one_active ON public.policy_versions USING btree (policy_id) WHERE ((status)::text = 'ACTIVE'::text);


--
-- Name: agent_retrievals agent_retrievals_agent_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.agent_retrievals
    ADD CONSTRAINT agent_retrievals_agent_run_id_fkey FOREIGN KEY (agent_run_id) REFERENCES public.agent_runs(id) ON DELETE CASCADE;


--
-- Name: agent_retrievals agent_retrievals_chunk_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.agent_retrievals
    ADD CONSTRAINT agent_retrievals_chunk_id_fkey FOREIGN KEY (chunk_id) REFERENCES public.document_chunks(id) ON DELETE CASCADE;


--
-- Name: agent_runs agent_runs_conversation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.agent_runs
    ADD CONSTRAINT agent_runs_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.conversations(id) ON DELETE CASCADE;


--
-- Name: agent_runs agent_runs_message_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.agent_runs
    ADD CONSTRAINT agent_runs_message_id_fkey FOREIGN KEY (message_id) REFERENCES public.messages(id) ON DELETE CASCADE;


--
-- Name: agent_runs agent_runs_output_message_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.agent_runs
    ADD CONSTRAINT agent_runs_output_message_id_fkey FOREIGN KEY (output_message_id) REFERENCES public.messages(id) ON DELETE SET NULL;


--
-- Name: case_access case_access_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.case_access
    ADD CONSTRAINT case_access_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.cases(id) ON DELETE CASCADE;


--
-- Name: case_access case_access_granted_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.case_access
    ADD CONSTRAINT case_access_granted_by_fkey FOREIGN KEY (granted_by) REFERENCES public.users(id);


--
-- Name: case_access case_access_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.case_access
    ADD CONSTRAINT case_access_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: case_drafts case_drafts_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.case_drafts
    ADD CONSTRAINT case_drafts_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.cases(id) ON DELETE CASCADE;


--
-- Name: case_drafts case_drafts_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.case_drafts
    ADD CONSTRAINT case_drafts_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: case_drafts case_drafts_recommendation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.case_drafts
    ADD CONSTRAINT case_drafts_recommendation_id_fkey FOREIGN KEY (recommendation_id) REFERENCES public.recommendations(id) ON DELETE SET NULL;


--
-- Name: case_facts case_facts_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.case_facts
    ADD CONSTRAINT case_facts_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.cases(id) ON DELETE CASCADE;


--
-- Name: case_facts case_facts_confirmed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.case_facts
    ADD CONSTRAINT case_facts_confirmed_by_fkey FOREIGN KEY (confirmed_by) REFERENCES public.users(id);


--
-- Name: case_facts case_facts_source_message_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.case_facts
    ADD CONSTRAINT case_facts_source_message_id_fkey FOREIGN KEY (source_message_id) REFERENCES public.messages(id) ON DELETE SET NULL;


--
-- Name: case_violations case_violations_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.case_violations
    ADD CONSTRAINT case_violations_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.cases(id) ON DELETE CASCADE;


--
-- Name: case_violations case_violations_violation_type_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.case_violations
    ADD CONSTRAINT case_violations_violation_type_id_fkey FOREIGN KEY (violation_type_id) REFERENCES public.violation_types(id);


--
-- Name: cases cases_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cases
    ADD CONSTRAINT cases_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);


--
-- Name: conversations conversations_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.conversations
    ADD CONSTRAINT conversations_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.cases(id) ON DELETE SET NULL;


--
-- Name: conversations conversations_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.conversations
    ADD CONSTRAINT conversations_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: disciplinary_decisions disciplinary_decisions_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.disciplinary_decisions
    ADD CONSTRAINT disciplinary_decisions_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.cases(id) ON DELETE CASCADE;


--
-- Name: disciplinary_decisions disciplinary_decisions_draft_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.disciplinary_decisions
    ADD CONSTRAINT disciplinary_decisions_draft_id_fkey FOREIGN KEY (draft_id) REFERENCES public.case_drafts(id) ON DELETE SET NULL;


--
-- Name: disciplinary_decisions disciplinary_decisions_issued_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.disciplinary_decisions
    ADD CONSTRAINT disciplinary_decisions_issued_by_fkey FOREIGN KEY (issued_by) REFERENCES public.users(id);


--
-- Name: document_chunks document_chunks_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.document_chunks
    ADD CONSTRAINT document_chunks_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE;


--
-- Name: documents documents_policy_version_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_policy_version_id_fkey FOREIGN KEY (policy_version_id) REFERENCES public.policy_versions(id) ON DELETE CASCADE;


--
-- Name: legal_chunk_references fk_legal_chunk_references_source_chunk_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.legal_chunk_references
    ADD CONSTRAINT fk_legal_chunk_references_source_chunk_id FOREIGN KEY (source_chunk_id) REFERENCES public.legal_chunks(chunk_id) ON DELETE CASCADE;


--
-- Name: legal_chunk_references fk_legal_chunk_references_target_chunk_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.legal_chunk_references
    ADD CONSTRAINT fk_legal_chunk_references_target_chunk_id FOREIGN KEY (target_chunk_id) REFERENCES public.legal_chunks(chunk_id) ON DELETE SET NULL;


--
-- Name: legal_chunks fk_legal_chunks_document_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.legal_chunks
    ADD CONSTRAINT fk_legal_chunks_document_id FOREIGN KEY (document_id) REFERENCES public.legal_documents(document_id) ON DELETE CASCADE;


--
-- Name: legal_chunk_embeddings legal_chunk_embeddings_chunk_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.legal_chunk_embeddings
    ADD CONSTRAINT legal_chunk_embeddings_chunk_id_fkey FOREIGN KEY (chunk_id) REFERENCES public.legal_chunks(chunk_id) ON DELETE CASCADE;


--
-- Name: messages messages_conversation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.conversations(id) ON DELETE CASCADE;


--
-- Name: policy_versions policy_versions_policy_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.policy_versions
    ADD CONSTRAINT policy_versions_policy_id_fkey FOREIGN KEY (policy_id) REFERENCES public.policies(id);


--
-- Name: recommendation_citations recommendation_citations_chunk_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.recommendation_citations
    ADD CONSTRAINT recommendation_citations_chunk_id_fkey FOREIGN KEY (chunk_id) REFERENCES public.document_chunks(id) ON DELETE SET NULL;


--
-- Name: recommendation_citations recommendation_citations_recommendation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.recommendation_citations
    ADD CONSTRAINT recommendation_citations_recommendation_id_fkey FOREIGN KEY (recommendation_id) REFERENCES public.recommendations(id) ON DELETE CASCADE;


--
-- Name: recommendations recommendations_agent_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.recommendations
    ADD CONSTRAINT recommendations_agent_run_id_fkey FOREIGN KEY (agent_run_id) REFERENCES public.agent_runs(id) ON DELETE SET NULL;


--
-- Name: recommendations recommendations_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.recommendations
    ADD CONSTRAINT recommendations_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.cases(id) ON DELETE CASCADE;


--
-- Name: reviews reviews_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.reviews
    ADD CONSTRAINT reviews_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.cases(id) ON DELETE CASCADE;


--
-- Name: reviews reviews_draft_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.reviews
    ADD CONSTRAINT reviews_draft_id_fkey FOREIGN KEY (draft_id) REFERENCES public.case_drafts(id) ON DELETE SET NULL;


--
-- Name: reviews reviews_recommendation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.reviews
    ADD CONSTRAINT reviews_recommendation_id_fkey FOREIGN KEY (recommendation_id) REFERENCES public.recommendations(id) ON DELETE SET NULL;


--
-- Name: reviews reviews_reviewer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.reviews
    ADD CONSTRAINT reviews_reviewer_id_fkey FOREIGN KEY (reviewer_id) REFERENCES public.users(id);


--
-- Name: tool_calls tool_calls_agent_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tool_calls
    ADD CONSTRAINT tool_calls_agent_run_id_fkey FOREIGN KEY (agent_run_id) REFERENCES public.agent_runs(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict QLi0tv0kBb287fVgTmRVu9NRhBRiYRPW1XpUnP2ezsU9lkNTxM1U1v52JuhK2CQ

