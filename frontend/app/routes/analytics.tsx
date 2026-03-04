import { useQuery } from "@tanstack/react-query";
import {
	ArrowLeft,
	BookOpen,
	CalendarDays,
	CheckCircle,
	FileText,
	GraduationCap,
	TrendingUp,
} from "lucide-react";
import { Link } from "react-router";
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
import { AuthProvider } from "~/components/AuthProvider";
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
import { Skeleton } from "~/components/ui/skeleton";
import { getProfileAnalytics } from "~/lib/api";

// ── Chart Configs ──────────────────────────────────────

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

// ── Page ───────────────────────────────────────────────

export default function AnalyticsRoute() {
	return (
		<AuthProvider>
			<AnalyticsPage />
		</AuthProvider>
	);
}

function AnalyticsPage() {
	const { data: analytics, isLoading } = useQuery({
		queryKey: ["analytics"],
		queryFn: getProfileAnalytics,
	});

	if (isLoading) {
		return (
			<div className="mx-auto w-full max-w-5xl px-6 py-8">
				<div className="mb-6">
					<Button variant="ghost" size="sm" className="mb-2 -ml-2" asChild>
						<Link to="/spaces">
							<ArrowLeft className="size-4" />
							Back to Spaces
						</Link>
					</Button>
					<h1 className="text-2xl font-bold tracking-tight">Analytics</h1>
					<p className="text-muted-foreground">
						Your study metrics and progress at a glance.
					</p>
				</div>
				<div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
					{[...Array(4)].map((_, i) => (
						<Skeleton key={`stat-${i}`} className="h-24 rounded-xl" />
					))}
				</div>
				<div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 mt-4">
					{[...Array(3)].map((_, i) => (
						<Skeleton key={`chart-${i}`} className="h-52 rounded-xl" />
					))}
				</div>
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
		<div className="mx-auto w-full max-w-5xl px-6 py-8">
			<div className="mb-6">
				<Button variant="ghost" size="sm" className="mb-2 -ml-2" asChild>
					<Link to="/spaces">
						<ArrowLeft className="size-4" />
						Back to Spaces
					</Link>
				</Button>
				<h1 className="text-2xl font-bold tracking-tight">Analytics</h1>
				<p className="text-muted-foreground">
					Your study metrics and progress at a glance.
				</p>
			</div>

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
									<LineChart
										data={analytics.quiz_score_trend}
										accessibilityLayer
									>
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
		</div>
	);
}

// ── Helpers ────────────────────────────────────────────

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
