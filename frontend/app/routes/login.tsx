import { Github } from "lucide-react";
import { Button } from "~/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "~/components/ui/card";
import { getGitHubLoginUrl } from "~/lib/api";

export default function LoginPage() {
	return (
		<div className="flex min-h-screen flex-col items-center justify-center bg-linear-to-b from-background to-muted/30 px-4">
			<Card className="w-full max-w-sm">
				<CardHeader className="text-center">
					<CardTitle className="text-2xl">CU Study Assistant</CardTitle>
					<CardDescription>
						Sign in to manage your study spaces, upload documents, and take
						quizzes.
					</CardDescription>
				</CardHeader>
				<CardContent>
					<Button asChild className="w-full" size="lg">
						<a href={getGitHubLoginUrl()}>
							<Github className="mr-2 size-5" />
							Sign in with GitHub
						</a>
					</Button>
				</CardContent>
			</Card>

			<p className="mt-6 text-xs text-muted-foreground">
				Powered by Gemini AI &bull; Your data stays in your spaces
			</p>
		</div>
	);
}
