import type {
	AskRequest,
	AskResponse,
	Document,
	DocumentChunk,
	DocumentListParams,
	DocumentListResponse,
	DocumentTagsUpdateRequest,
	Quiz,
	QuizAttemptRequest,
	QuizAttemptResponse,
	QuizGenerateRequest,
	QuizListResponse,
	QuizResultsResponse,
	SearchRequest,
	SearchResponse,
	SummaryRequest,
	SummaryResponse,
	Tag,
	TagCreateRequest,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";
const TIMEOUT = 120_000; // generous timeout for LLM calls

function url(path: string): string {
	return `${API_BASE}/api/v1${path}`;
}

/** Generic error class for API failures */
export class ApiError extends Error {
	constructor(
		public status: number,
		public detail: string,
	) {
		super(`API error (${status}): ${detail}`);
		this.name = "ApiError";
	}
}

/** Shared response handler */
async function handle<T>(resp: Response): Promise<T> {
	if (!resp.ok) {
		let detail: string;
		try {
			const body = await resp.json();
			detail = body.detail ?? resp.statusText;
		} catch {
			detail = resp.statusText;
		}
		throw new ApiError(resp.status, detail);
	}
	return resp.json() as Promise<T>;
}

/** Build an AbortSignal that times out */
function timeoutSignal(ms: number = TIMEOUT): AbortSignal {
	return AbortSignal.timeout(ms);
}

// ── Health ─────────────────────────────────────────────

export async function health(): Promise<{ status: string }> {
	const resp = await fetch(`${API_BASE}/health`, {
		signal: timeoutSignal(10_000),
	});
	return handle(resp);
}

// ── Documents ──────────────────────────────────────────

export async function uploadDocument(
	file: File,
	meta?: { course_name?: string; subject?: string },
): Promise<Document> {
	const params = new URLSearchParams();
	if (meta?.course_name) params.set("course_name", meta.course_name);
	if (meta?.subject) params.set("subject", meta.subject);

	const body = new FormData();
	body.append("file", file);

	const qs = params.toString();
	const resp = await fetch(url(`/documents/${qs ? `?${qs}` : ""}`), {
		method: "POST",
		body,
		signal: timeoutSignal(),
	});
	return handle<Document>(resp);
}

export async function listDocuments(
	params?: DocumentListParams,
): Promise<DocumentListResponse> {
	const qs = new URLSearchParams();
	if (params) {
		for (const [k, v] of Object.entries(params)) {
			if (v != null) qs.set(k, String(v));
		}
	}
	const q = qs.toString();
	const resp = await fetch(url(`/documents/${q ? `?${q}` : ""}`), {
		signal: timeoutSignal(),
	});
	return handle<DocumentListResponse>(resp);
}

export async function getDocument(docId: string): Promise<Document> {
	const resp = await fetch(url(`/documents/${docId}`), {
		signal: timeoutSignal(),
	});
	return handle<Document>(resp);
}

export async function deleteDocument(docId: string): Promise<void> {
	const resp = await fetch(url(`/documents/${docId}`), {
		method: "DELETE",
		signal: timeoutSignal(),
	});
	if (!resp.ok) {
		await handle(resp); // throws ApiError
	}
}

export async function getChunks(
	docId: string,
	offset = 0,
	limit = 20,
): Promise<DocumentChunk[]> {
	const qs = new URLSearchParams({
		offset: String(offset),
		limit: String(limit),
	});
	const resp = await fetch(url(`/documents/${docId}/chunks?${qs}`), {
		signal: timeoutSignal(),
	});
	return handle<DocumentChunk[]>(resp);
}

// ── Tags ───────────────────────────────────────────────

export async function listTags(): Promise<Tag[]> {
	const resp = await fetch(url("/tags/"), { signal: timeoutSignal() });
	return handle<Tag[]>(resp);
}

export async function createTag(data: TagCreateRequest): Promise<Tag> {
	const resp = await fetch(url("/tags/"), {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(data),
		signal: timeoutSignal(),
	});
	return handle<Tag>(resp);
}

export async function addTagsToDocument(
	docId: string,
	data: DocumentTagsUpdateRequest,
): Promise<Document> {
	const resp = await fetch(url(`/documents/${docId}/tags`), {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(data),
		signal: timeoutSignal(),
	});
	return handle<Document>(resp);
}

// ── Q&A ────────────────────────────────────────────────

export async function askQuestion(data: AskRequest): Promise<AskResponse> {
	const resp = await fetch(url("/qa/ask"), {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(data),
		signal: timeoutSignal(),
	});
	return handle<AskResponse>(resp);
}

export async function semanticSearch(
	data: SearchRequest,
): Promise<SearchResponse> {
	const resp = await fetch(url("/qa/search"), {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(data),
		signal: timeoutSignal(),
	});
	return handle<SearchResponse>(resp);
}

// ── Summaries ──────────────────────────────────────────

export async function generateSummary(
	data: SummaryRequest,
): Promise<SummaryResponse> {
	const resp = await fetch(url("/summaries/generate"), {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(data),
		signal: timeoutSignal(),
	});
	return handle<SummaryResponse>(resp);
}

// ── Quizzes ────────────────────────────────────────────

export async function generateQuiz(data: QuizGenerateRequest): Promise<Quiz> {
	const resp = await fetch(url("/quizzes/generate"), {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(data),
		signal: timeoutSignal(),
	});
	return handle<Quiz>(resp);
}

export async function listQuizzes(
	documentId?: string,
): Promise<QuizListResponse> {
	const qs = documentId
		? `?${new URLSearchParams({ document_id: documentId })}`
		: "";
	const resp = await fetch(url(`/quizzes/${qs}`), {
		signal: timeoutSignal(),
	});
	return handle<QuizListResponse>(resp);
}

export async function getQuiz(quizId: string): Promise<Quiz> {
	const resp = await fetch(url(`/quizzes/${quizId}`), {
		signal: timeoutSignal(),
	});
	return handle<Quiz>(resp);
}

export async function submitAttempt(
	quizId: string,
	data: QuizAttemptRequest,
): Promise<QuizAttemptResponse> {
	const resp = await fetch(url(`/quizzes/${quizId}/attempt`), {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(data),
		signal: timeoutSignal(),
	});
	return handle<QuizAttemptResponse>(resp);
}

export async function getQuizResults(
	quizId: string,
): Promise<QuizResultsResponse> {
	const resp = await fetch(url(`/quizzes/${quizId}/results`), {
		signal: timeoutSignal(),
	});
	return handle<QuizResultsResponse>(resp);
}
