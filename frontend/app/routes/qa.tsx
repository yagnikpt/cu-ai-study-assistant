import { useMutation, useQuery } from "@tanstack/react-query";
import {
	BookOpen,
	ChevronDown,
	Loader2,
	Send,
	Settings2,
	Trash2,
} from "lucide-react";
import { useCallback, useRef, useState } from "react";
import { Badge } from "~/components/ui/badge";
import { Button } from "~/components/ui/button";
import {
	Collapsible,
	CollapsibleContent,
	CollapsibleTrigger,
} from "~/components/ui/collapsible";
import { Input } from "~/components/ui/input";
import { Label } from "~/components/ui/label";
import { Separator } from "~/components/ui/separator";
import { askQuestion, listDocuments } from "~/lib/api";
import type { AskResponse, SourceReference } from "~/lib/types";
import { cn } from "~/lib/utils";

// ── Types ──────────────────────────────────────────────

interface Message {
	id: string;
	role: "user" | "assistant";
	content: string;
	sources?: SourceReference[];
	model?: string;
}

let msgId = 0;
function nextId() {
	return `msg-${++msgId}`;
}

// ── Main Page ──────────────────────────────────────────

export default function QAPage() {
	const [messages, setMessages] = useState<Message[]>([]);
	const [input, setInput] = useState("");
	const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
	const [topK, setTopK] = useState(5);
	const scrollRef = useRef<HTMLDivElement>(null);

	// Load ready documents for scope selector
	const { data: docData } = useQuery({
		queryKey: ["documents", { status: "ready", limit: 100 }],
		queryFn: () => listDocuments({ status: "ready", limit: 100 }),
	});
	const docs = docData?.documents ?? [];

	const askMut = useMutation({
		mutationFn: (question: string) =>
			askQuestion({
				question,
				document_ids: selectedDocIds.length > 0 ? selectedDocIds : undefined,
				top_k: topK,
			}),
		onSuccess: (data: AskResponse) => {
			setMessages((prev) => [
				...prev,
				{
					id: nextId(),
					role: "assistant",
					content: data.answer,
					sources: data.sources,
					model: data.model,
				},
			]);
			scrollToBottom();
		},
		onError: (err: Error) => {
			setMessages((prev) => [
				...prev,
				{ id: nextId(), role: "assistant", content: `Error: ${err.message}` },
			]);
			scrollToBottom();
		},
	});

	const scrollToBottom = useCallback(() => {
		requestAnimationFrame(() => {
			scrollRef.current?.scrollTo({
				top: scrollRef.current.scrollHeight,
				behavior: "smooth",
			});
		});
	}, []);

	const handleSubmit = (e: React.SubmitEvent) => {
		e.preventDefault();
		const question = input.trim();
		if (!question || askMut.isPending) return;

		setMessages((prev) => [
			...prev,
			{ id: nextId(), role: "user", content: question },
		]);
		setInput("");
		scrollToBottom();
		askMut.mutate(question);
	};

	const handleClear = () => {
		setMessages([]);
		askMut.reset();
	};

	return (
		<div className="flex h-[calc(100vh-8rem)] flex-col">
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
			<div
				ref={scrollRef}
				className="flex-1 space-y-4 overflow-y-auto rounded-xl border bg-muted/30 p-4"
			>
				{messages.length === 0 && !askMut.isPending && (
					<div className="flex h-full flex-col items-center justify-center gap-2">
						<BookOpen className="size-8 text-muted-foreground" />
						<p className="text-sm text-muted-foreground">
							Ask a question to get started.
						</p>
					</div>
				)}

				{messages.map((msg) => (
					<ChatBubble key={msg.id} message={msg} />
				))}

				{askMut.isPending && (
					<div className="flex items-center gap-2 px-4 py-3">
						<Loader2 className="size-4 animate-spin text-muted-foreground" />
						<span className="text-sm text-muted-foreground">Thinking...</span>
					</div>
				)}
			</div>

			{/* Input */}
			<form onSubmit={handleSubmit} className="mt-3 flex gap-2">
				<Input
					value={input}
					onChange={(e) => setInput(e.target.value)}
					placeholder="Ask a question about your documents..."
					disabled={askMut.isPending}
					className="flex-1"
				/>
				<Button type="submit" disabled={!input.trim() || askMut.isPending}>
					{askMut.isPending ? <Loader2 className="animate-spin" /> : <Send />}
					Send
				</Button>
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

// ── Chat Bubble ────────────────────────────────────────

function ChatBubble({ message }: { message: Message }) {
	const [showSources, setShowSources] = useState(false);
	const isUser = message.role === "user";

	return (
		<div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
			<div
				className={cn(
					"max-w-[85%] rounded-xl px-4 py-3",
					isUser ? "bg-primary text-primary-foreground" : "border bg-card",
				)}
			>
				<p className="whitespace-pre-wrap text-sm">{message.content}</p>

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
									<SourceCard key={src.chunk_id} source={src} />
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

function SourceCard({ source }: { source: SourceReference }) {
	const pages =
		source.page_start === source.page_end
			? `p.${source.page_start}`
			: `p.${source.page_start}-${source.page_end}`;

	return (
		<div className="rounded-lg bg-muted p-2">
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
