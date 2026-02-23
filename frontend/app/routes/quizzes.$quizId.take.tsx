import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowLeft, Loader2 } from "lucide-react";
import { useState } from "react";
import { useNavigate, useParams } from "react-router";
import { Badge } from "~/components/ui/badge";
import { Button } from "~/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "~/components/ui/card";
import { Label } from "~/components/ui/label";
import { RadioGroup, RadioGroupItem } from "~/components/ui/radio-group";
import { Skeleton } from "~/components/ui/skeleton";
import { Textarea } from "~/components/ui/textarea";
import { getQuiz, submitAttempt } from "~/lib/api";
import type { AnswerSubmission, QuizQuestion } from "~/lib/types";
import { cn } from "~/lib/utils";

// ── Loading skeleton ───────────────────────────────────

function PageSkeleton() {
	return (
		<div className="space-y-6">
			<Skeleton className="h-8 w-1/2" />
			<Skeleton className="h-4 w-1/3" />
			<div className="space-y-4">
				<Skeleton className="h-40 w-full" />
				<Skeleton className="h-40 w-full" />
				<Skeleton className="h-40 w-full" />
			</div>
		</div>
	);
}

// ── Main Page ──────────────────────────────────────────

export default function TakeQuizPage() {
	const { quizId } = useParams();
	const navigate = useNavigate();
	const [answers, setAnswers] = useState<Record<string, string>>({});

	const {
		data: quiz,
		isLoading,
		isError,
		error,
	} = useQuery({
		queryKey: ["quiz", quizId],
		queryFn: () => getQuiz(quizId!),
		enabled: !!quizId,
	});

	const submitMut = useMutation({
		mutationFn: (submissions: AnswerSubmission[]) =>
			submitAttempt(quizId!, { answers: submissions }),
		onSuccess: () => {
			navigate(`/quizzes/${quizId}/results`);
		},
	});

	const setAnswer = (questionId: string, value: string) => {
		setAnswers((prev) => ({ ...prev, [questionId]: value }));
	};

	const handleSubmit = (e: React.SubmitEvent) => {
		e.preventDefault();
		if (!quiz) return;

		const submissions: AnswerSubmission[] = quiz.questions.map((q) => ({
			question_id: q.id,
			answer: answers[q.id] ?? "",
		}));
		submitMut.mutate(submissions);
	};

	const answeredCount = quiz
		? quiz.questions.filter((q) => answers[q.id]?.trim()).length
		: 0;

	if (isLoading) return <PageSkeleton />;

	if (isError) {
		return (
			<div className="py-8 text-center">
				<p className="text-sm text-destructive">
					Failed to load quiz: {error.message}
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

	if (!quiz) return null;

	return (
		<div className="space-y-6">
			{/* Header */}
			<div className="flex items-start justify-between">
				<div>
					<h1 className="text-2xl font-bold tracking-tight">{quiz.title}</h1>
					<div className="mt-1 flex items-center gap-2 text-sm text-muted-foreground">
						{quiz.topic && <span>{quiz.topic}</span>}
						<Badge variant="outline">
							{answeredCount}/{quiz.questions.length} answered
						</Badge>
					</div>
				</div>
				<Button variant="ghost" size="sm" onClick={() => navigate("/quizzes")}>
					<ArrowLeft />
					Back
				</Button>
			</div>

			{/* Questions */}
			<form onSubmit={handleSubmit} className="space-y-4">
				{quiz.questions.map((q, idx) => (
					<QuestionCard
						key={q.id}
						question={q}
						index={idx + 1}
						value={answers[q.id] ?? ""}
						onChange={(v) => setAnswer(q.id, v)}
					/>
				))}

				{submitMut.isError && (
					<p className="text-sm text-destructive">
						Submit failed: {submitMut.error.message}
					</p>
				)}

				<div className="flex items-center gap-3">
					<Button type="submit" disabled={submitMut.isPending}>
						{submitMut.isPending && <Loader2 className="animate-spin" />}
						Submit answers
					</Button>
					<span className="text-sm text-muted-foreground">
						{answeredCount} of {quiz.questions.length} questions answered
					</span>
				</div>
			</form>
		</div>
	);
}

// ── Question Card ──────────────────────────────────────

function QuestionCard({
	question,
	index,
	value,
	onChange,
}: {
	question: QuizQuestion;
	index: number;
	value: string;
	onChange: (v: string) => void;
}) {
	const isMCQ = question.question_type === "mcq" && question.options;

	return (
		<Card>
			<CardHeader>
				<div className="flex items-start justify-between">
					<CardTitle className="text-sm font-medium">
						<span className="mr-1.5 text-primary">Q{index}.</span>
						{question.question_text}
					</CardTitle>
					<Badge variant="outline">
						{question.question_type === "mcq" ? "MCQ" : "Short Answer"}
					</Badge>
				</div>
				{question.source_pages && (
					<p className="text-xs text-muted-foreground">
						Source: pages {question.source_pages}
					</p>
				)}
			</CardHeader>
			<CardContent>
				{isMCQ ? (
					<RadioGroup value={value} onValueChange={onChange}>
						{question.options!.map((opt) => (
							<Label
								key={opt.label}
								htmlFor={`${question.id}-${opt.label}`}
								className={cn(
									"flex cursor-pointer items-center gap-3 rounded-lg border px-4 py-3 text-sm transition-colors",
									value === opt.label
										? "border-primary bg-primary/5"
										: "border-border hover:border-muted-foreground/50",
								)}
							>
								<RadioGroupItem
									value={opt.label}
									id={`${question.id}-${opt.label}`}
								/>
								<span>
									<span className="font-medium">{opt.label}.</span> {opt.text}
								</span>
							</Label>
						))}
					</RadioGroup>
				) : (
					<div className="space-y-2">
						<Label htmlFor={`sa-${question.id}`} className="sr-only">
							Your answer for question {index}
						</Label>
						<Textarea
							id={`sa-${question.id}`}
							rows={3}
							value={value}
							onChange={(e) => onChange(e.target.value)}
							placeholder="Type your answer..."
						/>
					</div>
				)}
			</CardContent>
		</Card>
	);
}
