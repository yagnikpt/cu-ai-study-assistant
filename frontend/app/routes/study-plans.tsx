import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
	BookOpen,
	CalendarDays,
	Check,
	ChevronDown,
	ChevronUp,
	Clock,
	Loader2,
	Sparkles,
	Trash2,
} from "lucide-react";
import { useState } from "react";
import { useParams } from "react-router";
import { Badge } from "~/components/ui/badge";
import { Button } from "~/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "~/components/ui/card";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "~/components/ui/dialog";
import { Input } from "~/components/ui/input";
import { Label } from "~/components/ui/label";
import { Separator } from "~/components/ui/separator";
import { Skeleton } from "~/components/ui/skeleton";
import {
	deleteStudyPlan,
	generateStudyPlan,
	listStudyPlans,
	toggleTopicComplete,
} from "~/lib/api";
import type { StudyPlan, StudySession, StudyTopic } from "~/lib/types";

export default function StudyPlansPage() {
	const { spaceId } = useParams<{ spaceId: string }>();
	const [showGenerate, setShowGenerate] = useState(false);
	const [expandedPlan, setExpandedPlan] = useState<string | null>(null);

	const { data, isLoading, isError, error } = useQuery({
		queryKey: ["study-plans", spaceId],
		queryFn: () => listStudyPlans(spaceId!),
		enabled: !!spaceId,
	});

	return (
		<div>
			<div className="flex items-center justify-between mb-6">
				<div>
					<h1 className="text-2xl font-bold tracking-tight">Study Plans</h1>
					<p className="text-muted-foreground">
						AI-generated study plans with spaced repetition scheduling.
					</p>
				</div>
				<Button onClick={() => setShowGenerate(true)}>
					<Sparkles className="mr-2 size-4" />
					Generate Plan
				</Button>
			</div>

			{isLoading ? (
				<div className="space-y-4">
					{[...Array(2)].map((_, i) => (
						<Skeleton key={i} className="h-32 rounded-xl" />
					))}
				</div>
			) : isError ? (
				<p className="py-8 text-sm text-destructive text-center">
					Failed to load plans: {error.message}
				</p>
			) : data && data.plans.length === 0 ? (
				<div className="flex flex-col items-center justify-center py-20 text-center">
					<BookOpen className="mb-4 size-12 text-muted-foreground" />
					<h2 className="text-lg font-semibold">No study plans yet</h2>
					<p className="mt-1 text-sm text-muted-foreground max-w-sm">
						Generate an AI-powered study plan from your documents. It will break
						down topics, estimate study time, and create a spaced repetition
						schedule.
					</p>
					<Button className="mt-6" onClick={() => setShowGenerate(true)}>
						<Sparkles className="mr-2 size-4" />
						Generate your first plan
					</Button>
				</div>
			) : (
				<div className="space-y-4">
					{data?.plans.map((plan) => (
						<PlanCard
							key={plan.id}
							plan={plan}
							spaceId={spaceId!}
							expanded={expandedPlan === plan.id}
							onToggle={() =>
								setExpandedPlan(expandedPlan === plan.id ? null : plan.id)
							}
						/>
					))}
				</div>
			)}

			{showGenerate && (
				<GenerateDialog
					spaceId={spaceId!}
					onClose={() => setShowGenerate(false)}
				/>
			)}
		</div>
	);
}

// ── Plan Card ──────────────────────────────────────────

function PlanCard({
	plan,
	spaceId,
	expanded,
	onToggle,
}: {
	plan: StudyPlan;
	spaceId: string;
	expanded: boolean;
	onToggle: () => void;
}) {
	const queryClient = useQueryClient();
	const completedCount = plan.topics.filter((t) => t.completed).length;
	const totalHours = plan.topics.reduce((sum, t) => sum + t.estimated_hours, 0);
	const progress =
		plan.topics.length > 0
			? Math.round((completedCount / plan.topics.length) * 100)
			: 0;

	const deleteMut = useMutation({
		mutationFn: () => deleteStudyPlan(spaceId, plan.id),
		onSuccess: () =>
			queryClient.invalidateQueries({
				queryKey: ["study-plans", spaceId],
			}),
	});

	return (
		<Card>
			<CardHeader className="cursor-pointer" onClick={onToggle}>
				<div className="flex items-center justify-between">
					<div className="flex-1 min-w-0">
						<CardTitle className="text-lg">{plan.title}</CardTitle>
						<CardDescription className="flex items-center gap-3 mt-1">
							<span className="flex items-center gap-1">
								<BookOpen className="size-3.5" />
								{plan.topics.length} topics
							</span>
							<span className="flex items-center gap-1">
								<Clock className="size-3.5" />
								{totalHours.toFixed(1)}h total
							</span>
							{plan.exam_date && (
								<span className="flex items-center gap-1">
									<CalendarDays className="size-3.5" />
									Exam: {new Date(plan.exam_date).toLocaleDateString()}
								</span>
							)}
						</CardDescription>
					</div>
					<div className="flex items-center gap-3">
						{/* Progress bar */}
						<div className="flex items-center gap-2">
							<div className="w-24 h-2 bg-muted rounded-full overflow-hidden">
								<div
									className="h-full bg-primary rounded-full transition-all"
									style={{ width: `${progress}%` }}
								/>
							</div>
							<span className="text-xs text-muted-foreground min-w-[3ch]">
								{progress}%
							</span>
						</div>
						<Button
							variant="ghost"
							size="icon"
							className="size-8"
							onClick={(e) => {
								e.stopPropagation();
								if (confirm(`Delete "${plan.title}"?`)) deleteMut.mutate();
							}}
						>
							<Trash2 className="size-4 text-destructive" />
						</Button>
						{expanded ? (
							<ChevronUp className="size-4 text-muted-foreground" />
						) : (
							<ChevronDown className="size-4 text-muted-foreground" />
						)}
					</div>
				</div>
			</CardHeader>

			{expanded && (
				<CardContent className="space-y-6">
					<Separator />

					{/* Topics list */}
					<div>
						<h3 className="text-sm font-semibold mb-3">Topics</h3>
						<div className="space-y-2">
							{plan.topics.map((topic) => (
								<TopicRow
									key={topic.id}
									topic={topic}
									planId={plan.id}
									spaceId={spaceId}
								/>
							))}
						</div>
					</div>

					{/* Schedule */}
					{plan.schedule.length > 0 && (
						<div>
							<h3 className="text-sm font-semibold mb-3">Schedule</h3>
							<ScheduleView sessions={plan.schedule} />
						</div>
					)}
				</CardContent>
			)}
		</Card>
	);
}

// ── Topic Row ──────────────────────────────────────────

function TopicRow({
	topic,
	planId,
	spaceId,
}: {
	topic: StudyTopic;
	planId: string;
	spaceId: string;
}) {
	const queryClient = useQueryClient();

	const toggleMut = useMutation({
		mutationFn: () =>
			toggleTopicComplete(spaceId, planId, topic.id, !topic.completed),
		onSuccess: () =>
			queryClient.invalidateQueries({
				queryKey: ["study-plans", spaceId],
			}),
	});

	const priorityColor = {
		high: "text-red-600 bg-red-50 dark:bg-red-950/30",
		medium: "text-amber-600 bg-amber-50 dark:bg-amber-950/30",
		low: "text-green-600 bg-green-50 dark:bg-green-950/30",
	}[topic.priority];

	const difficultyColor = {
		hard: "text-red-600 bg-red-50 dark:bg-red-950/30",
		medium: "text-amber-600 bg-amber-50 dark:bg-amber-950/30",
		easy: "text-green-600 bg-green-50 dark:bg-green-950/30",
	}[topic.difficulty];

	return (
		<div
			className={`flex items-start gap-3 p-3 rounded-lg border transition-colors ${topic.completed ? "bg-muted/50 opacity-60" : ""}`}
		>
			<button
				type="button"
				onClick={() => toggleMut.mutate()}
				disabled={toggleMut.isPending}
				className={`mt-0.5 flex size-5 shrink-0 items-center justify-center rounded border-2 transition-colors ${
					topic.completed
						? "bg-primary border-primary text-primary-foreground"
						: "border-muted-foreground/30 hover:border-primary"
				}`}
			>
				{topic.completed && <Check className="size-3" />}
			</button>

			<div className="flex-1 min-w-0">
				<div className="flex items-center gap-2 flex-wrap">
					<span
						className={`font-medium text-sm ${topic.completed ? "line-through" : ""}`}
					>
						{topic.title}
					</span>
					<Badge
						variant="outline"
						className={`text-[10px] px-1.5 py-0 ${priorityColor}`}
					>
						{topic.priority}
					</Badge>
					<Badge
						variant="outline"
						className={`text-[10px] px-1.5 py-0 ${difficultyColor}`}
					>
						{topic.difficulty}
					</Badge>
				</div>
				<p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
					{topic.description}
				</p>
				<div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
					<span className="flex items-center gap-1">
						<Clock className="size-3" />
						{topic.estimated_hours}h
					</span>
					{topic.source_pages && (
						<span className="truncate">{topic.source_pages}</span>
					)}
				</div>
			</div>
		</div>
	);
}

// ── Schedule View ──────────────────────────────────────

function ScheduleView({ sessions }: { sessions: StudySession[] }) {
	// Group sessions by date
	const grouped = sessions.reduce(
		(acc, session) => {
			if (!acc[session.date]) acc[session.date] = [];
			acc[session.date].push(session);
			return acc;
		},
		{} as Record<string, StudySession[]>,
	);

	return (
		<div className="space-y-3">
			{Object.entries(grouped).map(([date, daySessions]) => (
				<div key={date} className="flex gap-3">
					<div className="w-20 shrink-0 text-xs text-muted-foreground pt-0.5">
						{new Date(date + "T00:00:00").toLocaleDateString(undefined, {
							month: "short",
							day: "numeric",
							weekday: "short",
						})}
					</div>
					<div className="flex-1 space-y-1">
						{daySessions.map((s, i) => (
							<div
								key={`${s.topic_id}-${s.session_type}-${i}`}
								className="flex items-center gap-2 text-sm"
							>
								<Badge
									variant={s.session_type === "learn" ? "default" : "secondary"}
									className="text-[10px] px-1.5 py-0"
								>
									{s.session_type}
								</Badge>
								<span className="truncate">{s.topic_title}</span>
								<span className="text-xs text-muted-foreground ml-auto shrink-0">
									{s.duration_hours}h
								</span>
							</div>
						))}
					</div>
				</div>
			))}
		</div>
	);
}

// ── Generate Dialog ────────────────────────────────────

function GenerateDialog({
	spaceId,
	onClose,
}: {
	spaceId: string;
	onClose: () => void;
}) {
	const queryClient = useQueryClient();
	const [examDate, setExamDate] = useState("");
	const [dailyHours, setDailyHours] = useState("2");

	const genMut = useMutation({
		mutationFn: () =>
			generateStudyPlan(spaceId, {
				exam_date: examDate || undefined,
				daily_hours: Number.parseFloat(dailyHours) || 2,
			}),
		onSuccess: () => {
			queryClient.invalidateQueries({
				queryKey: ["study-plans", spaceId],
			});
			onClose();
		},
	});

	const handleSubmit = (e: React.FormEvent) => {
		e.preventDefault();
		genMut.mutate();
	};

	return (
		<Dialog open onOpenChange={(open) => !open && onClose()}>
			<DialogContent>
				<DialogHeader>
					<DialogTitle>Generate Study Plan</DialogTitle>
					<DialogDescription>
						AI will analyze your documents and create a structured study plan
						with topic breakdowns, time estimates, and a spaced repetition
						schedule.
					</DialogDescription>
				</DialogHeader>

				<form onSubmit={handleSubmit} className="space-y-4">
					<div className="space-y-2">
						<Label htmlFor="exam-date">Exam Date (optional)</Label>
						<Input
							id="exam-date"
							type="date"
							value={examDate}
							onChange={(e) => setExamDate(e.target.value)}
						/>
						<p className="text-xs text-muted-foreground">
							Sets the deadline for the schedule. Leave empty for a self-paced
							plan.
						</p>
					</div>

					<div className="space-y-2">
						<Label htmlFor="daily-hours">Study Hours per Day</Label>
						<Input
							id="daily-hours"
							type="number"
							step="0.5"
							min="0.5"
							max="12"
							value={dailyHours}
							onChange={(e) => setDailyHours(e.target.value)}
						/>
					</div>

					{genMut.isError && (
						<p className="text-sm text-destructive">{genMut.error.message}</p>
					)}

					<DialogFooter>
						<Button type="button" variant="outline" onClick={onClose}>
							Cancel
						</Button>
						<Button type="submit" disabled={genMut.isPending}>
							{genMut.isPending ? (
								<>
									<Loader2 className="animate-spin mr-2 size-4" />
									Analyzing docs...
								</>
							) : (
								<>
									<Sparkles className="mr-2 size-4" />
									Generate
								</>
							)}
						</Button>
					</DialogFooter>
				</form>
			</DialogContent>
		</Dialog>
	);
}
