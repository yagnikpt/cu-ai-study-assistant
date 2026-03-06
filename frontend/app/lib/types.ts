// ── Shared / Common ────────────────────────────────────

/** ISO-8601 date string returned by the backend */
export type ISODateString = string;

// ── Auth / User ────────────────────────────────────────

export interface User {
	id: string;
	username: string;
	email: string | null;
	avatar_url: string | null;
	created_at: ISODateString;
}

// ── Spaces ─────────────────────────────────────────────

export interface Space {
	id: string;
	name: string;
	description: string | null;
	document_count: number;
	created_at: ISODateString;
	updated_at: ISODateString;
}

export interface SpaceCreateRequest {
	name: string;
	description?: string | null;
}

export interface SpaceUpdateRequest {
	name?: string | null;
	description?: string | null;
}

export interface SpaceListResponse {
	spaces: Space[];
	total: number;
}
// ── Tags ───────────────────────────────────────────────

export interface Tag {
	id: string;
	name: string;
	color: string | null;
	space_id: string;
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

export type DocumentStatus = "processing" | "ready" | "failed";

export type IngestionProgress =
	| "uploading"
	| "parsing"
	| "chunking"
	| "embedding"
	| "storing"
	| "done";

export type ImageIngestionProgress =
	| "pending"
	| "uploading"
	| "embedding"
	| "storing"
	| "done"
	| "skipped";

export interface DocumentChunk {
	id: string;
	chunk_index: number;
	content: string;
	page_start: number;
	page_end: number;
	section_title: string | null;
	token_count: number;
}

export interface DocumentImage {
	id: string;
	gcs_url: string;
	page_number: number | null;
	image_index: number;
	mime_type: string;
	caption: string | null;
	created_at: ISODateString;
}

export interface Document {
	id: string;
	filename: string;
	original_filename: string;
	file_size_bytes: number;
	page_count: number;
	status: DocumentStatus;
	progress: IngestionProgress | null;
	images_progress: ImageIngestionProgress | null;
	error_message: string | null;
	chunk_count: number;
	image_count: number;
	tags: Tag[];
	created_at: ISODateString;
	updated_at: ISODateString;
}

export interface DocumentListResponse {
	documents: Document[];
	total: number;
}

export interface DocumentListParams {
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

export interface ImageReference {
	image_id: string;
	image_url: string;
	document_id: string;
	document_name: string;
	page_number: number | null;
	caption: string | null;
	relevance_score: number;
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
	document_id: string;
}

export interface SummaryResponse {
	summary: string;
	topic: string;
	sources: SummarySource[];
	images: ImageReference[];
	model: string;
}

// ── Q&A SSE Events ────────────────────────────────────

/** First event — array of source references */
export interface QASourcesEvent {
	type: "sources";
	data: SourceReference[];
}

/** Second event (optional) — array of relevant images */
export interface QAImagesEvent {
	type: "images";
	data: ImageReference[];
}

/** Repeated — each text fragment */
export interface QATokenEvent {
	type: "token";
	data: string;
}

/** Final event */
export interface QADoneEvent {
	type: "done";
	data: { model: string };
}

export type QAStreamEvent =
	| QASourcesEvent
	| QAImagesEvent
	| QATokenEvent
	| QADoneEvent;

// ── Summary SSE Events ────────────────────────────────

/** First event — topic + sources */
export interface SummaryMetaEvent {
	type: "meta";
	data: { topic: string; sources: SummarySource[] };
}

/** Second event (optional) — array of relevant images */
export interface SummaryImagesEvent {
	type: "images";
	data: ImageReference[];
}

/** Repeated — each text fragment */
export interface SummaryTokenEvent {
	type: "token";
	data: string;
}

/** Final event */
export interface SummaryDoneEvent {
	type: "done";
	data: { model: string };
}

export type SummaryStreamEvent =
	| SummaryMetaEvent
	| SummaryImagesEvent
	| SummaryTokenEvent
	| SummaryDoneEvent;

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

// ── Study Plans ───────────────────────────────────────

export type TopicPriority = "high" | "medium" | "low";
export type TopicDifficulty = "hard" | "medium" | "easy";

export interface StudyTopic {
	id: string;
	title: string;
	description: string;
	priority: TopicPriority;
	difficulty: TopicDifficulty;
	estimated_hours: number;
	source_pages: string | null;
	order_index: number;
	completed: boolean;
	completed_at: ISODateString | null;
}

export interface StudySession {
	date: string;
	topic_id: string;
	topic_title: string;
	session_type: "learn" | "review";
	duration_hours: number;
}

export interface StudyPlan {
	id: string;
	title: string;
	exam_date: ISODateString | null;
	daily_hours: number;
	status: "generating" | "ready" | "failed";
	error_message: string | null;
	topics: StudyTopic[];
	schedule: StudySession[];
	created_at: ISODateString;
	updated_at: ISODateString;
}

export interface StudyPlanListResponse {
	plans: StudyPlan[];
	total: number;
}

export interface StudyPlanGenerateRequest {
	document_ids?: string[] | null;
	exam_date?: string | null;
	daily_hours?: number;
}

// ── Analytics ─────────────────────────────────────────

export interface DocumentStats {
	total: number;
	ready: number;
	processing: number;
	failed: number;
}

export interface QuizScorePoint {
	date: string;
	score: number;
}

export interface TopicStrengthItem {
	topic: string;
	accuracy: number;
	total_questions: number;
}

export interface StudyPlanAnalytics {
	total_plans: number;
	topics_total: number;
	topics_completed: number;
	estimated_hours: number;
}

export interface ActivityDay {
	date: string;
	documents: number;
	quizzes: number;
	plans: number;
}

export interface ProfileAnalytics {
	spaces_count: number;
	document_stats: DocumentStats;
	quiz_count: number;
	quiz_attempts_count: number;
	quiz_avg_score: number;
	quiz_score_trend: QuizScorePoint[];
	topic_strengths: TopicStrengthItem[];
	study_plan_stats: StudyPlanAnalytics;
	activity: ActivityDay[];
}
