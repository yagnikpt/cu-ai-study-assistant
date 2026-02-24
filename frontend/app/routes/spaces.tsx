import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
	ArrowRight,
	BookOpen,
	CalendarDays,
	CheckCircle,
	FileText,
	FolderOpen,
	GraduationCap,
	Loader2,
	LogOut,
	Plus,
	Trash2,
	TrendingUp,
} from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router";
import {
	Area,
	AreaChart,
	Bar,
	BarChart,
	CartesianGrid,
	Cell,
	Label,
	Line,
	LineChart,
	Pie,
	PieChart,
	XAxis,
	YAxis,
} from "recharts";
import { AuthProvider, useAuth } from "~/components/AuthProvider";
import { Avatar, AvatarFallback, AvatarImage } from "~/components/ui/avatar";
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
	type ChartConfig,
	ChartContainer,
	ChartTooltip,
	ChartTooltipContent,
} from "~/components/ui/chart";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "~/components/ui/dialog";
import { Input } from "~/components/ui/input";
import { Label as FormLabel } from "~/components/ui/label";
import { Separator } from "~/components/ui/separator";
import { Skeleton } from "~/components/ui/skeleton";
import {
	createSpace,
	deleteSpace,
	getProfileAnalytics,
	listSpaces,
	logout,
} from "~/lib/api";

export default function SpacesPage() {
	return (
		<AuthProvider>
			<SpacesContent />
		</AuthProvider>
	);
}

function SpacesContent() {
	const { user } = useAuth();
	const navigate = useNavigate();
	const queryClient = useQueryClient();
	const [showCreate, setShowCreate] = useState(false);

	const { data, isLoading, isError, error } = useQuery({
		queryKey: ["spaces"],
		queryFn: listSpaces,
	});

	const handleLogout = async () => {
		await logout();
		queryClient.clear();
		navigate("/login");
	};

	return (
		<div className="mx-auto w-full max-w-5xl px-6 py-8">
			{/* Header */}
			<div className="flex items-center justify-between mb-8">
				<div className="flex items-center gap-3">
					<GraduationCap className="size-8 text-primary" />
					<div>
						<h1 className="text-2xl font-bold tracking-tight">
							{user ? `Hi, ${user.username}` : "Study Assistant"}
						</h1>
						<p className="text-muted-foreground">
							Your study dashboard &amp; spaces.
						</p>
					</div>
				</div>
				<div className="flex items-center gap-3">
					{user && (
						<div className="flex items-center gap-2">
							<Avatar className="size-8">
								<AvatarImage
									src={user.avatar_url ?? undefined}
									alt={user.username}
								/>
								<AvatarFallback>
									{user.username[0]?.toUpperCase()}
								</AvatarFallback>
							</Avatar>
							<Button variant="ghost" size="sm" onClick={handleLogout}>
								<LogOut className="size-4" />
								Logout
							</Button>
						</div>
					)}
				</div>
			</div>

			{/* Analytics Dashboard */}
			<AnalyticsDashboard />

			<Separator className="my-8" />

			{/* Spaces header */}
			<div className="flex items-center justify-between mb-4">
				<h2 className="text-lg font-semibold">Your Spaces</h2>
				<Button size="sm" onClick={() => setShowCreate(true)}>
					<Plus className="mr-1 size-4" />
					New Space
				</Button>
			</div>

			{/* Spaces grid */}
			{isLoading ? (
				<div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
					{[...Array(3)].map((_, i) => (
						<Skeleton key={i} className="h-40 rounded-xl" />
					))}
				</div>
			) : isError ? (
				<p className="py-8 text-sm text-destructive text-center">
					Failed to load spaces: {error.message}
				</p>
			) : data && data.spaces.length === 0 ? (
				<div className="flex flex-col items-center justify-center py-20 text-center">
					<FolderOpen className="mb-4 size-12 text-muted-foreground" />
					<h2 className="text-lg font-semibold">No spaces yet</h2>
					<p className="mt-1 text-sm text-muted-foreground max-w-sm">
						Spaces help you organize your study materials. Create your first
						space to get started.
					</p>
					<Button className="mt-6" onClick={() => setShowCreate(true)}>
						<Plus />
						Create your first space
					</Button>
				</div>
			) : (
				<div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
					{data?.spaces.map((space) => (
						<SpaceCard
							key={space.id}
							id={space.id}
							name={space.name}
							description={space.description}
							documentCount={space.document_count}
							createdAt={space.created_at}
							onClick={() => navigate(`/spaces/${space.id}/documents`)}
						/>
					))}
				</div>
			)}

			{showCreate && (
				<CreateSpaceDialog
					onClose={() => setShowCreate(false)}
					onCreated={(id) => navigate(`/spaces/${id}/documents`)}
				/>
			)}
		</div>
	);
}

// ── Analytics Dashboard ────────────────────────────────

const scoreTrendConfig = {
	score: { label: "Score", color: "hsl(221, 83%, 53%)" },
} satisfies ChartConfig;

const progressConfig = {
	completed: { label: "Completed", color: "hsl(142, 71%, 45%)" },
	remaining: { label: "Remaining", color: "hsl(215, 16%, 90%)" },
} satisfies ChartConfig;

const activityConfig = {
	documents: { label: "Documents", color: "hsl(221, 83%, 53%)" },
	quizzes: { label: "Quizzes", color: "hsl(262, 83%, 58%)" },
	plans: { label: "Plans", color: "hsl(142, 71%, 45%)" },
} satisfies ChartConfig;

const topicConfig = {
	accuracy: { label: "Accuracy", color: "hsl(221, 83%, 53%)" },
} satisfies ChartConfig;

function AnalyticsDashboard() {
	const { data: analytics, isLoading } = useQuery({
		queryKey: ["analytics"],
		queryFn: getProfileAnalytics,
	});

	if (isLoading) {
		return (
			<div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
				{[...Array(4)].map((_, i) => (
					<Skeleton key={i} className="h-24 rounded-xl" />
				))}
			</div>
		);
	}

	if (!analytics) return null;

	const planProgress =
		analytics.study_plan_stats.topics_total > 0
			? Math.round(
					(analytics.study_plan_stats.topics_completed /
						analytics.study_plan_stats.topics_total) *
						100,
				)
			: 0;

	const donutData = [
		{
			name: "completed",
			value: analytics.study_plan_stats.topics_completed,
			fill: "var(--color-completed)",
		},
		{
			name: "remaining",
			value:
				analytics.study_plan_stats.topics_total -
				analytics.study_plan_stats.topics_completed,
			fill: "var(--color-remaining)",
		},
	];

	return (
		<div className="space-y-4">
			{/* Stat cards */}
			<div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
				<StatCard
					icon={FileText}
					label="Documents"
					value={analytics.document_stats.total}
					sub={`${analytics.document_stats.ready} ready`}
				/>
				<StatCard
					icon={GraduationCap}
					label="Quiz Average"
					value={`${analytics.quiz_avg_score}%`}
					sub={`${analytics.quiz_attempts_count} attempts`}
				/>
				<StatCard
					icon={CalendarDays}
					label="Study Plans"
					value={analytics.study_plan_stats.total_plans}
					sub={`${analytics.study_plan_stats.estimated_hours}h estimated`}
				/>
				<StatCard
					icon={CheckCircle}
					label="Topics Done"
					value={`${analytics.study_plan_stats.topics_completed}/${analytics.study_plan_stats.topics_total}`}
					sub={`${planProgress}% complete`}
				/>
			</div>

			{/* Charts row */}
			<div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
				{/* Quiz score trend */}
				<Card>
					<CardHeader className="pb-2">
						<CardTitle className="text-sm font-medium flex items-center gap-2">
							<TrendingUp className="size-4" />
							Quiz Score Trend
						</CardTitle>
					</CardHeader>
					<CardContent>
						{analytics.quiz_score_trend.length > 0 ? (
							<ChartContainer
								config={scoreTrendConfig}
								className="h-[160px] w-full"
							>
								<LineChart data={analytics.quiz_score_trend} accessibilityLayer>
									<CartesianGrid vertical={false} />
									<XAxis
										dataKey="date"
										tickLine={false}
										axisLine={false}
										tickMargin={8}
										tickFormatter={(d: string) =>
											new Date(d).toLocaleDateString(undefined, {
												month: "short",
												day: "numeric",
											})
										}
									/>
									<YAxis
										domain={[0, 100]}
										tickLine={false}
										axisLine={false}
										tickFormatter={(v: number) => `${v}%`}
									/>
									<ChartTooltip content={<ChartTooltipContent />} />
									<Line
										type="monotone"
										dataKey="score"
										stroke="var(--color-score)"
										strokeWidth={2}
										dot={{ r: 3 }}
									/>
								</LineChart>
							</ChartContainer>
						) : (
							<EmptyChart label="No quiz attempts yet" />
						)}
					</CardContent>
				</Card>

				{/* Study plan donut */}
				<Card>
					<CardHeader className="pb-2">
						<CardTitle className="text-sm font-medium flex items-center gap-2">
							<BookOpen className="size-4" />
							Study Progress
						</CardTitle>
					</CardHeader>
					<CardContent>
						{analytics.study_plan_stats.topics_total > 0 ? (
							<ChartContainer
								config={progressConfig}
								className="h-[160px] w-full"
							>
								<PieChart>
									<ChartTooltip content={<ChartTooltipContent hideLabel />} />
									<Pie
										data={donutData}
										dataKey="value"
										nameKey="name"
										innerRadius={45}
										outerRadius={65}
										startAngle={90}
										endAngle={-270}
									>
										<Label
											content={({ viewBox }) => {
												if (viewBox && "cx" in viewBox && "cy" in viewBox) {
													return (
														<text
															x={viewBox.cx}
															y={viewBox.cy}
															textAnchor="middle"
															dominantBaseline="middle"
														>
															<tspan
																x={viewBox.cx}
																y={viewBox.cy}
																className="fill-foreground text-2xl font-bold"
															>
																{planProgress}%
															</tspan>
															<tspan
																x={viewBox.cx}
																y={(viewBox.cy ?? 0) + 18}
																className="fill-muted-foreground text-xs"
															>
																done
															</tspan>
														</text>
													);
												}
												return null;
											}}
										/>
									</Pie>
								</PieChart>
							</ChartContainer>
						) : (
							<EmptyChart label="No study plans yet" />
						)}
					</CardContent>
				</Card>

				{/* Activity */}
				<Card>
					<CardHeader className="pb-2">
						<CardTitle className="text-sm font-medium flex items-center gap-2">
							<CalendarDays className="size-4" />
							7-Day Activity
						</CardTitle>
					</CardHeader>
					<CardContent>
						{analytics.activity.length > 0 ? (
							<ChartContainer
								config={activityConfig}
								className="h-[160px] w-full"
							>
								<AreaChart data={analytics.activity} accessibilityLayer>
									<CartesianGrid vertical={false} />
									<XAxis
										dataKey="date"
										tickLine={false}
										axisLine={false}
										tickMargin={8}
										tickFormatter={(d: string) =>
											new Date(d).toLocaleDateString(undefined, {
												weekday: "short",
											})
										}
									/>
									<YAxis
										tickLine={false}
										axisLine={false}
										allowDecimals={false}
									/>
									<ChartTooltip content={<ChartTooltipContent />} />
									<Area
										type="monotone"
										dataKey="documents"
										stackId="1"
										stroke="var(--color-documents)"
										fill="var(--color-documents)"
										fillOpacity={0.3}
									/>
									<Area
										type="monotone"
										dataKey="quizzes"
										stackId="1"
										stroke="var(--color-quizzes)"
										fill="var(--color-quizzes)"
										fillOpacity={0.3}
									/>
									<Area
										type="monotone"
										dataKey="plans"
										stackId="1"
										stroke="var(--color-plans)"
										fill="var(--color-plans)"
										fillOpacity={0.3}
									/>
								</AreaChart>
							</ChartContainer>
						) : (
							<EmptyChart label="No activity yet" />
						)}
					</CardContent>
				</Card>
			</div>

			{/* Topic strengths */}
			{analytics.topic_strengths.length > 0 && (
				<Card>
					<CardHeader className="pb-2">
						<CardTitle className="text-sm font-medium">
							Topic Strengths
						</CardTitle>
						<CardDescription>
							Accuracy on quiz questions by topic (lowest first)
						</CardDescription>
					</CardHeader>
					<CardContent>
						<ChartContainer config={topicConfig} className="h-[200px] w-full">
							<BarChart
								data={analytics.topic_strengths}
								layout="vertical"
								margin={{ left: 20 }}
								accessibilityLayer
							>
								<CartesianGrid horizontal={false} />
								<XAxis
									type="number"
									domain={[0, 100]}
									tickLine={false}
									axisLine={false}
									tickFormatter={(v: number) => `${v}%`}
								/>
								<YAxis
									type="category"
									dataKey="topic"
									width={150}
									tickLine={false}
									axisLine={false}
								/>
								<ChartTooltip content={<ChartTooltipContent />} />
								<Bar dataKey="accuracy" radius={[0, 4, 4, 0]}>
									{analytics.topic_strengths.map((item) => (
										<Cell
											key={item.topic}
											fill={
												item.accuracy < 50
													? "hsl(0, 72%, 51%)"
													: item.accuracy < 75
														? "hsl(38, 92%, 50%)"
														: "hsl(142, 71%, 45%)"
											}
										/>
									))}
								</Bar>
							</BarChart>
						</ChartContainer>
					</CardContent>
				</Card>
			)}
		</div>
	);
}

function StatCard({
	icon: Icon,
	label,
	value,
	sub,
}: {
	icon: React.ComponentType<{ className?: string }>;
	label: string;
	value: string | number;
	sub: string;
}) {
	return (
		<Card>
			<CardContent className="pt-4 pb-3">
				<div className="flex items-center gap-3">
					<div className="rounded-lg bg-primary/10 p-2">
						<Icon className="size-5 text-primary" />
					</div>
					<div>
						<p className="text-2xl font-bold leading-none">{value}</p>
						<p className="text-xs text-muted-foreground mt-1">
							{label} &middot; {sub}
						</p>
					</div>
				</div>
			</CardContent>
		</Card>
	);
}

function EmptyChart({ label }: { label: string }) {
	return (
		<div className="flex items-center justify-center h-[160px] text-sm text-muted-foreground">
			{label}
		</div>
	);
}

// ── Space Card ─────────────────────────────────────────

function SpaceCard({
	id,
	name,
	description,
	documentCount,
	createdAt,
	onClick,
}: {
	id: string;
	name: string;
	description: string | null;
	documentCount: number;
	createdAt: string;
	onClick: () => void;
}) {
	const queryClient = useQueryClient();
	const deleteMut = useMutation({
		mutationFn: () => deleteSpace(id),
		onSuccess: () => queryClient.invalidateQueries({ queryKey: ["spaces"] }),
	});

	const date = new Date(createdAt).toLocaleDateString(undefined, {
		month: "short",
		day: "numeric",
		year: "numeric",
	});

	return (
		<Card className="group cursor-pointer transition-all hover:shadow-md hover:border-primary/40">
			<CardHeader className="pb-2" onClick={onClick}>
				<div className="flex items-start justify-between">
					<CardTitle className="text-base line-clamp-1">{name}</CardTitle>
					<ArrowRight className="size-4 shrink-0 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
				</div>
				{description && (
					<CardDescription className="line-clamp-2">
						{description}
					</CardDescription>
				)}
			</CardHeader>
			<CardContent onClick={onClick}>
				<div className="flex items-center gap-3 text-sm text-muted-foreground">
					<Badge variant="secondary" className="font-normal">
						{documentCount} {documentCount === 1 ? "doc" : "docs"}
					</Badge>
					<span className="text-xs">{date}</span>
				</div>
			</CardContent>
			<Separator />
			<div className="flex justify-end px-4 py-2">
				<Button
					variant="ghost"
					size="sm"
					className="text-destructive hover:text-destructive"
					onClick={(e) => {
						e.stopPropagation();
						if (confirm(`Delete space "${name}" and all its contents?`))
							deleteMut.mutate();
					}}
					disabled={deleteMut.isPending}
				>
					{deleteMut.isPending ? (
						<Loader2 className="animate-spin size-3.5" />
					) : (
						<Trash2 className="size-3.5" />
					)}
					Delete
				</Button>
			</div>
		</Card>
	);
}

// ── Create Space Dialog ────────────────────────────────

function CreateSpaceDialog({
	onClose,
	onCreated,
}: {
	onClose: () => void;
	onCreated: (id: string) => void;
}) {
	const queryClient = useQueryClient();
	const [name, setName] = useState("");
	const [description, setDescription] = useState("");

	const createMut = useMutation({
		mutationFn: () =>
			createSpace({ name, description: description || undefined }),
		onSuccess: (space) => {
			queryClient.invalidateQueries({ queryKey: ["spaces"] });
			onCreated(space.id);
		},
	});

	const handleSubmit = (e: React.FormEvent) => {
		e.preventDefault();
		if (name.trim()) createMut.mutate();
	};

	return (
		<Dialog open onOpenChange={(open) => !open && onClose()}>
			<DialogContent>
				<DialogHeader>
					<DialogTitle>Create a new space</DialogTitle>
					<DialogDescription>
						A space groups your study documents together. You can ask questions,
						generate summaries, and take quizzes within each space.
					</DialogDescription>
				</DialogHeader>

				<form onSubmit={handleSubmit} className="space-y-4">
					<div className="space-y-2">
						<FormLabel htmlFor="space-name">Name</FormLabel>
						<Input
							id="space-name"
							placeholder="e.g. CS 101 — Data Structures"
							value={name}
							onChange={(e) => setName(e.target.value)}
							autoFocus
						/>
					</div>
					<div className="space-y-2">
						<FormLabel htmlFor="space-desc">Description (optional)</FormLabel>
						<Input
							id="space-desc"
							placeholder="e.g. Fall 2026 semester materials"
							value={description}
							onChange={(e) => setDescription(e.target.value)}
						/>
					</div>

					{createMut.isError && (
						<p className="text-sm text-destructive">
							{createMut.error.message}
						</p>
					)}

					<DialogFooter>
						<Button type="button" variant="outline" onClick={onClose}>
							Cancel
						</Button>
						<Button
							type="submit"
							disabled={!name.trim() || createMut.isPending}
						>
							{createMut.isPending && <Loader2 className="animate-spin" />}
							Create
						</Button>
					</DialogFooter>
				</form>
			</DialogContent>
		</Dialog>
	);
}
