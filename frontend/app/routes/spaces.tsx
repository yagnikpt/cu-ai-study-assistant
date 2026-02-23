import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
	ArrowRight,
	FolderOpen,
	GraduationCap,
	Loader2,
	LogOut,
	Plus,
	Trash2,
} from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router";
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
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "~/components/ui/dialog";
import { Input } from "~/components/ui/input";
import { Label } from "~/components/ui/label";
import { Separator } from "~/components/ui/separator";
import { Skeleton } from "~/components/ui/skeleton";
import { createSpace, deleteSpace, listSpaces, logout } from "~/lib/api";

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
							Select a space to start studying.
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

			{/* Content */}
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
					<button
						type="button"
						className="grid place-content-center border-2 border-dashed border-primary/15 rounded-xl"
						onClick={() => setShowCreate(true)}
					>
						<div className="flex items-center gap-2 text-neutral-600">
							<Plus />
							Create New Space
						</div>
					</button>
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

			{/* Create dialog */}
			{showCreate && (
				<CreateSpaceDialog
					onClose={() => setShowCreate(false)}
					onCreated={(id) => navigate(`/spaces/${id}/documents`)}
				/>
			)}
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
						<Label htmlFor="space-name">Name</Label>
						<Input
							id="space-name"
							placeholder="e.g. CS 101 — Data Structures"
							value={name}
							onChange={(e) => setName(e.target.value)}
							autoFocus
						/>
					</div>
					<div className="space-y-2">
						<Label htmlFor="space-desc">Description (optional)</Label>
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
