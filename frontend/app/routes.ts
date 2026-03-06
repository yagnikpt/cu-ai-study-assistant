import {
	index,
	layout,
	type RouteConfig,
	route,
} from "@react-router/dev/routes";

export default [
	// Redirect "/" → "/spaces"
	index("routes/index.tsx"),

	// Login page — no auth required
	route("login", "routes/login.tsx"),

	// Spaces list — auth required (handled in AuthGate layout)
	route("spaces", "routes/spaces.tsx"),

	// Analytics — global, auth required
	route("analytics", "routes/analytics.tsx"),

	// All pages inside a space share the sidebar layout
	layout("components/layout.tsx", [
		route("spaces/:spaceId/documents", "routes/documents.tsx"),
		route("spaces/:spaceId/qa", "routes/qa.tsx"),
		route("spaces/:spaceId/summaries", "routes/summaries.tsx"),
		route("spaces/:spaceId/quizzes", "routes/quizzes.tsx"),
		route("spaces/:spaceId/flashcards", "routes/flashcards.tsx"),
		route("spaces/:spaceId/study-plans", "routes/study-plans.tsx"),
		route(
			"spaces/:spaceId/quizzes/:quizId/take",
			"routes/quizzes.$quizId.take.tsx",
		),
		route(
			"spaces/:spaceId/quizzes/:quizId/results",
			"routes/quizzes.$quizId.results.tsx",
		),
		route(
			"spaces/:spaceId/flashcards/:deckId/study",
			"routes/flashcards.$deckId.study.tsx",
		),
	]),
] satisfies RouteConfig;
