import {
	FileText,
	GraduationCap,
	MessageCircle,
	ScrollText,
} from "lucide-react";
import { NavLink, Outlet } from "react-router";
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

const NAV_ITEMS = [
	{ to: "/documents", label: "Documents", icon: FileText },
	{ to: "/qa", label: "Q&A", icon: MessageCircle },
	{ to: "/summaries", label: "Summaries", icon: ScrollText },
	{ to: "/quizzes", label: "Quizzes", icon: GraduationCap },
] as const;

export default function AppLayout() {
	return (
		<SidebarProvider>
			<Sidebar collapsible="offcanvas">
				<SidebarHeader>
					<div className="flex items-center gap-2 px-2 py-1">
						<GraduationCap className="size-5 text-primary" />
						<span className="text-lg font-semibold">CU Study</span>
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
					<p className="px-2 text-xs text-muted-foreground">
						CU Study Assistant
					</p>
				</SidebarFooter>
			</Sidebar>

			<SidebarInset>
				{/* Top bar with sidebar trigger for mobile */}
				<header className="flex h-12 items-center gap-2 border-b px-4 md:hidden">
					<SidebarTrigger />
					<Separator orientation="vertical" className="h-4" />
					<span className="text-sm font-medium">CU Study</span>
				</header>

				<div className="mx-auto w-full max-w-5xl px-6 py-8">
					<Outlet />
				</div>
			</SidebarInset>
		</SidebarProvider>
	);
}
