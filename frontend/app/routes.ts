import {
	index,
	layout,
	type RouteConfig,
	route,
} from "@react-router/dev/routes";

export default [
	// Redirect "/" → "/documents"
	index("routes/index.tsx"),

	// All pages share the sidebar layout
	layout("components/layout.tsx", [
		route("documents", "routes/documents.tsx"),
		route("qa", "routes/qa.tsx"),
		route("summaries", "routes/summaries.tsx"),
		route("quizzes", "routes/quizzes.tsx"),
		route("quizzes/:quizId/take", "routes/quizzes.$quizId.take.tsx"),
		route("quizzes/:quizId/results", "routes/quizzes.$quizId.results.tsx"),
	]),
] satisfies RouteConfig;
