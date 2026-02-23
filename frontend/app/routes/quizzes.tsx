import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BarChart3, GraduationCap, Loader2, Play, Plus } from "lucide-react";
import { useState } from "react";
import { useNavigate, useParams } from "react-router";
import { Button } from "~/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "~/components/ui/card";
import {
	Collapsible,
	CollapsibleContent,
	CollapsibleTrigger,
} from "~/components/ui/collapsible";
import { Input } from "~/components/ui/input";
import { Label } from "~/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "~/components/ui/select";
import { Skeleton } from "~/components/ui/skeleton";
import { generateQuiz, listDocuments, listQuizzes } from "~/lib/api";
import type { QuestionType } from "~/lib/types";
import { cn } from "~/lib/utils";

// ── Main Page ──────────────────────────────────────────

export default function QuizzesPage() {
	const { spaceId } = useParams<{ spaceId: string }>();
	if (!spaceId) return null;

	return (
		<div className="space-y-8">
			<div>
				<h1 className="text-2xl font-bold tracking-tight">Quizzes</h1>
				<p className="text-muted-foreground">
					Generate and take quizzes based on your documents.
				</p>
			</div>

			<GenerateSection spaceId={spaceId} />
			<QuizList spaceId={spaceId} />
		</div>
	);
}

// ── Generate Section ───────────────────────────────────

function GenerateSection({ spaceId }: { spaceId: string }) {
	const navigate = useNavigate();
	const queryClient = useQueryClient();
	const [docId, setDocId] = useState("");
	const [topic, setTopic] = useState("");
	const [count, setCount] = useState(5);
	const [types, setTypes] = useState<QuestionType[]>(["mcq"]);

	const { data: docData } = useQuery({
		queryKey: ["documents", spaceId, { status: "ready", limit: 100 }],
		queryFn: () => listDocuments(spaceId, { status: "ready", limit: 100 }),
	});
	const docs = docData?.documents ?? [];

	const genMut = useMutation({
		mutationFn: () =>
			generateQuiz(spaceId, {
				document_id: docId || undefined,
				topic: topic || undefined,
				question_count: count,
				question_types: types.length > 0 ? types : undefined,
			}),
		onSuccess: (quiz) => {
			queryClient.invalidateQueries({ queryKey: ["quizzes"] });
			navigate(`/spaces/${spaceId}/quizzes/${quiz.id}/take`);
		},
	});

	const handleSubmit = (e: React.SubmitEvent) => {
		e.preventDefault();
		genMut.mutate();
	};

	const toggleType = (t: QuestionType) => {
		setTypes((prev) =>
			prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t],
		);
	};

	return (
		<Collapsible>
			<Card>
				<CollapsibleTrigger className="w-full">
					<CardHeader>
						<div className="flex items-center justify-between">
							<div className="text-left">
								<CardTitle>Generate a New Quiz</CardTitle>
								<CardDescription>Click to expand and configure</CardDescription>
							</div>
							<Plus className="size-5 text-muted-foreground transition-transform in-data-[state=open]:rotate-45" />
						</div>
					</CardHeader>
				</CollapsibleTrigger>

				<CollapsibleContent>
					<CardContent>
						<form onSubmit={handleSubmit} className="space-y-4">
							<div className="space-y-2">
								<Label>Document</Label>
								<Select
									value={docId || "all"}
									onValueChange={(v) => setDocId(v === "all" ? "" : v)}
								>
									<SelectTrigger className="w-full">
										<SelectValue placeholder="Select a document" />
									</SelectTrigger>
									<SelectContent>
										<SelectItem value="all">(all documents)</SelectItem>
										{docs.map((d) => (
											<SelectItem key={d.id} value={d.id}>
												{d.original_filename}
											</SelectItem>
										))}
									</SelectContent>
								</Select>
							</div>

							<div className="space-y-2">
								<Label htmlFor="quiz-topic">Topic (optional)</Label>
								<Input
									id="quiz-topic"
									placeholder="e.g. Photosynthesis, Chapter 3..."
									value={topic}
									onChange={(e) => setTopic(e.target.value)}
								/>
							</div>

							<div className="grid grid-cols-2 gap-4">
								{/* Question count */}
								<div className="space-y-2">
									<Label htmlFor="q-count">Number of questions: {count}</Label>
									<input
										id="q-count"
										type="range"
										min={1}
										max={20}
										value={count}
										onChange={(e) => setCount(Number(e.target.value))}
										className="w-full accent-primary"
									/>
								</div>

								{/* Question types */}
								<div className="space-y-2">
									<Label>Question types</Label>
									<div className="flex gap-2">
										{(["mcq", "short_answer"] as const).map((t) => {
											const selected = types.includes(t);
											return (
												<button
													key={t}
													type="button"
													onClick={() => toggleType(t)}
													className={cn(
														"rounded-full border px-3 py-1 text-xs transition-colors",
														selected
															? "border-primary bg-primary/10 text-primary"
															: "border-border text-muted-foreground hover:border-muted-foreground",
													)}
												>
													{t === "mcq" ? "Multiple Choice" : "Short Answer"}
												</button>
											);
										})}
									</div>
								</div>
							</div>

							{genMut.isError && (
								<p className="text-sm text-destructive">
									Failed to generate quiz: {genMut.error.message}
								</p>
							)}

							<Button type="submit" disabled={genMut.isPending}>
								{genMut.isPending && <Loader2 className="animate-spin" />}
								Generate quiz
							</Button>
						</form>
					</CardContent>
				</CollapsibleContent>
			</Card>
		</Collapsible>
	);
}

// ── Quiz List ──────────────────────────────────────────

function QuizList({ spaceId }: { spaceId: string }) {
	const navigate = useNavigate();

	const { data, isLoading, isError, error } = useQuery({
		queryKey: ["quizzes", spaceId],
		queryFn: () => listQuizzes(spaceId),
	});

	return (
		<Card>
			<CardHeader>
				<CardTitle>Your Quizzes</CardTitle>
				{data && (
					<CardDescription>
						{data.total} quiz{data.total === 1 ? "" : "zes"}
					</CardDescription>
				)}
			</CardHeader>
			<CardContent>
				{isLoading ? (
					<div className="space-y-3 py-6">
						<Skeleton className="h-4 w-3/4" />
						<Skeleton className="h-4 w-1/2" />
						<Skeleton className="h-4 w-2/3" />
					</div>
				) : isError ? (
					<p className="py-4 text-sm text-destructive">
						Failed to load quizzes: {error.message}
					</p>
				) : !data || data.quizzes.length === 0 ? (
					<div className="flex flex-col items-center justify-center py-12 text-center">
						<GraduationCap className="mb-3 size-10 text-muted-foreground" />
						<p className="font-medium">No quizzes yet</p>
						<p className="text-sm text-muted-foreground">
							Generate a quiz above to get started.
						</p>
					</div>
				) : (
					<div className="divide-y">
						{data.quizzes.map((q) => (
							<div
								key={q.id}
								className="flex items-center justify-between py-3 first:pt-0 last:pb-0"
							>
								<div className="min-w-0 flex-1">
									<p className="truncate text-sm font-medium">{q.title}</p>
									<div className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
										<span>{q.question_count} questions</span>
										{q.topic && (
											<>
												<span aria-hidden="true">&middot;</span>
												<span>{q.topic}</span>
											</>
										)}
									</div>
								</div>

								<div className="ml-4 flex shrink-0 gap-2">
									<Button
										size="sm"
										onClick={() => navigate(`/spaces/${spaceId}/quizzes/${q.id}/take`)}
									>
										<Play />
										Take
									</Button>
									<Button
										variant="outline"
										size="sm"
										onClick={() => navigate(`/spaces/${spaceId}/quizzes/${q.id}/results`)}
									>
										<BarChart3 />
										Results
									</Button>
								</div>
							</div>
						))}
					</div>
				)}
			</CardContent>
		</Card>
	);
}
