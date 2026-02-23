// ── Shared / Common ────────────────────────────────────

/** ISO-8601 date string returned by the backend */
export type ISODateString = string;

// ── Tags ───────────────────────────────────────────────

export interface Tag {
	id: string;
	name: string;
	color: string | null;
	created_at: ISODateString;
}

export interface TagCreateRequest {
	name: string;
	color?: string | null;
}

export interface DocumentTagsUpdateRequest {
	tag_ids: string[];
}

// ── Documents ──────────────────────────────────────────

export type DocumentStatus = "processing" | "ready" | "error";

export interface DocumentChunk {
	id: string;
	chunk_index: number;
	content: string;
	page_start: number;
	page_end: number;
	section_title: string | null;
	token_count: number;
}

export interface Document {
	id: string;
	filename: string;
	original_filename: string;
	file_size_bytes: number;
	page_count: number;
	course_name: string | null;
	subject: string | null;
	status: DocumentStatus;
	error_message: string | null;
	chunk_count: number;
	tags: Tag[];
	created_at: ISODateString;
	updated_at: ISODateString;
}

export interface DocumentListResponse {
	documents: Document[];
	total: number;
}

export interface DocumentListParams {
	course_name?: string;
	subject?: string;
	status?: DocumentStatus;
	offset?: number;
	limit?: number;
}

// ── Q&A ────────────────────────────────────────────────

export interface SourceReference {
	chunk_id: string;
	document_id: string;
	document_name: string;
	page_start: number;
	page_end: number;
	section_title: string | null;
	relevance_score: number;
	text_preview: string;
}

export interface AskRequest {
	question: string;
	document_ids?: string[] | null;
	top_k?: number;
}

export interface AskResponse {
	answer: string;
	sources: SourceReference[];
	model: string;
}

export interface SearchRequest {
	query: string;
	document_ids?: string[] | null;
	top_k?: number;
}

export interface SearchResult {
	chunk_id: string;
	document_id: string;
	document_name: string;
	content: string;
	page_start: number;
	page_end: number;
	section_title: string | null;
	score: number;
}

export interface SearchResponse {
	results: SearchResult[];
	query: string;
}

// ── Summaries ──────────────────────────────────────────

export type DetailLevel = "brief" | "standard" | "detailed";

export interface SummaryRequest {
	topic?: string | null;
	document_id?: string | null;
	page_start?: number | null;
	page_end?: number | null;
	detail_level?: DetailLevel;
}

export interface SummarySource {
	document_name: string;
	pages: string;
	chunk_id: string;
}

export interface SummaryResponse {
	summary: string;
	topic: string;
	sources: SummarySource[];
	model: string;
}

// ── Quizzes ────────────────────────────────────────────

export type QuestionType = "mcq" | "short_answer";

export interface MCQOption {
	label: string;
	text: string;
	is_correct: boolean;
}

export interface QuizQuestion {
	id: string;
	question_type: QuestionType;
	question_text: string;
	options: MCQOption[] | null;
	source_pages: string | null;
}

export interface QuizQuestionWithAnswer extends QuizQuestion {
	correct_answer: string;
	explanation: string | null;
}

export interface Quiz {
	id: string;
	title: string;
	topic: string | null;
	document_id: string | null;
	question_count: number;
	questions: QuizQuestion[];
	created_at: ISODateString;
}

export interface QuizListResponse {
	quizzes: Quiz[];
	total: number;
}

export interface QuizGenerateRequest {
	document_id?: string | null;
	topic?: string | null;
	question_count?: number;
	question_types?: QuestionType[];
}

// ── Quiz Attempts ──────────────────────────────────────

export interface AnswerSubmission {
	question_id: string;
	answer: string;
}

export interface QuizAttemptRequest {
	answers: AnswerSubmission[];
}

export interface QuestionFeedback {
	question_id: string;
	question_text: string;
	user_answer: string;
	correct_answer: string;
	is_correct: boolean;
	explanation: string | null;
	feedback: string | null;
	source_pages: string | null;
}

export interface QuizAttemptResponse {
	quiz_id: string;
	total_questions: number;
	correct_count: number;
	score_percentage: number;
	feedback: QuestionFeedback[];
}

// ── Quiz Results / Progress ────────────────────────────

export interface TopicStrength {
	topic: string;
	total_questions: number;
	correct_count: number;
	accuracy: number;
	needs_reinforcement: boolean;
}

export interface QuizResultsResponse {
	quiz_id: string;
	title: string;
	attempts_count: number;
	best_score: number;
	topic_strengths: TopicStrength[];
}
