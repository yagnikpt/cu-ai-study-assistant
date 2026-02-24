import type {
	AskRequest,
	AskResponse,
	Document,
	DocumentChunk,
	DocumentListParams,
	DocumentListResponse,
	DocumentTagsUpdateRequest,
	ProfileAnalytics,
	QAStreamEvent,
	Quiz,
	QuizAttemptRequest,
	QuizAttemptResponse,
	QuizGenerateRequest,
	QuizListResponse,
	QuizResultsResponse,
	SearchRequest,
	SearchResponse,
	Space,
	SpaceCreateRequest,
	SpaceListResponse,
	SpaceUpdateRequest,
	StudyPlan,
	StudyPlanGenerateRequest,
	StudyPlanListResponse,
	StudyTopic,
	SummaryRequest,
	SummaryResponse,
	SummaryStreamEvent,
	Tag,
	TagCreateRequest,
	User,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";
const TIMEOUT = 120_000; // generous timeout for LLM calls

function url(path: string): string {
	return `${API_BASE}/api/v1${path}`;
}

/** Default fetch options — always send cookies */
const defaultOpts: RequestInit = { credentials: "include" };

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
		...defaultOpts,
		signal: timeoutSignal(10_000),
	});
	return handle(resp);
}

// ── Auth ───────────────────────────────────────────────

/** URL the browser should navigate to for GitHub OAuth login. */
export function getGitHubLoginUrl(): string {
	return `${API_BASE}/auth/github/login`;
}

/** Fetch the currently authenticated user from the session cookie. */
export async function getMe(): Promise<User> {
	const resp = await fetch(url("/auth/me"), {
		...defaultOpts,
		signal: timeoutSignal(10_000),
	});
	return handle<User>(resp);
}

/** Clear the session cookie. */
export async function logout(): Promise<void> {
	await fetch(url("/auth/logout"), {
		...defaultOpts,
		method: "POST",
		signal: timeoutSignal(5_000),
	});
}

// ── Spaces ─────────────────────────────────────────────

export async function createSpace(data: SpaceCreateRequest): Promise<Space> {
	const resp = await fetch(url("/spaces/"), {
		...defaultOpts,
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(data),
		signal: timeoutSignal(),
	});
	return handle<Space>(resp);
}

export async function listSpaces(): Promise<SpaceListResponse> {
	const resp = await fetch(url("/spaces/"), {
		...defaultOpts,
		signal: timeoutSignal(),
	});
	return handle<SpaceListResponse>(resp);
}

export async function getSpace(spaceId: string): Promise<Space> {
	const resp = await fetch(url(`/spaces/${spaceId}`), {
		...defaultOpts,
		signal: timeoutSignal(),
	});
	return handle<Space>(resp);
}

export async function updateSpace(
	spaceId: string,
	data: SpaceUpdateRequest,
): Promise<Space> {
	const resp = await fetch(url(`/spaces/${spaceId}`), {
		...defaultOpts,
		method: "PATCH",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(data),
		signal: timeoutSignal(),
	});
	return handle<Space>(resp);
}

export async function deleteSpace(spaceId: string): Promise<void> {
	const resp = await fetch(url(`/spaces/${spaceId}`), {
		...defaultOpts,
		method: "DELETE",
		signal: timeoutSignal(),
	});
	if (!resp.ok) {
		await handle(resp); // throws ApiError
	}
}

// ── Documents ──────────────────────────────────────────

export async function uploadDocument(
	spaceId: string,
	file: File,
	meta?: { course_name?: string; subject?: string },
): Promise<Document> {
	const params = new URLSearchParams();
	if (meta?.course_name) params.set("course_name", meta.course_name);
	if (meta?.subject) params.set("subject", meta.subject);

	const body = new FormData();
	body.append("file", file);

	const qs = params.toString();
	const resp = await fetch(
		url(`/spaces/${spaceId}/documents/${qs ? `?${qs}` : ""}`),
		{
			...defaultOpts,
			method: "POST",
			body,
			signal: timeoutSignal(),
		},
	);
	return handle<Document>(resp);
}

export async function listDocuments(
	spaceId: string,
	params?: DocumentListParams,
): Promise<DocumentListResponse> {
	const qs = new URLSearchParams();
	if (params) {
		for (const [k, v] of Object.entries(params)) {
			if (v != null) qs.set(k, String(v));
		}
	}
	const q = qs.toString();
	const resp = await fetch(
		url(`/spaces/${spaceId}/documents/${q ? `?${q}` : ""}`),
		{
			...defaultOpts,
			signal: timeoutSignal(),
		},
	);
	return handle<DocumentListResponse>(resp);
}

export async function getDocument(
	spaceId: string,
	docId: string,
): Promise<Document> {
	const resp = await fetch(url(`/spaces/${spaceId}/documents/${docId}`), {
		...defaultOpts,
		signal: timeoutSignal(),
	});
	return handle<Document>(resp);
}

export async function deleteDocument(
	spaceId: string,
	docId: string,
): Promise<void> {
	const resp = await fetch(url(`/spaces/${spaceId}/documents/${docId}`), {
		...defaultOpts,
		method: "DELETE",
		signal: timeoutSignal(),
	});
	if (!resp.ok) {
		await handle(resp); // throws ApiError
	}
}

export async function getChunks(
	spaceId: string,
	docId: string,
	offset = 0,
	limit = 20,
): Promise<DocumentChunk[]> {
	const qs = new URLSearchParams({
		offset: String(offset),
		limit: String(limit),
	});
	const resp = await fetch(
		url(`/spaces/${spaceId}/documents/${docId}/chunks?${qs}`),
		{
			...defaultOpts,
			signal: timeoutSignal(),
		},
	);
	return handle<DocumentChunk[]>(resp);
}

// ── Tags ───────────────────────────────────────────────

export async function listTags(): Promise<Tag[]> {
	const resp = await fetch(url("/tags/"), {
		...defaultOpts,
		signal: timeoutSignal(),
	});
	return handle<Tag[]>(resp);
}

export async function createTag(data: TagCreateRequest): Promise<Tag> {
	const resp = await fetch(url("/tags/"), {
		...defaultOpts,
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(data),
		signal: timeoutSignal(),
	});
	return handle<Tag>(resp);
}

export async function addTagsToDocument(
	spaceId: string,
	docId: string,
	data: DocumentTagsUpdateRequest,
): Promise<Document> {
	const resp = await fetch(url(`/spaces/${spaceId}/documents/${docId}/tags`), {
		...defaultOpts,
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(data),
		signal: timeoutSignal(),
	});
	return handle<Document>(resp);
}

// ── Q&A ────────────────────────────────────────────────

export async function askQuestion(
	spaceId: string,
	data: AskRequest,
): Promise<AskResponse> {
	const resp = await fetch(url(`/spaces/${spaceId}/qa/ask`), {
		...defaultOpts,
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(data),
		signal: timeoutSignal(),
	});
	return handle<AskResponse>(resp);
}

export async function semanticSearch(
	spaceId: string,
	data: SearchRequest,
): Promise<SearchResponse> {
	const resp = await fetch(url(`/spaces/${spaceId}/qa/search`), {
		...defaultOpts,
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(data),
		signal: timeoutSignal(),
	});
	return handle<SearchResponse>(resp);
}

// ── Summaries ──────────────────────────────────────────

export async function generateSummary(
	spaceId: string,
	data: SummaryRequest,
): Promise<SummaryResponse> {
	const resp = await fetch(url(`/spaces/${spaceId}/summaries/generate`), {
		...defaultOpts,
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(data),
		signal: timeoutSignal(),
	});
	return handle<SummaryResponse>(resp);
}

// ── SSE Streaming ─────────────────────────────────────

/**
 * Parse an SSE text/event-stream into typed events.
 *
 * Each SSE frame has the shape:
 *   event: <type>\n
 *   data: <json>\n\n
 *
 * The callback fires once per parsed event.
 */
async function consumeSSE<T extends { type: string; data?: any }>(
	resp: Response,
	onEvent: (event: T) => void,
): Promise<void> {
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

	const reader = resp.body?.getReader();
	if (!reader) throw new Error("Response body is not readable");

	const decoder = new TextDecoder();
	let buffer = "";

	for (;;) {
		const { done, value } = await reader.read();
		if (done) break;

		buffer += decoder.decode(value, { stream: true });

		// Split on double newlines (SSE frame boundary)
		let boundary: number;
		while ((boundary = buffer.indexOf("\n\n")) !== -1) {
			const frame = buffer.slice(0, boundary);
			buffer = buffer.slice(boundary + 2);

			let eventType = "";
			let eventData = "";

			for (const line of frame.split("\n")) {
				if (line.startsWith("event: ")) {
					eventType = line.slice(7);
				} else if (line.startsWith("data: ")) {
					eventData = line.slice(6);
				}
			}

			if (eventType && eventData) {
				onEvent({ type: eventType, data: JSON.parse(eventData) } as T);
			}
		}
	}
}

/**
 * Stream a Q&A answer via SSE.
 * Calls `onEvent` for each SSE event (sources → token* → done).
 */
export async function askQuestionStream(
	spaceId: string,
	data: AskRequest,
	onEvent: (event: QAStreamEvent) => void,
	signal?: AbortSignal,
): Promise<void> {
	const resp = await fetch(url(`/spaces/${spaceId}/qa/ask/stream`), {
		...defaultOpts,
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(data),
		signal: signal ?? timeoutSignal(300_000),
	});
	await consumeSSE<QAStreamEvent>(resp, onEvent);
}

/**
 * Stream a summary via SSE.
 * Calls `onEvent` for each SSE event (meta → token* → done).
 */
export async function generateSummaryStream(
	spaceId: string,
	data: SummaryRequest,
	onEvent: (event: SummaryStreamEvent) => void,
	signal?: AbortSignal,
): Promise<void> {
	const resp = await fetch(
		url(`/spaces/${spaceId}/summaries/generate/stream`),
		{
			...defaultOpts,
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(data),
			signal: signal ?? timeoutSignal(300_000),
		},
	);
	await consumeSSE<SummaryStreamEvent>(resp, onEvent);
}

// ── Quizzes ────────────────────────────────────────────

export async function generateQuiz(
	spaceId: string,
	data: QuizGenerateRequest,
): Promise<Quiz> {
	const resp = await fetch(url(`/spaces/${spaceId}/quizzes/generate`), {
		...defaultOpts,
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(data),
		signal: timeoutSignal(),
	});
	return handle<Quiz>(resp);
}

export async function listQuizzes(
	spaceId: string,
	documentId?: string,
): Promise<QuizListResponse> {
	const qs = documentId
		? `?${new URLSearchParams({ document_id: documentId })}`
		: "";
	const resp = await fetch(url(`/spaces/${spaceId}/quizzes/${qs}`), {
		...defaultOpts,
		signal: timeoutSignal(),
	});
	return handle<QuizListResponse>(resp);
}

export async function getQuiz(spaceId: string, quizId: string): Promise<Quiz> {
	const resp = await fetch(url(`/spaces/${spaceId}/quizzes/${quizId}`), {
		...defaultOpts,
		signal: timeoutSignal(),
	});
	return handle<Quiz>(resp);
}

export async function submitAttempt(
	spaceId: string,
	quizId: string,
	data: QuizAttemptRequest,
): Promise<QuizAttemptResponse> {
	const resp = await fetch(
		url(`/spaces/${spaceId}/quizzes/${quizId}/attempt`),
		{
			...defaultOpts,
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(data),
			signal: timeoutSignal(),
		},
	);
	return handle<QuizAttemptResponse>(resp);
}

export async function getQuizResults(
	spaceId: string,
	quizId: string,
): Promise<QuizResultsResponse> {
	const resp = await fetch(
		url(`/spaces/${spaceId}/quizzes/${quizId}/results`),
		{
			...defaultOpts,
			signal: timeoutSignal(),
		},
	);
	return handle<QuizResultsResponse>(resp);
}

// ── Study Plans ────────────────────────────────────────

export async function generateStudyPlan(
	spaceId: string,
	data: StudyPlanGenerateRequest,
): Promise<StudyPlan> {
	const resp = await fetch(url(`/spaces/${spaceId}/study-plans/generate`), {
		...defaultOpts,
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(data),
		signal: timeoutSignal(),
	});
	return handle<StudyPlan>(resp);
}

export async function listStudyPlans(
	spaceId: string,
): Promise<StudyPlanListResponse> {
	const resp = await fetch(url(`/spaces/${spaceId}/study-plans/`), {
		...defaultOpts,
		signal: timeoutSignal(),
	});
	return handle<StudyPlanListResponse>(resp);
}

export async function getStudyPlan(
	spaceId: string,
	planId: string,
): Promise<StudyPlan> {
	const resp = await fetch(url(`/spaces/${spaceId}/study-plans/${planId}`), {
		...defaultOpts,
		signal: timeoutSignal(),
	});
	return handle<StudyPlan>(resp);
}

export async function toggleTopicComplete(
	spaceId: string,
	planId: string,
	topicId: string,
	completed: boolean,
): Promise<StudyTopic> {
	const resp = await fetch(
		url(`/spaces/${spaceId}/study-plans/${planId}/topics/${topicId}`),
		{
			...defaultOpts,
			method: "PATCH",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ completed }),
			signal: timeoutSignal(),
		},
	);
	return handle<StudyTopic>(resp);
}

export async function deleteStudyPlan(
	spaceId: string,
	planId: string,
): Promise<void> {
	await fetch(url(`/spaces/${spaceId}/study-plans/${planId}`), {
		...defaultOpts,
		method: "DELETE",
		signal: timeoutSignal(),
	});
}

// ── Analytics ──────────────────────────────────────────

export async function getProfileAnalytics(): Promise<ProfileAnalytics> {
	const resp = await fetch(url("/analytics/profile"), {
		...defaultOpts,
		signal: timeoutSignal(),
	});
	return handle<ProfileAnalytics>(resp);
}
