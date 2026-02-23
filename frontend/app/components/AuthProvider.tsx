import { useQuery } from "@tanstack/react-query";
import { createContext, type ReactNode, useContext } from "react";
import { Navigate } from "react-router";
import { getMe } from "~/lib/api";
import type { User } from "~/lib/types";

interface AuthContextType {
	user: User | null;
	isLoading: boolean;
	isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType>({
	user: null,
	isLoading: true,
	isAuthenticated: false,
});

export function useAuth() {
	return useContext(AuthContext);
}

/**
 * Auth provider that wraps authenticated routes.
 * If not authenticated, redirects to /login.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
	const {
		data: user,
		isLoading,
		isError,
	} = useQuery({
		queryKey: ["auth", "me"],
		queryFn: getMe,
		retry: false,
		staleTime: 5 * 60 * 1000, // 5 min
	});

	// Still loading — don't flash anything
	if (isLoading) {
		return (
			<div className="flex min-h-screen items-center justify-center">
				<div className="animate-pulse text-muted-foreground">Loading...</div>
			</div>
		);
	}

	// Not authenticated — redirect to login
	if (isError || !user) {
		return <Navigate to="/login" replace />;
	}

	return (
		<AuthContext.Provider
			value={{
				user,
				isLoading: false,
				isAuthenticated: true,
			}}
		>
			{children}
		</AuthContext.Provider>
	);
}
