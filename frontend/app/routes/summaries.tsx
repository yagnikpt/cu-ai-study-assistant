import { useQuery } from "@tanstack/react-query";
import { BookOpen, ChevronDown, ImageIcon, Loader2, Square } from "lucide-react";
import { useCallback, useMemo, useRef, useState } from "react";
import Markdown from "react-markdown";
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
import type {
	DetailLevel,
	ImageReference,
	SummarySource,
	SummaryStreamEvent,
} from "~/lib/types";
import { cn } from "~/lib/utils";

// ── Streaming result state ─────────────────────────────

interface StreamingResult {
	summary: string;
	topic: string;
	sources: SummarySource[];
	images: ImageReference[];
	model: string | null;
	isStreaming: boolean;
}

const EMPTY_RESULT: StreamingResult = {
	summary: "",
	topic: "",
	sources: [],
	images: [],
	model: null,
	isStreaming: false,
};

// ── Main Page ──────────────────────────────────────────

export default function SummariesPage() {
	const { spaceId } = useParams<{ spaceId: string }>();
	const [result, setResult] = useState<StreamingResult | null>(null);
	const [isStreaming, setIsStreaming] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const abortRef = useRef<AbortController | null>(null);

	if (!spaceId) return null;

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
				spaceId,
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
					case "images":
						setResult((prev) =>
							prev ? { ...prev, images: event.data } : null,
						);
						break;
					case "token":
						setResult((prev) =>
							prev ? { ...prev, summary: prev.summary + event.data } : null,
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
					setResult((prev) => (prev ? { ...prev, isStreaming: false } : null));
				})
				.finally(() => {
					setIsStreaming(false);
					abortRef.current = null;
				});
		},
		[spaceId],
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
				spaceId={spaceId}
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
	spaceId,
	onGenerate,
	isStreaming,
	onStop,
	error,
}: {
	spaceId: string;
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
		queryKey: ["documents", spaceId, { status: "ready", limit: 100 }],
		queryFn: () => listDocuments(spaceId!, { status: "ready", limit: 100 }),
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
						<Button type="submit" disabled={(!topic && !docId) || isStreaming}>
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

// ── Image placeholder utilities ───────────────────────

/**
 * Regex to match AI-generated image placeholders in markdown content.
 * Format: [Image: caption | id=<uuid>]
 */
const IMAGE_PLACEHOLDER_RE =
	/\[Image:\s*(.+?)\s*\|\s*id=([0-9a-f-]{36})\]/gi;

/**
 * Build a map of image_id -> image_url from the images array.
 */
function buildImageMap(
	images: ImageReference[] | undefined,
): Map<string, string> {
	const map = new Map<string, string>();
	if (!images) return map;
	for (const img of images) {
		map.set(img.image_id, img.image_url);
	}
	return map;
}

/**
 * Replace [Image: caption | id=<uuid>] placeholders with standard markdown
 * images: ![caption](url)
 *
 * If the image_id is not found in the map, the placeholder is left as-is.
 */
function resolveImagePlaceholders(
	content: string,
	imageMap: Map<string, string>,
): string {
	if (imageMap.size === 0) return content;
	return content.replace(IMAGE_PLACEHOLDER_RE, (_match, caption, id) => {
		const url = imageMap.get(id);
		if (!url) return _match;
		return `\n\n![${caption}](${url})\n\n`;
	});
}

// ── Source placeholder utilities ──────────────────────

/**
 * Regex to match AI-generated source placeholders in markdown content.
 * Format: [Source: display text | chunk_id=<uuid>]
 */
const SOURCE_PLACEHOLDER_RE =
	/\[Source:\s*(.+?)\s*\|\s*chunk_id=([0-9a-f-]{36})\]/gi;

/**
 * Build a set of known source chunk_ids for quick lookup.
 */
function buildSourceIdSet(
	sources: SummarySource[] | undefined,
): Set<string> {
	const set = new Set<string>();
	if (!sources) return set;
	for (const src of sources) {
		set.add(src.chunk_id);
	}
	return set;
}

/**
 * Replace [Source: display | chunk_id=<uuid>] placeholders with markdown
 * links that the custom `a` component will render as clickable badges.
 *
 * Output: [display](#source-<uuid>)
 */
function resolveSourcePlaceholders(
	content: string,
	sourceIds: Set<string>,
): string {
	if (sourceIds.size === 0) return content;
	return content.replace(SOURCE_PLACEHOLDER_RE, (_match, display, id) => {
		if (!sourceIds.has(id)) return _match;
		return `[${display}](#source-${id})`;
	});
}

// ── Summary Result ─────────────────────────────────────

function SummaryResult({ result }: { result: StreamingResult }) {
	const [highlightedSourceId, setHighlightedSourceId] = useState<
		string | null
	>(null);
	const [sourcesOpen, setSourcesOpen] = useState(false);

	// Build image lookup map and resolve placeholders in content
	const imageMap = useMemo(
		() => buildImageMap(result.images),
		[result.images],
	);
	const sourceIds = useMemo(
		() => buildSourceIdSet(result.sources),
		[result.sources],
	);
	const resolvedSummary = useMemo(() => {
		if (!result.summary) return "";
		let text = resolveImagePlaceholders(result.summary, imageMap);
		text = resolveSourcePlaceholders(text, sourceIds);
		return text;
	}, [result.summary, imageMap, sourceIds]);

	/** Handle click on a source citation badge: expand sources + scroll */
	const handleSourceBadgeClick = useCallback((chunkId: string) => {
		setSourcesOpen(true);
		setHighlightedSourceId(chunkId);
		// Wait a tick for the collapsible to expand, then scroll
		requestAnimationFrame(() => {
			const el = document.getElementById(`source-${chunkId}`);
			el?.scrollIntoView({ behavior: "smooth", block: "nearest" });
		});
		// Clear highlight after animation
		setTimeout(() => setHighlightedSourceId(null), 2000);
	}, []);

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
						{result.model && <Badge variant="outline">{result.model}</Badge>}
					</div>
				</div>
			</CardHeader>
			<CardContent className="space-y-4">
				<div className="prose prose-sm max-w-none dark:prose-invert">
					{resolvedSummary ? (
						<Markdown
							components={{
								img: ({ src, alt }) => (
									<figure className="my-3">
										<a
											href={src}
											target="_blank"
											rel="noopener noreferrer"
											className="block overflow-hidden rounded-lg border no-underline"
										>
											<img
												src={src}
												alt={alt || ""}
												className="!my-0 w-full max-h-80 object-contain bg-muted/40"
												loading="lazy"
											/>
										</a>
										{alt && (
											<figcaption className="mt-1.5 text-center text-xs text-muted-foreground">
												{alt}
											</figcaption>
										)}
									</figure>
								),
								a: ({ href, children }) => {
									if (href?.startsWith("#source-")) {
										const chunkId = href.replace("#source-", "");
										return (
											<button
												type="button"
												onClick={() => handleSourceBadgeClick(chunkId)}
												className="no-underline! inline-flex items-center rounded-full border border-primary/30 bg-primary/10 px-2 py-0.5 text-[11px] font-medium text-primary hover:bg-primary/20 transition-colors cursor-pointer align-baseline mx-0.5"
											>
												<BookOpen className="mr-1 size-3" />
												{children}
											</button>
										);
									}
									return (
										<a href={href} target="_blank" rel="noopener noreferrer">
											{children}
										</a>
									);
								},
							}}
						>
							{resolvedSummary}
						</Markdown>
					) : result.isStreaming ? (
						<div className="flex items-center gap-2">
							<Loader2 className="size-4 animate-spin text-muted-foreground" />
							<span className="text-sm text-muted-foreground">
								Generating summary...
							</span>
						</div>
					) : null}
				</div>

				{result.images.length > 0 && (
					<Collapsible>
						<Separator />
						<CollapsibleTrigger asChild>
							<Button
								variant="ghost"
								size="sm"
								className="mt-2 gap-1 text-primary"
							>
								<ImageIcon className="size-3" />
								<ChevronDown className="size-3 transition-transform in-data-[state=open]:rotate-180" />
								Relevant figures ({result.images.length})
							</Button>
						</CollapsibleTrigger>

						<CollapsibleContent>
							<div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
								{result.images.map((img) => (
									<a
										key={img.image_id}
										href={img.image_url}
										target="_blank"
										rel="noopener noreferrer"
										className="group overflow-hidden rounded-lg border"
									>
										<img
											src={img.image_url}
											alt={img.caption || `Figure from ${img.document_name}${img.page_number != null ? `, p.${img.page_number}` : ""}`}
											className="aspect-square w-full object-cover transition-transform group-hover:scale-105"
											loading="lazy"
										/>
										<div className="px-2 py-1">
											<p className="truncate text-[10px] text-muted-foreground">
												{img.caption || img.document_name}
												{img.page_number != null && ` p.${img.page_number}`}
											</p>
										</div>
									</a>
								))}
							</div>
						</CollapsibleContent>
					</Collapsible>
				)}

				{result.sources.length > 0 && (
					<Collapsible open={sourcesOpen} onOpenChange={setSourcesOpen}>
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
										id={`source-${src.chunk_id}`}
										className={cn(
											"flex items-baseline justify-between rounded-lg bg-muted px-3 py-2 transition-colors duration-500",
											highlightedSourceId === src.chunk_id &&
												"ring-2 ring-primary bg-primary/10",
										)}
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
