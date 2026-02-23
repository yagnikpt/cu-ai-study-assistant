import { useQuery } from "@tanstack/react-query";
import { ChevronDown, Loader2, Square } from "lucide-react";
import { useCallback, useRef, useState } from "react";
import Markdown from "react-markdown";
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
import { Separator } from "~/components/ui/separator";
import { generateSummaryStream, listDocuments } from "~/lib/api";
import type { DetailLevel, SummarySource, SummaryStreamEvent } from "~/lib/types";

// ── Streaming result state ─────────────────────────────

interface StreamingResult {
	summary: string;
	topic: string;
	sources: SummarySource[];
	model: string | null;
	isStreaming: boolean;
}

const EMPTY_RESULT: StreamingResult = {
	summary: "",
	topic: "",
	sources: [],
	model: null,
	isStreaming: false,
};

// ── Main Page ──────────────────────────────────────────

export default function SummariesPage() {
	const [result, setResult] = useState<StreamingResult | null>(null);
	const [isStreaming, setIsStreaming] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const abortRef = useRef<AbortController | null>(null);

	const handleStream = useCallback(
		(params: {
			topic?: string;
			document_id?: string;
			page_start?: number;
			page_end?: number;
			detail_level: DetailLevel;
		}) => {
			setError(null);
			setIsStreaming(true);
			setResult({ ...EMPTY_RESULT, isStreaming: true });

			const abort = new AbortController();
			abortRef.current = abort;

			generateSummaryStream(
				{
					topic: params.topic || undefined,
					document_id: params.document_id || undefined,
					page_start: params.page_start,
					page_end: params.page_end,
					detail_level: params.detail_level,
				},
				(event: SummaryStreamEvent) => {
					switch (event.type) {
						case "meta":
							setResult((prev) =>
								prev
									? {
											...prev,
											topic: event.data.topic,
											sources: event.data.sources,
										}
									: null,
							);
							break;
						case "token":
							setResult((prev) =>
								prev
									? { ...prev, summary: prev.summary + event.data }
									: null,
							);
							break;
						case "done":
							setResult((prev) =>
								prev
									? {
											...prev,
											model: event.data.model,
											isStreaming: false,
										}
									: null,
							);
							break;
					}
				},
				abort.signal,
			)
				.catch((err) => {
					if ((err as Error).name !== "AbortError") {
						setError((err as Error).message);
					}
					setResult((prev) =>
						prev ? { ...prev, isStreaming: false } : null,
					);
				})
				.finally(() => {
					setIsStreaming(false);
					abortRef.current = null;
				});
		},
		[],
	);

	const handleStop = () => {
		abortRef.current?.abort();
	};

	return (
		<div className="space-y-8">
			<div>
				<h1 className="text-2xl font-bold tracking-tight">Summaries</h1>
				<p className="text-muted-foreground">
					Generate topic-based or document-specific summaries.
				</p>
			</div>

			<SummaryForm
				onGenerate={handleStream}
				isStreaming={isStreaming}
				onStop={handleStop}
				error={error}
			/>
			{result && <SummaryResult result={result} />}
		</div>
	);
}

// ── Summary Form ───────────────────────────────────────

function SummaryForm({
	onGenerate,
	isStreaming,
	onStop,
	error,
}: {
	onGenerate: (params: {
		topic?: string;
		document_id?: string;
		page_start?: number;
		page_end?: number;
		detail_level: DetailLevel;
	}) => void;
	isStreaming: boolean;
	onStop: () => void;
	error: string | null;
}) {
	const [topic, setTopic] = useState("");
	const [docId, setDocId] = useState("");
	const [detailLevel, setDetailLevel] = useState<DetailLevel>("standard");
	const [pageStart, setPageStart] = useState("");
	const [pageEnd, setPageEnd] = useState("");

	const { data: docData } = useQuery({
		queryKey: ["documents", { status: "ready", limit: 100 }],
		queryFn: () => listDocuments({ status: "ready", limit: 100 }),
	});
	const docs = docData?.documents ?? [];

	const handleSubmit = (e: React.SubmitEvent) => {
		e.preventDefault();
		if (!topic && !docId) return;
		onGenerate({
			topic: topic || undefined,
			document_id: docId || undefined,
			page_start: pageStart ? Number(pageStart) : undefined,
			page_end: pageEnd ? Number(pageEnd) : undefined,
			detail_level: detailLevel,
		});
	};

	return (
		<Card>
			<CardHeader>
				<CardTitle>Generate a Summary</CardTitle>
				<CardDescription>Provide a topic, a document, or both.</CardDescription>
			</CardHeader>
			<CardContent>
				<form onSubmit={handleSubmit} className="space-y-4">
					<div className="space-y-2">
						<Label htmlFor="summary-topic">Topic</Label>
						<Input
							id="summary-topic"
							placeholder="e.g. Photosynthesis, Chapter 3, Sorting algorithms..."
							value={topic}
							onChange={(e) => setTopic(e.target.value)}
						/>
					</div>

					<div className="space-y-2">
						<Label>Document (optional)</Label>
						<Select
							value={docId || "none"}
							onValueChange={(v) => setDocId(v === "none" ? "" : v)}
						>
							<SelectTrigger className="w-full">
								<SelectValue placeholder="Select a document" />
							</SelectTrigger>
							<SelectContent>
								<SelectItem value="none">
									(none -- topic-only search)
								</SelectItem>
								{docs.map((d) => (
									<SelectItem key={d.id} value={d.id}>
										{d.original_filename}
									</SelectItem>
								))}
							</SelectContent>
						</Select>
					</div>

					<div className="grid md:grid-cols-3 gap-4">
						<div className="space-y-2">
							<Label>Detail level</Label>
							<Select
								value={detailLevel}
								onValueChange={(v) => setDetailLevel(v as DetailLevel)}
							>
								<SelectTrigger className="w-full">
									<SelectValue />
								</SelectTrigger>
								<SelectContent>
									<SelectItem value="brief">Brief</SelectItem>
									<SelectItem value="standard">Standard</SelectItem>
									<SelectItem value="detailed">Detailed</SelectItem>
								</SelectContent>
							</Select>
						</div>
						<div className="space-y-2">
							<Label htmlFor="page-start">Start page (optional)</Label>
							<Input
								id="page-start"
								type="number"
								min={1}
								placeholder="1"
								value={pageStart}
								onChange={(e) => setPageStart(e.target.value)}
							/>
						</div>
						<div className="space-y-2">
							<Label htmlFor="page-end">End page (optional)</Label>
							<Input
								id="page-end"
								type="number"
								min={1}
								placeholder="10"
								value={pageEnd}
								onChange={(e) => setPageEnd(e.target.value)}
							/>
						</div>
					</div>

					{error && (
						<p className="text-sm text-destructive">
							Failed to generate summary: {error}
						</p>
					)}

					<div className="flex gap-2">
						<Button
							type="submit"
							disabled={(!topic && !docId) || isStreaming}
						>
							{isStreaming && <Loader2 className="animate-spin" />}
							Generate summary
						</Button>
						{isStreaming && (
							<Button type="button" variant="destructive" onClick={onStop}>
								<Square />
								Stop
							</Button>
						)}
					</div>
				</form>
			</CardContent>
		</Card>
	);
}

// ── Summary Result ─────────────────────────────────────

function SummaryResult({ result }: { result: StreamingResult }) {
	return (
		<Card>
			<CardHeader>
				<div className="flex items-center justify-between">
					<CardTitle>
						{result.topic
							? `Summary: ${result.topic}`
							: result.isStreaming
								? "Generating..."
								: "Summary"}
					</CardTitle>
					<div className="flex items-center gap-2">
						{result.isStreaming && (
							<Loader2 className="size-4 animate-spin text-muted-foreground" />
						)}
						{result.model && (
							<Badge variant="outline">{result.model}</Badge>
						)}
					</div>
				</div>
			</CardHeader>
			<CardContent className="space-y-4">
				<div className="prose prose-sm max-w-none dark:prose-invert">
					{result.summary ? (
						<Markdown>{result.summary}</Markdown>
					) : result.isStreaming ? (
						<div className="flex items-center gap-2">
							<Loader2 className="size-4 animate-spin text-muted-foreground" />
							<span className="text-sm text-muted-foreground">
								Generating summary...
							</span>
						</div>
					) : null}
				</div>

				{result.sources.length > 0 && (
					<Collapsible>
						<Separator />
						<CollapsibleTrigger asChild>
							<Button
								variant="ghost"
								size="sm"
								className="mt-2 gap-1 text-primary"
							>
								<ChevronDown className="size-3 transition-transform in-data-[state=open]:rotate-180" />
								Sources ({result.sources.length})
							</Button>
						</CollapsibleTrigger>

						<CollapsibleContent>
							<div className="mt-2 space-y-2">
								{result.sources.map((src) => (
									<div
										key={src.chunk_id}
										className="flex items-baseline justify-between rounded-lg bg-muted px-3 py-2"
									>
										<span className="text-sm font-medium">
											{src.document_name}
										</span>
										<span className="text-xs text-muted-foreground">
											pages {src.pages}
										</span>
									</div>
								))}
							</div>
						</CollapsibleContent>
					</Collapsible>
				)}
			</CardContent>
		</Card>
	);
}
