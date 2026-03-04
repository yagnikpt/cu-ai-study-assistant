import { useQuery } from "@tanstack/react-query";
import {
	BookOpen,
	ChevronDown,
	ImageIcon,
	Loader2,
	Send,
	Settings2,
	Square,
	Trash2,
} from "lucide-react";
import { useCallback, useMemo, useRef, useState } from "react";
import Markdown from "react-markdown";
import { useParams } from "react-router";
import { Badge } from "~/components/ui/badge";
import { Button } from "~/components/ui/button";
import {
	Collapsible,
	CollapsibleContent,
	CollapsibleTrigger,
} from "~/components/ui/collapsible";
import { Input } from "~/components/ui/input";
import { Label } from "~/components/ui/label";
import { ScrollArea } from "~/components/ui/scroll-area";
import { Separator } from "~/components/ui/separator";
import { askQuestionStream, listDocuments } from "~/lib/api";
import type {
	ImageReference,
	QAStreamEvent,
	SourceReference,
} from "~/lib/types";
import { cn } from "~/lib/utils";

// ── Types ──────────────────────────────────────────────

interface Message {
	id: string;
	role: "user" | "assistant";
	content: string;
	sources?: SourceReference[];
	images?: ImageReference[];
	model?: string;
	isStreaming?: boolean;
}

let msgId = 0;
function nextId() {
	return `msg-${++msgId}`;
}

// ── Main Page ──────────────────────────────────────────

export default function QAPage() {
	const { spaceId } = useParams<{ spaceId: string }>();
	const [messages, setMessages] = useState<Message[]>([]);
	const [input, setInput] = useState("");
	const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
	const [topK, setTopK] = useState(5);
	const [isStreaming, setIsStreaming] = useState(false);
	const abortRef = useRef<AbortController | null>(null);
	const scrollRef = useRef<HTMLDivElement>(null);

	if (!spaceId) return null;

	// Load ready documents for scope selector
	const { data: docData } = useQuery({
		queryKey: ["documents", spaceId, { status: "ready", limit: 100 }],
		queryFn: () => listDocuments(spaceId, { status: "ready", limit: 100 }),
	});
	const docs = docData?.documents ?? [];

	const scrollToBottom = useCallback(() => {
		requestAnimationFrame(() => {
			scrollRef.current?.scrollTo({
				top: scrollRef.current.scrollHeight,
				behavior: "smooth",
			});
		});
	}, []);

	const handleStream = useCallback(
		async (question: string) => {
			const assistantId = nextId();
			setIsStreaming(true);

			// Add placeholder assistant message
			setMessages((prev) => [
				...prev,
				{ id: assistantId, role: "assistant", content: "", isStreaming: true },
			]);
			scrollToBottom();

			const abort = new AbortController();
			abortRef.current = abort;

			try {
				await askQuestionStream(
					spaceId,
					{
						question,
						document_ids:
							selectedDocIds.length > 0 ? selectedDocIds : undefined,
						top_k: topK,
					},
					(event: QAStreamEvent) => {
						switch (event.type) {
							case "sources":
								setMessages((prev) =>
									prev.map((m) =>
										m.id === assistantId ? { ...m, sources: event.data } : m,
									),
								);
								break;
							case "images":
								setMessages((prev) =>
									prev.map((m) =>
										m.id === assistantId ? { ...m, images: event.data } : m,
									),
								);
								break;
							case "token":
								setMessages((prev) =>
									prev.map((m) =>
										m.id === assistantId
											? { ...m, content: m.content + event.data }
											: m,
									),
								);
								scrollToBottom();
								break;
							case "done":
								setMessages((prev) =>
									prev.map((m) =>
										m.id === assistantId
											? {
													...m,
													model: event.data.model,
													isStreaming: false,
												}
											: m,
									),
								);
								break;
						}
					},
					abort.signal,
				);
			} catch (err) {
				if ((err as Error).name === "AbortError") {
					// Mark as no longer streaming but keep partial content
					setMessages((prev) =>
						prev.map((m) =>
							m.id === assistantId ? { ...m, isStreaming: false } : m,
						),
					);
				} else {
					setMessages((prev) =>
						prev.map((m) =>
							m.id === assistantId
								? {
										...m,
										content: `Error: ${(err as Error).message}`,
										isStreaming: false,
									}
								: m,
						),
					);
				}
			} finally {
				setIsStreaming(false);
				abortRef.current = null;
				scrollToBottom();
			}
		},
		[selectedDocIds, topK, scrollToBottom],
	);

	const handleSubmit = (e: React.SubmitEvent) => {
		e.preventDefault();
		const question = input.trim();
		if (!question || isStreaming) return;

		setMessages((prev) => [
			...prev,
			{ id: nextId(), role: "user", content: question },
		]);
		setInput("");
		scrollToBottom();
		handleStream(question);
	};

	const handleStop = () => {
		abortRef.current?.abort();
	};

	const handleClear = () => {
		abortRef.current?.abort();
		setMessages([]);
		setIsStreaming(false);
	};

	return (
		<div className="flex h-[calc(100dvh-6rem)] flex-col">
			{/* Header */}
			<div className="mb-4 flex items-start justify-between">
				<div>
					<h1 className="text-2xl font-bold tracking-tight">Q&A</h1>
					<p className="text-muted-foreground">
						Ask questions about your documents and get AI-powered answers.
					</p>
				</div>
				{messages.length > 0 && (
					<Button variant="ghost" size="sm" onClick={handleClear}>
						<Trash2 />
						Clear chat
					</Button>
				)}
			</div>

			{/* Settings bar */}
			<SettingsBar
				docs={docs}
				selectedDocIds={selectedDocIds}
				onChangeDocIds={setSelectedDocIds}
				topK={topK}
				onChangeTopK={setTopK}
			/>

			{/* Chat area */}
			<ScrollArea
				ref={scrollRef}
				className="flex-1 overflow-y-hidden rounded-xl border bg-muted/30 relative"
			>
				<div className="p-4 space-y-4">
					{messages.length === 0 && !isStreaming && (
						<div className="flex flex-col justify-center items-center gap-2 absolute top-1/2 left-1/2 -translate-1/2">
							<BookOpen className="size-8 text-muted-foreground" />
							<p className="text-sm text-muted-foreground text-center">
								Ask a question to get started.
							</p>
						</div>
					)}

					{messages.map((msg) => (
						<ChatBubble key={msg.id} message={msg} />
					))}
				</div>
			</ScrollArea>

			{/* Input */}
			<form onSubmit={handleSubmit} className="mt-3 flex gap-2">
				<Input
					value={input}
					onChange={(e) => setInput(e.target.value)}
					placeholder="Ask a question about your documents..."
					disabled={isStreaming}
					className="flex-1 h-11 text-base!"
				/>
				{isStreaming ? (
					<Button
						className="h-full"
						type="button"
						variant="destructive"
						onClick={handleStop}
					>
						<Square />
						Stop
					</Button>
				) : (
					<Button className="h-full" type="submit" disabled={!input.trim()}>
						<Send />
						Send
					</Button>
				)}
			</form>
		</div>
	);
}

// ── Settings Bar ───────────────────────────────────────

function SettingsBar({
	docs,
	selectedDocIds,
	onChangeDocIds,
	topK,
	onChangeTopK,
}: {
	docs: { id: string; original_filename: string }[];
	selectedDocIds: string[];
	onChangeDocIds: (ids: string[]) => void;
	topK: number;
	onChangeTopK: (k: number) => void;
}) {
	return (
		<Collapsible>
			<div className="mb-3">
				<CollapsibleTrigger asChild>
					<Button variant="ghost" size="sm" className="gap-1.5">
						<Settings2 className="size-3.5" />
						Settings
						{selectedDocIds.length > 0 && (
							<Badge variant="secondary" className="ml-1">
								{selectedDocIds.length} doc
								{selectedDocIds.length > 1 ? "s" : ""}
							</Badge>
						)}
					</Button>
				</CollapsibleTrigger>

				<CollapsibleContent>
					<div className="mt-2 rounded-lg border bg-card p-3">
						<div className="grid gap-4 sm:grid-cols-[1fr_auto]">
							{/* Document scope */}
							<div>
								<Label className="mb-1.5 text-xs">
									Limit to documents
									<span className="ml-1 font-normal text-muted-foreground">
										(leave empty for all)
									</span>
								</Label>
								{docs.length === 0 ? (
									<p className="text-xs text-muted-foreground">
										No ready documents.
									</p>
								) : (
									<div className="flex max-h-32 flex-wrap gap-1.5 overflow-y-auto">
										{docs.map((d) => {
											const selected = selectedDocIds.includes(d.id);
											return (
												<button
													key={d.id}
													type="button"
													onClick={() =>
														onChangeDocIds(
															selected
																? selectedDocIds.filter((id) => id !== d.id)
																: [...selectedDocIds, d.id],
														)
													}
													className={cn(
														"rounded-full border px-2.5 py-1 text-xs transition-colors",
														selected
															? "border-primary bg-primary/10 text-primary"
															: "border-border text-muted-foreground hover:border-muted-foreground",
													)}
												>
													{d.original_filename}
												</button>
											);
										})}
									</div>
								)}
							</div>

							{/* Top-K slider */}
							<div className="min-w-35">
								<Label htmlFor="top-k-slider" className="mb-1.5 text-xs">
									Sources to retrieve: {topK}
								</Label>
								<input
									id="top-k-slider"
									type="range"
									min={1}
									max={20}
									value={topK}
									onChange={(e) => onChangeTopK(Number(e.target.value))}
									className="w-full accent-primary"
								/>
							</div>
						</div>
					</div>
				</CollapsibleContent>
			</div>
		</Collapsible>
	);
}

// ── Image placeholder utilities ───────────────────────

/**
 * Regex to match AI-generated image placeholders in markdown content.
 * Format: [Image: caption | id=<uuid>]
 */
const IMAGE_PLACEHOLDER_RE = /\[Image:\s*(.+?)\s*\|\s*id=([0-9a-f-]{36})\]/gi;

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
 * If the image_id is not found in the map, the placeholder is left as-is
 * (rendered as plain text).
 */
function resolveImagePlaceholders(
	content: string,
	imageMap: Map<string, string>,
): string {
	if (imageMap.size === 0) return content;
	return content.replace(IMAGE_PLACEHOLDER_RE, (_match, caption, id) => {
		const url = imageMap.get(id);
		if (!url) return _match; // leave unknown references as plain text
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
	sources: SourceReference[] | undefined,
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
 *
 * If the chunk_id is not in the known sources set, the placeholder is left
 * as-is (rendered as plain text).
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

// ── Chat Bubble ────────────────────────────────────────

function ChatBubble({ message }: { message: Message }) {
	const [showSources, setShowSources] = useState(false);
	const [showImages, setShowImages] = useState(false);
	const [highlightedSourceId, setHighlightedSourceId] = useState<
		string | null
	>(null);
	const isUser = message.role === "user";

	// Build image lookup map and resolve placeholders in content
	const imageMap = useMemo(
		() => buildImageMap(message.images),
		[message.images],
	);
	const sourceIds = useMemo(
		() => buildSourceIdSet(message.sources),
		[message.sources],
	);
	const resolvedContent = useMemo(() => {
		if (!message.content) return "";
		let text = resolveImagePlaceholders(message.content, imageMap);
		text = resolveSourcePlaceholders(text, sourceIds);
		return text;
	}, [message.content, imageMap, sourceIds]);

	/** Handle click on a source citation badge: expand sources + scroll */
	const handleSourceBadgeClick = useCallback(
		(chunkId: string) => {
			setShowSources(true);
			setHighlightedSourceId(chunkId);
			// Wait a tick for the collapsible to expand, then scroll
			requestAnimationFrame(() => {
				const el = document.getElementById(`source-${chunkId}`);
				el?.scrollIntoView({ behavior: "smooth", block: "nearest" });
			});
			// Clear highlight after animation
			setTimeout(() => setHighlightedSourceId(null), 2000);
		},
		[],
	);

	return (
		<div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
			<div
				className={cn(
					"max-w-[85%] rounded-xl px-4 py-3",
					isUser ? "bg-primary text-primary-foreground" : "border bg-card",
				)}
			>
				{isUser ? (
					<p className="whitespace-pre-wrap text-sm">{message.content}</p>
				) : (
					<div className="prose prose-sm max-w-none dark:prose-invert">
						{resolvedContent ? (
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
													className="my-0! w-full max-h-80 object-contain bg-muted/40"
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
								{resolvedContent}
							</Markdown>
						) : message.isStreaming ? (
							<div className="flex items-center gap-2">
								<Loader2 className="size-4 animate-spin text-muted-foreground" />
								<span className="text-sm text-muted-foreground">
									Thinking...
								</span>
							</div>
						) : null}
					</div>
				)}

				{!isUser && message.sources && message.sources.length > 0 && (
					<>
						<Separator className="my-2" />
						<button
							type="button"
							onClick={() => setShowSources((v) => !v)}
							className="flex items-center gap-1 text-xs font-medium text-primary hover:underline"
						>
							<ChevronDown
								className={cn(
									"size-3 transition-transform",
									showSources && "rotate-180",
								)}
							/>
							{showSources ? "Hide" : "Show"} sources ({message.sources.length})
						</button>

						{showSources && (
							<div className="mt-2 space-y-2">
							{message.sources.map((src) => (
									<SourceCard
										key={src.chunk_id}
										source={src}
										highlighted={highlightedSourceId === src.chunk_id}
									/>
								))}
							</div>
						)}
					</>
				)}

				{!isUser && message.images && message.images.length > 0 && (
					<>
						<Separator className="my-2" />
						<button
							type="button"
							onClick={() => setShowImages((v) => !v)}
							className="flex items-center gap-1 text-xs font-medium text-primary hover:underline"
						>
							<ImageIcon className="size-3" />
							<ChevronDown
								className={cn(
									"size-3 transition-transform",
									showImages && "rotate-180",
								)}
							/>
							{showImages ? "Hide" : "Show"} relevant figures (
							{message.images.length})
						</button>

						{showImages && (
							<div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
								{message.images.map((img) => (
									<a
										key={img.image_url}
										href={img.image_url}
										target="_blank"
										rel="noopener noreferrer"
										className="group overflow-hidden rounded-lg border"
									>
										<img
											src={img.image_url}
											alt={`Figure from ${img.document_name}${img.page_number != null ? `, p.${img.page_number}` : ""}`}
											className="aspect-square w-full object-cover transition-transform group-hover:scale-105"
											loading="lazy"
										/>
										<div className="px-2 py-1">
											<p className="truncate text-[10px] text-muted-foreground">
												{img.document_name}
												{img.page_number != null && ` p.${img.page_number}`}
											</p>
										</div>
									</a>
								))}
							</div>
						)}
					</>
				)}

				{!isUser && message.model && (
					<p className="mt-1 text-[11px] text-muted-foreground">
						{message.model}
					</p>
				)}
			</div>
		</div>
	);
}

// ── Source Card ─────────────────────────────────────────

function SourceCard({
	source,
	highlighted,
}: { source: SourceReference; highlighted?: boolean }) {
	const pages =
		source.page_start === source.page_end
			? `p.${source.page_start}`
			: `p.${source.page_start}-${source.page_end}`;

	return (
		<div
			id={`source-${source.chunk_id}`}
			className={cn(
				"rounded-lg bg-muted p-2 transition-colors duration-500",
				highlighted && "ring-2 ring-primary bg-primary/10",
			)}
		>
			<div className="flex items-baseline justify-between gap-2">
				<span className="text-xs font-medium">
					{source.document_name}
					<span className="ml-1 font-normal text-muted-foreground">
						({pages})
					</span>
				</span>
				<span className="shrink-0 text-[10px] text-muted-foreground">
					{(source.relevance_score * 100).toFixed(0)}% match
				</span>
			</div>
			{source.section_title && (
				<p className="text-[11px] text-muted-foreground">
					{source.section_title}
				</p>
			)}
			{source.text_preview && (
				<p className="mt-1 line-clamp-3 text-[11px] leading-relaxed text-muted-foreground">
					{source.text_preview}
				</p>
			)}
		</div>
	);
}
