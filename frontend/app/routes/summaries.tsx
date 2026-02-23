import { useMutation, useQuery } from "@tanstack/react-query";
import { ChevronDown, Loader2 } from "lucide-react";
import { useState } from "react";
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
import { generateSummary, listDocuments } from "~/lib/api";
import type { DetailLevel, SummaryResponse } from "~/lib/types";

// ── Main Page ──────────────────────────────────────────

export default function SummariesPage() {
	const [result, setResult] = useState<SummaryResponse | null>(null);

	return (
		<div className="space-y-8">
			<div>
				<h1 className="text-2xl font-bold tracking-tight">Summaries</h1>
				<p className="text-muted-foreground">
					Generate topic-based or document-specific summaries.
				</p>
			</div>

			<SummaryForm onResult={setResult} />
			{result && <SummaryResult result={result} />}
		</div>
	);
}

// ── Summary Form ───────────────────────────────────────

function SummaryForm({ onResult }: { onResult: (r: SummaryResponse) => void }) {
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

	const genMut = useMutation({
		mutationFn: () =>
			generateSummary({
				topic: topic || undefined,
				document_id: docId || undefined,
				page_start: pageStart ? Number(pageStart) : undefined,
				page_end: pageEnd ? Number(pageEnd) : undefined,
				detail_level: detailLevel,
			}),
		onSuccess: (data) => onResult(data),
	});

	const handleSubmit = (e: React.SubmitEvent) => {
		e.preventDefault();
		if (!topic && !docId) return;
		genMut.mutate();
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

					<div className="grid grid-cols-3 gap-4">
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

					{genMut.isError && (
						<p className="text-sm text-destructive">
							Failed to generate summary: {genMut.error.message}
						</p>
					)}

					<Button
						type="submit"
						disabled={(!topic && !docId) || genMut.isPending}
					>
						{genMut.isPending && <Loader2 className="animate-spin" />}
						Generate summary
					</Button>
				</form>
			</CardContent>
		</Card>
	);
}

// ── Summary Result ─────────────────────────────────────

function SummaryResult({ result }: { result: SummaryResponse }) {
	return (
		<Card>
			<CardHeader>
				<div className="flex items-center justify-between">
					<CardTitle>Summary: {result.topic}</CardTitle>
					{result.model && <Badge variant="outline">{result.model}</Badge>}
				</div>
			</CardHeader>
			<CardContent className="space-y-4">
				<div className="prose prose-sm max-w-none dark:prose-invert">
					<Markdown>{result.summary}</Markdown>
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
