import { Container, getContainer } from "@cloudflare/containers";
import { env } from "cloudflare:workers";

/**
 * Container class for the pipeline-worker background service.
 */
export class PipelineWorkerContainer extends Container<Env> {
	/**
	 * Health check endpoint runs on port 8080
	 */
	defaultPort = 8080;

	
	envVars = {
		CONTENT_SERVER_URL: (env as any).CONTENT_SERVER_URL,
		SERVICE_BUS_CONNECTION_STRING: (env as any).SERVICE_BUS_CONNECTION_STRING,		
		R2_STORAGE_ENDPOINT: (env as any).R2_STORAGE_ENDPOINT,
		R2_ACCESS_KEY_ID: (env as any).R2_ACCESS_KEY_ID,
		R2_SECRET_ACCESS_KEY: (env as any).R2_SECRET_ACCESS_KEY,
		BLOB_OUTPUT_PREFIX: (env as any).BLOB_OUTPUT_PREFIX,
	};
}

/**
 * Worker entry point for pipeline-worker container.
 */
export default {

	async fetch(request: Request, env: Env): Promise<Response> {
		const container = getContainer(env.PIPELINE_WORKER_CONTAINER, "pipeline-worker");
		
		try {
			const url = new URL(request.url);
			const path = url.pathname;
			
			// Forward webhook requests to the container
			if (path === "/webhook" && request.method === "POST") {
				const containerUrl = `http://container/webhook`;
				const forwardedRequest = new Request(containerUrl, {
					method: request.method,
					headers: request.headers,
					body: request.body,
				});
				
				return await container.fetch(forwardedRequest);
			}
			
			// Handle health check endpoint
			if (path === "/health" && request.method === "GET") {
				const healthResponse = await container.fetch(new Request("http://container/health"));
				
				if (healthResponse.ok) {
					return new Response("Pipeline worker container is running", {
						status: 200,
						headers: { "Content-Type": "text/plain" },
					});
				} else {
					return new Response("Container health check failed", { status: 503 });
				}
			}
			
			// Return 404 for unknown routes
			return new Response("Not found", { status: 404 });
		} catch (error) {
			console.error("Container request failed", error);
			return new Response("Container error", { status: 500 });
		}
	}
};

