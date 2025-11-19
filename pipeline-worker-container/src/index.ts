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
			// Fetch from the container's health endpoint to wake it up and verify it's running
			const healthResponse = await container.fetch(new Request("http://container/health"));
			
			if (healthResponse.ok) {
				return new Response("Pipeline worker container is running", {
					status: 200,
					headers: { "Content-Type": "text/plain" },
				});
			} else {
				return new Response("Container health check failed", { status: 503 });
			}
		} catch (error) {
			console.error("Container check failed", error);
			return new Response("Container error", { status: 500 });
		}
	},
	
	/**
	 * Scheduled event handler to periodically wake the container to run the pipeline.
	 */
	async scheduled(event: ScheduledEvent, env: Env, ctx: ExecutionContext): Promise<void> {
		const container = getContainer(env.PIPELINE_WORKER_CONTAINER, "pipeline-worker");
		
		try {
			await container.fetch(new Request("http://container/health"));
			console.log("Container scheduled trigger completed");
		} catch (error) {
			console.error("Scheduled trigger failed", error);
		}
	},
};

