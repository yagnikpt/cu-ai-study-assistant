import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
	ChevronDown,
	CircleAlert,
	CircleCheck,
	Eye,
	FileStack,
	Loader2,
	SlidersHorizontal,
	Tags,
	Trash2,
	Upload,
} from "lucide-react";
import { type DragEvent, useCallback, useRef, useState } from "react";
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
import { ScrollArea } from "~/components/ui/scroll-area";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "~/components/ui/select";
import { Separator } from "~/components/ui/separator";
import { Skeleton } from "~/components/ui/skeleton";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "~/components/ui/tooltip";
import {
	addTagsToDocument,
	createTag,
	deleteDocument,
	getChunks,
	listDocuments,
	listTags,
	uploadDocument,
} from "~/lib/api";
import type {
	Document,
	DocumentChunk,
	DocumentListParams,
	DocumentListResponse,
	DocumentStatus,
} from "~/lib/types";
import { cn } from "~/lib/utils";

// ── Main Page ──────────────────────────────────────────

export default function DocumentsPage() {
	return (
		<div className="space-y-8">
			<div>
				<h1 className="text-2xl font-bold tracking-tight">Documents</h1>
				<p className="text-muted-foreground">
					Upload, manage, and inspect your study documents.
				</p>
			</div>

			<UploadSection />
			<DocumentList />
			<TagSection />
		</div>
	);
}

// ── Loading skeleton for page-level spinners ───────────

function PageSkeleton() {
	return (
		<div className="space-y-3 py-6">
			<Skeleton className="h-4 w-3/4" />
			<Skeleton className="h-4 w-1/2" />
			<Skeleton className="h-4 w-2/3" />
		</div>
	);
}

// ── Upload Section ─────────────────────────────────────

function UploadSection() {
	const queryClient = useQueryClient();
	const fileInputRef = useRef<HTMLInputElement>(null);
	const [file, setFile] = useState<File | null>(null);
	const [courseName, setCourseName] = useState("");
	const [subject, setSubject] = useState("");
	const [dragOver, setDragOver] = useState(false);

	const uploadMut = useMutation({
		mutationFn: (f: File) =>
			uploadDocument(f, {
				course_name: courseName || undefined,
				subject: subject || undefined,
			}),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["documents"] });
			setFile(null);
			setCourseName("");
			setSubject("");
			if (fileInputRef.current) fileInputRef.current.value = "";
		},
	});

	const handleDragOver = useCallback((e: DragEvent) => {
		e.preventDefault();
		setDragOver(true);
	}, []);

	const handleDragLeave = useCallback((e: DragEvent) => {
		e.preventDefault();
		setDragOver(false);
	}, []);

	const handleDrop = useCallback((e: DragEvent) => {
		e.preventDefault();
		setDragOver(false);
		const dropped = e.dataTransfer.files[0];
		if (dropped?.type === "application/pdf") {
			setFile(dropped);
		}
	}, []);

	const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
		const selected = e.target.files?.[0] ?? null;
		setFile(selected);
	};

	const handleSubmit = (e: React.FormEvent) => {
		e.preventDefault();
		if (file) uploadMut.mutate(file);
	};

	return (
		<Card>
			<CardHeader>
				<CardTitle>Upload a PDF</CardTitle>
				<CardDescription>
					Add a new document to your study library.
				</CardDescription>
			</CardHeader>
			<CardContent>
				<form onSubmit={handleSubmit} className="space-y-4">
					{/* Drop zone */}
					<button
						type="button"
						onDragOver={handleDragOver}
						onDragLeave={handleDragLeave}
						onDrop={handleDrop}
						onClick={() => fileInputRef.current?.click()}
						className={cn(
							"flex w-full cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-8 transition-colors",
							dragOver
								? "border-primary bg-primary/5"
								: file
									? "border-green-500 bg-green-500/5"
									: "border-border bg-muted/50 hover:border-muted-foreground/50",
						)}
					>
						<Upload className="mb-2 size-8 text-muted-foreground" />
						{file ? (
							<p className="text-sm font-medium">
								{file.name}{" "}
								<span className="text-muted-foreground">
									({(file.size / 1024).toFixed(1)} KB)
								</span>
							</p>
						) : (
							<>
								<p className="text-sm font-medium">
									Drop a PDF here or click to browse
								</p>
								<p className="mt-1 text-xs text-muted-foreground">
									PDF files only
								</p>
							</>
						)}
					</button>
					<input
						ref={fileInputRef}
						type="file"
						accept=".pdf,application/pdf"
						onChange={handleFileChange}
						className="hidden"
					/>

					{/* Metadata fields */}
					<div className="grid md:grid-cols-2 gap-4">
						<div className="space-y-2">
							<Label htmlFor="course-name">Course name (optional)</Label>
							<Input
								id="course-name"
								placeholder="e.g. CS 101"
								value={courseName}
								onChange={(e) => setCourseName(e.target.value)}
							/>
						</div>
						<div className="space-y-2">
							<Label htmlFor="subject">Subject (optional)</Label>
							<Input
								id="subject"
								placeholder="e.g. Data Structures"
								value={subject}
								onChange={(e) => setSubject(e.target.value)}
							/>
						</div>
					</div>

					{/* Error display */}
					{uploadMut.isError && (
						<p className="text-sm text-destructive">
							Upload failed: {uploadMut.error.message}
						</p>
					)}

					{/* Success display */}
					{uploadMut.isSuccess && (
						<p className="text-sm text-green-600 dark:text-green-400">
							Uploaded{" "}
							<span className="font-medium">
								{uploadMut.data.original_filename}
							</span>{" "}
							successfully. Processing will begin shortly.
						</p>
					)}

					<Button type="submit" disabled={!file || uploadMut.isPending}>
						{uploadMut.isPending && <Loader2 className="animate-spin" />}
						Upload
					</Button>
				</form>
			</CardContent>
		</Card>
	);
}

// ── Document List ──────────────────────────────────────

function DocumentList() {
	const [filters, setFilters] = useState<DocumentListParams>({});
	const [showFilters, setShowFilters] = useState(false);

	const { data, isLoading, isError, error } = useQuery({
		queryKey: ["documents", filters],
		queryFn: () => listDocuments(filters),
		refetchInterval: (query) => {
			const docs = query.state.data?.documents;
			if (docs?.some((d) => d.status === "processing")) return 3000;
			return false;
		},
	});

	return (
		<Card>
			<CardHeader>
				<div className="flex items-center justify-between">
					<div>
						<CardTitle>Your Documents</CardTitle>
						{data && (
							<CardDescription>
								{data.documents.length} of {data.total} documents
							</CardDescription>
						)}
					</div>
					<Button
						variant="ghost"
						size="sm"
						onClick={() => setShowFilters((v) => !v)}
					>
						<SlidersHorizontal />
						Filters
					</Button>
				</div>
			</CardHeader>
			<CardContent>
				{/* Filter bar */}
				{showFilters && <FilterBar filters={filters} onChange={setFilters} />}

				{/* Content */}
				{isLoading ? (
					<PageSkeleton />
				) : isError ? (
					<p className="py-4 text-sm text-destructive">
						Failed to load documents: {error.message}
					</p>
				) : data && data.documents.length === 0 ? (
					<div className="flex flex-col items-center justify-center py-12 text-center">
						<FileStack className="mb-3 size-10 text-muted-foreground" />
						<p className="font-medium">No documents yet</p>
						<p className="text-sm text-muted-foreground">
							Upload a PDF above to get started.
						</p>
					</div>
				) : (
					<div className="space-y-3">
						{data?.documents.map((doc) => (
							<DocumentRow key={doc.id} doc={doc} />
						))}
					</div>
				)}
			</CardContent>
		</Card>
	);
}

// ── Filter Bar ─────────────────────────────────────────

function FilterBar({
	filters,
	onChange,
}: {
	filters: DocumentListParams;
	onChange: (f: DocumentListParams) => void;
}) {
	return (
		<div className="mb-4 grid grid-cols-3 gap-3 rounded-lg border bg-muted/50 p-3">
			<Input
				placeholder="Course name"
				value={filters.course_name ?? ""}
				onChange={(e) =>
					onChange({ ...filters, course_name: e.target.value || undefined })
				}
			/>
			<Input
				placeholder="Subject"
				value={filters.subject ?? ""}
				onChange={(e) =>
					onChange({ ...filters, subject: e.target.value || undefined })
				}
			/>
			<Select
				value={filters.status ?? "all"}
				onValueChange={(v) =>
					onChange({
						...filters,
						status: v === "all" ? undefined : (v as DocumentStatus),
					})
				}
			>
				<SelectTrigger className="w-full">
					<SelectValue placeholder="All statuses" />
				</SelectTrigger>
				<SelectContent>
					<SelectItem value="all">All statuses</SelectItem>
					<SelectItem value="processing">Processing</SelectItem>
					<SelectItem value="ready">Ready</SelectItem>
					<SelectItem value="error">Error</SelectItem>
				</SelectContent>
			</Select>
		</div>
	);
}

// ── Status Icon ────────────────────────────────────────

function StatusIcon({ status }: { status: DocumentStatus }) {
	return (
		<TooltipProvider>
			<Tooltip>
				<TooltipTrigger asChild>
					<span className="flex shrink-0 items-center">
						{status === "processing" && (
							<Loader2 className="size-4 animate-spin text-muted-foreground" />
						)}
						{status === "ready" && (
							<CircleCheck className="size-4 text-green-500" />
						)}
						{status === "error" && (
							<CircleAlert className="size-4 text-destructive" />
						)}
					</span>
				</TooltipTrigger>
				<TooltipContent side="right">
					{status === "processing" && "Processing"}
					{status === "ready" && "Ready"}
					{status === "error" && "Error"}
				</TooltipContent>
			</Tooltip>
		</TooltipProvider>
	);
}

// ── Document Row ───────────────────────────────────────

function DocumentRow({ doc }: { doc: Document }) {
	const queryClient = useQueryClient();
	const [showChunks, setShowChunks] = useState(false);
	const [showTagModal, setShowTagModal] = useState(false);

	const deleteMut = useMutation({
		mutationFn: () => deleteDocument(doc.id),
		onSuccess: () =>
			setTimeout(
				() => queryClient.invalidateQueries({ queryKey: ["documents"] }),
				500,
			),
	});

	const sizeKB = (doc.file_size_bytes / 1024).toFixed(1);

	return (
		<Collapsible>
			<div className="rounded-lg border">
				{/* Header row */}
				<CollapsibleTrigger className="flex w-full items-center justify-between px-4 py-3 text-left transition-colors hover:bg-muted/50">
					<div className="flex items-center gap-3 overflow-hidden">
						<StatusIcon status={doc.status} />
						<span className="truncate text-sm font-medium">
							{doc.original_filename}
						</span>
						{doc.tags.length > 0 && (
							<div className="hidden items-center gap-1 sm:flex">
								{doc.tags.slice(0, 3).map((t) => (
									<Badge
										key={t.id}
										variant="outline"
										className="text-xs"
										style={
											t.color
												? {
														borderColor: t.color,
														color: t.color,
													}
												: undefined
										}
									>
										{t.name}
									</Badge>
								))}
								{doc.tags.length > 3 && (
									<span className="text-xs text-muted-foreground">
										+{doc.tags.length - 3}
									</span>
								)}
							</div>
						)}
					</div>
					<ChevronDown className="size-5 shrink-0 text-muted-foreground transition-transform in-data-[state=open]:rotate-180" />
				</CollapsibleTrigger>

				{/* Expanded detail */}
				<CollapsibleContent>
					<Separator />
					<div className="px-4 py-4">
						{/* Metrics row */}
						<div className="grid grid-cols-3 gap-3">
							<div className="rounded-lg border bg-muted/50 p-3 text-center">
								<p className="md:text-2xl font-bold tabular-nums">
									{doc.page_count}
								</p>
								<p className="text-xs text-muted-foreground">Pages</p>
							</div>
							<div className="rounded-lg border bg-muted/50 p-3 text-center">
								<p className="md:text-2xl font-bold tabular-nums">
									{doc.chunk_count}
								</p>
								<p className="text-xs text-muted-foreground">Chunks</p>
							</div>
							<div className="rounded-lg border bg-muted/50 p-3 text-center">
								<p className="md:text-2xl font-bold tabular-nums">{sizeKB}</p>
								<p className="text-xs text-muted-foreground">KB</p>
							</div>
						</div>

						{/* Metadata */}
						<div className="mt-3 space-y-1 text-sm text-muted-foreground">
							{doc.course_name && <p>Course: {doc.course_name}</p>}
							{doc.subject && <p>Subject: {doc.subject}</p>}
							{doc.error_message && (
								<p className="text-destructive">Error: {doc.error_message}</p>
							)}
						</div>

						{/* Tags on mobile */}
						{doc.tags.length > 0 && (
							<div className="mt-3 flex flex-wrap gap-1 sm:hidden">
								{doc.tags.map((t) => (
									<Badge
										key={t.id}
										variant="outline"
										className="text-xs"
										style={
											t.color
												? { borderColor: t.color, color: t.color }
												: undefined
										}
									>
										{t.name}
									</Badge>
								))}
							</div>
						)}

						{/* Actions */}
						<div className="mt-4 flex flex-wrap items-center gap-2">
							<Button
								variant="outline"
								size="sm"
								onClick={() => setShowChunks(true)}
								disabled={doc.status !== "ready"}
							>
								<Eye />
								View chunks
							</Button>
							<Button
								variant="outline"
								size="sm"
								onClick={() => setShowTagModal(true)}
							>
								<Tags />
								Manage tags
							</Button>
							<Button
								variant="destructive"
								size="sm"
								onClick={() => {
									if (confirm("Delete this document?")) deleteMut.mutate();
								}}
								disabled={deleteMut.isPending}
							>
								{deleteMut.isPending ? (
									<Loader2 className="animate-spin" />
								) : (
									<Trash2 />
								)}
								Delete
							</Button>
						</div>

						{deleteMut.isError && (
							<p className="mt-2 text-sm text-destructive">
								Delete failed: {deleteMut.error.message}
							</p>
						)}
					</div>
				</CollapsibleContent>
			</div>

			{/* Chunks dialog */}
			{showChunks && (
				<ChunkViewer docId={doc.id} onClose={() => setShowChunks(false)} />
			)}

			{/* Tag management dialog */}
			{showTagModal && (
				<TagAssignDialog doc={doc} onClose={() => setShowTagModal(false)} />
			)}
		</Collapsible>
	);
}

// ── Chunk Viewer Dialog ────────────────────────────────

function ChunkViewer({
	docId,
	onClose,
}: {
	docId: string;
	onClose: () => void;
}) {
	const { data: chunks, isLoading } = useQuery({
		queryKey: ["chunks", docId],
		queryFn: () => getChunks(docId, 0, 100),
	});

	return (
		<Dialog open onOpenChange={(open) => !open && onClose()}>
			<DialogContent className="sm:max-w-2xl">
				<DialogHeader>
					<DialogTitle>Document Chunks</DialogTitle>
					<DialogDescription>
						Inspect the text chunks extracted from this document.
					</DialogDescription>
				</DialogHeader>

				{isLoading ? (
					<PageSkeleton />
				) : !chunks || chunks.length === 0 ? (
					<p className="py-4 text-sm text-muted-foreground">
						No chunks available (document may still be processing).
					</p>
				) : (
					<ScrollArea className="max-h-[60vh]">
						<div className="space-y-4 pr-4">
							{chunks.map((chunk) => (
								<ChunkCard key={chunk.id} chunk={chunk} />
							))}
						</div>
					</ScrollArea>
				)}
			</DialogContent>
		</Dialog>
	);
}

function ChunkCard({ chunk }: { chunk: DocumentChunk }) {
	const pages =
		chunk.page_start === chunk.page_end
			? `p.${chunk.page_start}`
			: `p.${chunk.page_start}-${chunk.page_end}`;

	return (
		<div className="rounded-lg border p-3">
			<div className="mb-2 flex items-center justify-between">
				<span className="text-xs font-semibold">
					Chunk {chunk.chunk_index}{" "}
					<span className="font-normal text-muted-foreground">({pages})</span>
				</span>
				{chunk.section_title && (
					<span className="text-xs text-muted-foreground">
						{chunk.section_title}
					</span>
				)}
			</div>
			<p className="whitespace-pre-wrap text-xs leading-relaxed text-muted-foreground">
				{chunk.content.length > 500
					? `${chunk.content.slice(0, 500)}...`
					: chunk.content}
			</p>
			<p className="mt-1 text-[11px] text-muted-foreground/70">
				{chunk.token_count} tokens
			</p>
		</div>
	);
}

// ── Tag Assign Dialog ──────────────────────────────────

function TagAssignDialog({
	doc,
	onClose,
}: {
	doc: Document;
	onClose: () => void;
}) {
	const queryClient = useQueryClient();
	const [selectedTagIds, setSelectedTagIds] = useState<string[]>(
		doc.tags.map((t) => t.id),
	);

	const { data: allTags, isLoading } = useQuery({
		queryKey: ["tags"],
		queryFn: listTags,
	});

	const assignMut = useMutation({
		mutationFn: () => addTagsToDocument(doc.id, { tag_ids: selectedTagIds }),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["documents"] });
			onClose();
		},
	});

	const toggleTag = (tagId: string) => {
		setSelectedTagIds((prev) =>
			prev.includes(tagId)
				? prev.filter((id) => id !== tagId)
				: [...prev, tagId],
		);
	};

	return (
		<Dialog open onOpenChange={(open) => !open && onClose()}>
			<DialogContent>
				<DialogHeader>
					<DialogTitle>Tags for {doc.original_filename}</DialogTitle>
					<DialogDescription>
						Select tags to associate with this document.
					</DialogDescription>
				</DialogHeader>

				{isLoading ? (
					<PageSkeleton />
				) : !allTags || allTags.length === 0 ? (
					<p className="py-4 text-sm text-muted-foreground">
						No tags available. Create some in the Tags section below.
					</p>
				) : (
					<div className="flex flex-wrap gap-2">
						{allTags.map((tag) => {
							const selected = selectedTagIds.includes(tag.id);
							return (
								<button
									key={tag.id}
									type="button"
									onClick={() => toggleTag(tag.id)}
									className={cn(
										"inline-flex items-center rounded-full border px-3 py-1 text-sm transition-colors",
										selected
											? "border-primary bg-primary/10 text-primary"
											: "border-border text-muted-foreground hover:border-muted-foreground",
									)}
								>
									{tag.color && (
										<span
											className="mr-1.5 inline-block size-2 rounded-full"
											style={{ backgroundColor: tag.color }}
										/>
									)}
									{tag.name}
								</button>
							);
						})}
					</div>
				)}

				{assignMut.isError && (
					<p className="text-sm text-destructive">
						Failed to update tags: {assignMut.error.message}
					</p>
				)}

				<DialogFooter>
					<Button variant="outline" onClick={onClose}>
						Cancel
					</Button>
					<Button
						onClick={() => assignMut.mutate()}
						disabled={assignMut.isPending}
					>
						{assignMut.isPending && <Loader2 className="animate-spin" />}
						Save tags
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}

// ── Tag Section ────────────────────────────────────────

function TagSection() {
	const queryClient = useQueryClient();
	const [newName, setNewName] = useState("");
	const [newColor, setNewColor] = useState("#4A90D9");

	const { data: tags, isLoading } = useQuery({
		queryKey: ["tags"],
		queryFn: listTags,
	});

	const createMut = useMutation({
		mutationFn: () => createTag({ name: newName, color: newColor }),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["tags"] });
			setNewName("");
		},
	});

	const handleCreate = (e: React.SubmitEvent) => {
		e.preventDefault();
		if (newName.trim()) createMut.mutate();
	};

	return (
		<Card>
			<CardHeader>
				<CardTitle>Tags</CardTitle>
				<CardDescription>Organize documents with tags.</CardDescription>
			</CardHeader>
			<CardContent>
				<div className="grid gap-6 lg:grid-cols-[1fr_auto]">
					{/* Tag list */}
					<div>
						{isLoading ? (
							<PageSkeleton />
						) : !tags || tags.length === 0 ? (
							<p className="text-sm text-muted-foreground">
								No tags yet. Create one to get started.
							</p>
						) : (
							<div className="flex flex-wrap gap-2">
								{tags.map((tag) => (
									<Badge
										key={tag.id}
										style={
											tag.color
												? { backgroundColor: tag.color, color: "#fff" }
												: undefined
										}
									>
										{tag.name}
									</Badge>
								))}
							</div>
						)}
					</div>

					{/* Create tag form */}
					<form
						onSubmit={handleCreate}
						className="flex items-end gap-2 border-t pt-4 lg:border-t-0 lg:border-l lg:pl-6 lg:pt-0"
					>
						<div className="space-y-2">
							<Label htmlFor="new-tag-name">New tag</Label>
							<Input
								id="new-tag-name"
								placeholder="Tag name"
								value={newName}
								onChange={(e) => setNewName(e.target.value)}
							/>
						</div>
						<div className="space-y-2">
							<Label htmlFor="tag-color">Color</Label>
							<input
								id="tag-color"
								type="color"
								value={newColor}
								onChange={(e) => setNewColor(e.target.value)}
								className="h-9 w-12 cursor-pointer rounded-md border border-input bg-background p-1"
							/>
						</div>
						<Button
							type="submit"
							disabled={!newName.trim() || createMut.isPending}
						>
							{createMut.isPending && <Loader2 className="animate-spin" />}
							Create
						</Button>
					</form>
				</div>

				{createMut.isError && (
					<p className="mt-2 text-sm text-destructive">
						Failed to create tag: {createMut.error.message}
					</p>
				)}
			</CardContent>
		</Card>
	);
}
