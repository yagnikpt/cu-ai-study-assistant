import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Layers, Loader2, Play, Plus, Trash2 } from "lucide-react";
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
import {
	deleteFlashcardDeck,
	generateFlashcardDeck,
	listDocuments,
	listFlashcardDecks,
} from "~/lib/api";

// ── Main Page ──────────────────────────────────────────

export default function FlashcardsPage() {
	const { spaceId } = useParams<{ spaceId: string }>();
	if (!spaceId) return null;

	return (
		<div className="space-y-8">
			<div>
				<h1 className="text-2xl font-bold tracking-tight">Flashcards</h1>
				<p className="text-muted-foreground">
					Generate and study flashcard decks from your documents.
				</p>
			</div>

			<GenerateSection spaceId={spaceId} />
			<DeckList spaceId={spaceId} />
		</div>
	);
}

// ── Generate Section ───────────────────────────────────

function GenerateSection({ spaceId }: { spaceId: string }) {
	const navigate = useNavigate();
	const queryClient = useQueryClient();
	const [docId, setDocId] = useState("");
	const [topic, setTopic] = useState("");
	const [count, setCount] = useState(10);

	const { data: docData } = useQuery({
		queryKey: ["documents", spaceId, { status: "ready", limit: 100 }],
		queryFn: () => listDocuments(spaceId, { status: "ready", limit: 100 }),
	});
	const docs = docData?.documents ?? [];

	const genMut = useMutation({
		mutationFn: () =>
			generateFlashcardDeck(spaceId, {
				document_id: docId || undefined,
				topic: topic || undefined,
				card_count: count,
			}),
		onSuccess: (deck) => {
			queryClient.invalidateQueries({ queryKey: ["flashcard-decks"] });
			navigate(`/spaces/${spaceId}/flashcards/${deck.id}/study`);
		},
	});

	const handleSubmit = (e: React.SubmitEvent) => {
		e.preventDefault();
		genMut.mutate();
	};

	return (
		<Collapsible>
			<Card>
				<CollapsibleTrigger className="w-full">
					<CardHeader>
						<div className="flex items-center justify-between">
							<div className="text-left">
								<CardTitle>Generate a New Deck</CardTitle>
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
								<Label htmlFor="fc-topic">Topic (optional)</Label>
								<Input
									id="fc-topic"
									placeholder="e.g. Photosynthesis, Chapter 3..."
									value={topic}
									onChange={(e) => setTopic(e.target.value)}
								/>
							</div>

							<div className="space-y-2">
								<Label htmlFor="fc-count">Number of cards: {count}</Label>
								<input
									id="fc-count"
									type="range"
									min={1}
									max={50}
									value={count}
									onChange={(e) => setCount(Number(e.target.value))}
									className="w-full accent-primary"
								/>
							</div>

							{genMut.isError && (
								<p className="text-sm text-destructive">
									Failed to generate deck: {genMut.error.message}
								</p>
							)}

							<Button type="submit" disabled={genMut.isPending}>
								{genMut.isPending && <Loader2 className="animate-spin" />}
								Generate flashcards
							</Button>
						</form>
					</CardContent>
				</CollapsibleContent>
			</Card>
		</Collapsible>
	);
}

// ── Deck List ──────────────────────────────────────────

function DeckList({ spaceId }: { spaceId: string }) {
	const navigate = useNavigate();
	const queryClient = useQueryClient();

	const { data, isLoading, isError, error } = useQuery({
		queryKey: ["flashcard-decks", spaceId],
		queryFn: () => listFlashcardDecks(spaceId),
	});

	const deleteMut = useMutation({
		mutationFn: (deckId: string) => deleteFlashcardDeck(spaceId, deckId),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["flashcard-decks"] });
		},
	});

	return (
		<Card>
			<CardHeader>
				<CardTitle>Your Decks</CardTitle>
				{data && (
					<CardDescription>
						{data.total} deck{data.total === 1 ? "" : "s"}
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
						Failed to load decks: {error.message}
					</p>
				) : !data || data.decks.length === 0 ? (
					<div className="flex flex-col items-center justify-center py-12 text-center">
						<Layers className="mb-3 size-10 text-muted-foreground" />
						<p className="font-medium">No flashcard decks yet</p>
						<p className="text-sm text-muted-foreground">
							Generate a deck above to get started.
						</p>
					</div>
				) : (
					<div className="divide-y">
						{data.decks.map((d) => (
							<div
								key={d.id}
								className="flex items-center justify-between py-3 first:pt-0 last:pb-0"
							>
								<div className="min-w-0 flex-1">
									<p className="truncate text-sm font-medium">{d.title}</p>
									<div className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
										<span>{d.card_count} cards</span>
										{d.topic && (
											<>
												<span aria-hidden="true">&middot;</span>
												<span>{d.topic}</span>
											</>
										)}
									</div>
								</div>

								<div className="ml-4 flex shrink-0 gap-2">
									<Button
										size="sm"
										onClick={() =>
											navigate(
												`/spaces/${spaceId}/flashcards/${d.id}/study`,
											)
										}
									>
										<Play />
										Study
									</Button>
									<Button
										variant="outline"
										size="sm"
										onClick={() => deleteMut.mutate(d.id)}
										disabled={deleteMut.isPending}
									>
										<Trash2 />
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
