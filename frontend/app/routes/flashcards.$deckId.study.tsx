import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowLeft, ChevronLeft, ChevronRight, RotateCcw } from "lucide-react";
import { useState } from "react";
import { useNavigate, useParams } from "react-router";
import { Badge } from "~/components/ui/badge";
import { Button } from "~/components/ui/button";
import {
	Card,
	CardContent,
	CardFooter,
	CardHeader,
	CardTitle,
} from "~/components/ui/card";
import { Skeleton } from "~/components/ui/skeleton";
import { getFlashcardDeck, submitReviews } from "~/lib/api";
import type { FlashcardCard, ReviewRating, ReviewSubmission } from "~/lib/types";
import { cn } from "~/lib/utils";

// ── Loading skeleton ───────────────────────────────────

function PageSkeleton() {
	return (
		<div className="space-y-6">
			<Skeleton className="h-8 w-1/2" />
			<Skeleton className="h-4 w-1/3" />
			<Skeleton className="h-64 w-full" />
		</div>
	);
}

// ── Rating button config ───────────────────────────────

const RATINGS: {
	value: ReviewRating;
	label: string;
	color: string;
}[] = [
	{ value: "again", label: "Again", color: "bg-red-500/10 text-red-600 hover:bg-red-500/20 border-red-200" },
	{ value: "hard", label: "Hard", color: "bg-orange-500/10 text-orange-600 hover:bg-orange-500/20 border-orange-200" },
	{ value: "good", label: "Good", color: "bg-blue-500/10 text-blue-600 hover:bg-blue-500/20 border-blue-200" },
	{ value: "easy", label: "Easy", color: "bg-green-500/10 text-green-600 hover:bg-green-500/20 border-green-200" },
];

// ── Main Page ──────────────────────────────────────────

export default function StudyFlashcardsPage() {
	const { spaceId, deckId } = useParams();
	const navigate = useNavigate();

	const [currentIndex, setCurrentIndex] = useState(0);
	const [flipped, setFlipped] = useState(false);
	const [reviews, setReviews] = useState<Record<string, ReviewRating>>({});

	const {
		data: deck,
		isLoading,
		isError,
		error,
	} = useQuery({
		queryKey: ["flashcard-deck", deckId],
		queryFn: () => getFlashcardDeck(spaceId!, deckId!),
		enabled: !!deckId && !!spaceId,
	});

	const reviewMut = useMutation({
		mutationFn: (submissions: ReviewSubmission[]) =>
			submitReviews(spaceId!, deckId!, { reviews: submissions }),
	});

	const cards = deck?.cards ?? [];
	const currentCard = cards[currentIndex];
	const reviewedCount = Object.keys(reviews).length;
	const totalCards = cards.length;

	const handleRate = (rating: ReviewRating) => {
		if (!currentCard) return;

		setReviews((prev) => ({ ...prev, [currentCard.id]: rating }));
		setFlipped(false);

		// Auto-advance to next unreviewed card, or stay on last
		if (currentIndex < totalCards - 1) {
			setCurrentIndex((prev) => prev + 1);
		}
	};

	const handleFinish = () => {
		const submissions: ReviewSubmission[] = Object.entries(reviews).map(
			([flashcard_id, rating]) => ({ flashcard_id, rating }),
		);
		reviewMut.mutate(submissions, {
			onSuccess: () => navigate(`/spaces/${spaceId}/flashcards`),
		});
	};

	const goTo = (idx: number) => {
		if (idx >= 0 && idx < totalCards) {
			setCurrentIndex(idx);
			setFlipped(false);
		}
	};

	if (isLoading) return <PageSkeleton />;

	if (isError) {
		return (
			<div className="py-8 text-center">
				<p className="text-sm text-destructive">
					Failed to load deck: {error.message}
				</p>
				<Button
					variant="outline"
					size="sm"
					className="mt-4"
					onClick={() => navigate(`/spaces/${spaceId}/flashcards`)}
				>
					<ArrowLeft />
					Back to flashcards
				</Button>
			</div>
		);
	}

	if (!deck || totalCards === 0) {
		return (
			<div className="py-8 text-center">
				<p className="text-sm text-muted-foreground">
					This deck has no cards.
				</p>
				<Button
					variant="outline"
					size="sm"
					className="mt-4"
					onClick={() => navigate(`/spaces/${spaceId}/flashcards`)}
				>
					<ArrowLeft />
					Back to flashcards
				</Button>
			</div>
		);
	}

	return (
		<div className="space-y-6">
			{/* Header */}
			<div className="flex items-start justify-between">
				<div>
					<h1 className="text-2xl font-bold tracking-tight">{deck.title}</h1>
					<div className="mt-1 flex items-center gap-2 text-sm text-muted-foreground">
						{deck.topic && <span>{deck.topic}</span>}
						<Badge variant="outline">
							{reviewedCount}/{totalCards} reviewed
						</Badge>
					</div>
				</div>
				<Button
					variant="ghost"
					size="sm"
					onClick={() => navigate(`/spaces/${spaceId}/flashcards`)}
				>
					<ArrowLeft />
					Back
				</Button>
			</div>

			{/* Progress bar */}
			<div className="h-2 w-full rounded-full bg-muted">
				<div
					className="h-full rounded-full bg-primary transition-all"
					style={{ width: `${(reviewedCount / totalCards) * 100}%` }}
				/>
			</div>

			{/* Card */}
			<FlashcardView
				card={currentCard}
				flipped={flipped}
				onFlip={() => setFlipped((prev) => !prev)}
				reviewed={reviews[currentCard.id]}
			/>

			{/* Rating buttons (shown when flipped) */}
			{flipped && !reviews[currentCard.id] && (
				<div className="flex justify-center gap-3">
					{RATINGS.map(({ value, label, color }) => (
						<Button
							key={value}
							variant="outline"
							className={cn("min-w-[80px]", color)}
							onClick={() => handleRate(value)}
						>
							{label}
						</Button>
					))}
				</div>
			)}

			{/* Already rated indicator */}
			{reviews[currentCard.id] && (
				<div className="flex justify-center">
					<Badge variant="secondary">
						Rated: {reviews[currentCard.id]}
					</Badge>
				</div>
			)}

			{/* Navigation */}
			<div className="flex items-center justify-between">
				<Button
					variant="outline"
					size="sm"
					disabled={currentIndex === 0}
					onClick={() => goTo(currentIndex - 1)}
				>
					<ChevronLeft />
					Previous
				</Button>

				<span className="text-sm text-muted-foreground">
					{currentIndex + 1} / {totalCards}
				</span>

				{currentIndex < totalCards - 1 ? (
					<Button
						variant="outline"
						size="sm"
						onClick={() => goTo(currentIndex + 1)}
					>
						Next
						<ChevronRight />
					</Button>
				) : (
					<Button
						size="sm"
						onClick={handleFinish}
						disabled={reviewMut.isPending || reviewedCount === 0}
					>
						{reviewMut.isPending ? (
							<RotateCcw className="animate-spin" />
						) : null}
						Finish ({reviewedCount}/{totalCards})
					</Button>
				)}
			</div>

			{reviewMut.isError && (
				<p className="text-center text-sm text-destructive">
					Failed to save reviews: {reviewMut.error.message}
				</p>
			)}

			{/* Card dots for quick navigation */}
			<div className="flex flex-wrap justify-center gap-1.5">
				{cards.map((c, idx) => (
					<button
						key={c.id}
						type="button"
						onClick={() => goTo(idx)}
						className={cn(
							"size-2.5 rounded-full transition-colors",
							idx === currentIndex
								? "bg-primary"
								: reviews[c.id]
									? "bg-green-400"
									: "bg-muted-foreground/30",
						)}
						aria-label={`Go to card ${idx + 1}`}
					/>
				))}
			</div>
		</div>
	);
}

// ── Flashcard View ─────────────────────────────────────

function FlashcardView({
	card,
	flipped,
	onFlip,
	reviewed,
}: {
	card: FlashcardCard;
	flipped: boolean;
	onFlip: () => void;
	reviewed?: ReviewRating;
}) {
	return (
		<Card
			className={cn(
				"cursor-pointer select-none transition-all hover:shadow-md",
				"min-h-[250px] flex flex-col",
			)}
			onClick={onFlip}
		>
			<CardHeader className="pb-2">
				<div className="flex items-center justify-between">
					<Badge variant="outline">
						{card.card_type === "term_definition"
							? "Term / Definition"
							: "Question / Answer"}
					</Badge>
					{card.source_pages && (
						<span className="text-xs text-muted-foreground">
							{card.source_pages}
						</span>
					)}
				</div>
			</CardHeader>

			<CardContent className="flex flex-1 items-center justify-center py-8">
				<div className="text-center">
					{!flipped ? (
						<>
							<p className="text-xs font-medium uppercase tracking-wider text-muted-foreground mb-3">
								{card.card_type === "term_definition" ? "Term" : "Question"}
							</p>
							<p className="text-lg font-semibold">{card.front}</p>
						</>
					) : (
						<>
							<p className="text-xs font-medium uppercase tracking-wider text-muted-foreground mb-3">
								{card.card_type === "term_definition"
									? "Definition"
									: "Answer"}
							</p>
							<p className="text-lg">{card.back}</p>
							{card.explanation && (
								<p className="mt-4 text-sm text-muted-foreground">
									{card.explanation}
								</p>
							)}
						</>
					)}
				</div>
			</CardContent>

			<CardFooter className="justify-center border-t py-2">
				<p className="text-xs text-muted-foreground">
					{flipped ? "Click to see front" : "Click to flip"}
				</p>
			</CardFooter>
		</Card>
	);
}
