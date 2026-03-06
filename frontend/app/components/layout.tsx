import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
	ArrowLeft,
	CalendarDays,
	FileText,
	GraduationCap,
	Layers,
	LogOut,
	MessageCircle,
	ScrollText,
} from "lucide-react";
import { NavLink, Outlet, useNavigate, useParams } from "react-router";
import { AuthProvider, useAuth } from "~/components/AuthProvider";
import { Avatar, AvatarFallback, AvatarImage } from "~/components/ui/avatar";
import { Button } from "~/components/ui/button";
import { Separator } from "~/components/ui/separator";
import {
	Sidebar,
	SidebarContent,
	SidebarFooter,
	SidebarGroup,
	SidebarGroupContent,
	SidebarGroupLabel,
	SidebarHeader,
	SidebarInset,
	SidebarMenu,
	SidebarMenuButton,
	SidebarMenuItem,
	SidebarProvider,
	SidebarTrigger,
} from "~/components/ui/sidebar";
import { getSpace, logout } from "~/lib/api";

export default function AppLayout() {
	return (
		<AuthProvider>
			<LayoutContent />
		</AuthProvider>
	);
}

function LayoutContent() {
	const { user } = useAuth();
	const navigate = useNavigate();
	const queryClient = useQueryClient();
	const { spaceId } = useParams<{ spaceId: string }>();

	const { data: space } = useQuery({
		queryKey: ["space", spaceId],
		queryFn: () => getSpace(spaceId!),
		enabled: !!spaceId,
	});

	const handleLogout = async () => {
		await logout();
		queryClient.clear();
		navigate("/login");
	};

	const NAV_ITEMS = [
		{
			to: `/spaces/${spaceId}/documents`,
			label: "Documents",
			icon: FileText,
		},
		{ to: `/spaces/${spaceId}/qa`, label: "Q&A", icon: MessageCircle },
		{
			to: `/spaces/${spaceId}/summaries`,
			label: "Summaries",
			icon: ScrollText,
		},
		{
			to: `/spaces/${spaceId}/quizzes`,
			label: "Quizzes",
			icon: GraduationCap,
		},
		{
			to: `/spaces/${spaceId}/flashcards`,
			label: "Flashcards",
			icon: Layers,
		},
		{
			to: `/spaces/${spaceId}/study-plans`,
			label: "Study Plan",
			icon: CalendarDays,
		},
	] as const;

	return (
		<SidebarProvider>
			<Sidebar collapsible="offcanvas">
				<SidebarHeader>
					<div className="flex items-center gap-2 px-2 py-1">
						<NavLink
							to="/spaces"
							className="flex items-center gap-1.5 text-muted-foreground hover:text-foreground transition-colors"
						>
							<ArrowLeft className="size-4" />
						</NavLink>
						<Separator orientation="vertical" className="h-4" />
						<div className="min-w-0 flex-1">
							<p className="text-sm font-semibold truncate">
								{space?.name ?? "Space"}
							</p>
						</div>
					</div>
				</SidebarHeader>

				<Separator />

				<SidebarContent>
					<SidebarGroup>
						<SidebarGroupLabel>Navigation</SidebarGroupLabel>
						<SidebarGroupContent>
							<SidebarMenu>
								{NAV_ITEMS.map(({ to, label, icon: Icon }) => (
									<SidebarMenuItem key={to}>
										<NavLink to={to}>
											{({ isActive }) => (
												<SidebarMenuButton
													isActive={isActive}
													tooltip={label}
													asChild
												>
													<span>
														<Icon className="size-4" />
														<span>{label}</span>
													</span>
												</SidebarMenuButton>
											)}
										</NavLink>
									</SidebarMenuItem>
								))}
							</SidebarMenu>
						</SidebarGroupContent>
					</SidebarGroup>
				</SidebarContent>

				<SidebarFooter>
					{user && (
						<div className="flex items-center gap-2 px-2 py-1">
							<Avatar className="size-6">
								<AvatarImage
									src={user.avatar_url ?? undefined}
									alt={user.username}
								/>
								<AvatarFallback className="text-xs">
									{user.username[0]?.toUpperCase()}
								</AvatarFallback>
							</Avatar>
							<span className="flex-1 truncate text-xs font-medium">
								{user.username}
							</span>
							<Button
								variant="ghost"
								size="icon"
								className="size-6"
								onClick={handleLogout}
							>
								<LogOut className="size-3" />
							</Button>
						</div>
					)}
				</SidebarFooter>
			</Sidebar>

			<SidebarInset>
				{/* Top bar with sidebar trigger for mobile */}
				<header className="flex h-12 items-center gap-2 border-b px-4 md:hidden">
					<SidebarTrigger />
					<Separator orientation="vertical" className="h-4" />
					<span className="text-sm font-medium truncate">
						{space?.name ?? "Space"}
					</span>
				</header>

				<div className="mx-auto w-full max-w-5xl px-6 py-8">
					<Outlet />
				</div>
			</SidebarInset>
		</SidebarProvider>
	);
}
