import { Navigate } from "react-router";

/** Redirect the bare "/" path to "/documents" */
export default function Index() {
	return <Navigate to="/documents" replace />;
}
