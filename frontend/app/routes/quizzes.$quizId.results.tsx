import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, RotateCcw } from "lucide-react";
import { useNavigate, useParams } from "react-router";
import { Badge } from "~/components/ui/badge";
import { Button } from "~/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "~/components/ui/card";
import { Progress } from "~/components/ui/progress";
import { Skeleton } from "~/components/ui/skeleton";
import { getQuizResults } from "~/lib/api";
import type { TopicStrength } from "~/lib/types";

// ── Loading skeleton ───────────────────────────────────

function PageSkeleton() {
	return (
		<div className="space-y-6">
			<Skeleton className="h-8 w-1/2" />
			<div className="grid grid-cols-3 gap-3">
				<Skeleton className="h-24" />
				<Skeleton className="h-24" />
				<Skeleton className="h-24" />
			</div>
			<Skeleton className="h-40 w-full" />
		</div>
	);
}

// ── Main Page ──────────────────────────────────────────

export default function QuizResultsPage() {
	const { quizId } = useParams();
	const navigate = useNavigate();

	const { data, isLoading, isError, error } = useQuery({
		queryKey: ["quiz-results", quizId],
		queryFn: () => getQuizResults(quizId!),
		enabled: !!quizId,
	});

	if (isLoading) return <PageSkeleton />;

	if (isError) {
		return (
			<div className="py-8 text-center">
				<p className="text-sm text-destructive">
					Failed to load results: {error.message}
				</p>
				<Button
					variant="outline"
					size="sm"
					className="mt-4"
					onClick={() => navigate("/quizzes")}
				>
					<ArrowLeft />
					Back to quizzes
				</Button>
			</div>
		);
	}

	if (!data) return null;

	const needsReviewCount = data.topic_strengths.filter(
		(t) => t.needs_reinforcement,
	).length;

	return (
		<div className="space-y-6">
			{/* Header */}
			<div className="flex items-start justify-between">
				<div>
					<h1 className="text-2xl font-bold tracking-tight">Quiz Results</h1>
					<p className="text-muted-foreground">{data.title}</p>
				</div>
				<div className="flex gap-2">
					<Button size="sm" onClick={() => navigate(`/quizzes/${quizId}/take`)}>
						<RotateCcw />
						Retake
					</Button>
					<Button
						variant="ghost"
						size="sm"
						onClick={() => navigate("/quizzes")}
					>
						<ArrowLeft />
						Back
					</Button>
				</div>
			</div>

			{/* Score overview */}
			<div className="grid grid-cols-3 gap-3">
				<Card>
					<CardContent className="pt-6 text-center">
						<p className="text-3xl font-bold tabular-nums">
							{data.best_score.toFixed(0)}%
						</p>
						<p className="text-xs text-muted-foreground">Best Score</p>
						<p className="mt-1 text-xs text-muted-foreground">
							{scoreMessage(data.best_score)}
						</p>
					</CardContent>
				</Card>
				<Card>
					<CardContent className="pt-6 text-center">
						<p className="text-3xl font-bold tabular-nums">
							{data.attempts_count}
						</p>
						<p className="text-xs text-muted-foreground">Attempts</p>
					</CardContent>
				</Card>
				<Card>
					<CardContent className="pt-6 text-center">
						<p className="text-3xl font-bold tabular-nums">
							{data.topic_strengths.length}
						</p>
						<p className="text-xs text-muted-foreground">Topics</p>
						<p className="mt-1 text-xs text-muted-foreground">
							{needsReviewCount > 0
								? `${needsReviewCount} need review`
								: "All good"}
						</p>
					</CardContent>
				</Card>
			</div>

			{/* Topic strengths */}
			{data.topic_strengths.length > 0 && (
				<Card>
					<CardHeader>
						<CardTitle>Topic Strengths</CardTitle>
						<CardDescription>See how you performed by topic.</CardDescription>
					</CardHeader>
					<CardContent className="space-y-4">
						{data.topic_strengths.map((ts) => (
							<TopicStrengthRow key={ts.topic} strength={ts} />
						))}
					</CardContent>
				</Card>
			)}
		</div>
	);
}

// ── Topic Strength Row ─────────────────────────────────

function TopicStrengthRow({ strength }: { strength: TopicStrength }) {
	const pct = Math.round(strength.accuracy * 100);

	return (
		<div className="space-y-2">
			<div className="flex items-center justify-between">
				<div className="flex items-center gap-2">
					<span className="text-sm font-medium">{strength.topic}</span>
					{strength.needs_reinforcement && (
						<Badge variant="secondary">Needs review</Badge>
					)}
				</div>
				<span className="text-sm tabular-nums text-muted-foreground">
					{strength.correct_count}/{strength.total_questions} ({pct}%)
				</span>
			</div>
			<Progress value={Math.max(pct, 2)} />
		</div>
	);
}

// ── Helpers ────────────────────────────────────────────

function scoreMessage(score: number): string {
	if (score >= 80) return "Great job!";
	if (score >= 50) return "Room for improvement";
	return "Consider reviewing this material";
}
