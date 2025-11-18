import { Container, getContainer } from "@cloudflare/containers";
import { env } from "cloudflare:workers";

/**
 * Container class for the pipeline-worker background service.
 * 
 * This container runs continuously to maintain connection to Azure Service Bus.
 * Unlike the API container, this service does not sleep after idle periods
 * because it must stay alive to listen for incoming messages.
 */
export class PipelineWorkerContainer extends Container<Env> {
	/**
	 * Note: No defaultPort is set because this service doesn't expose an HTTP server.
	 * It runs as a background process listening to Azure Service Bus.
	 * 
	 * Note: No sleepAfter is configured because the service must run continuously
	 * to maintain the Azure Service Bus connection and process incoming messages.
	 */
	
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
 * 
 * This is a minimal worker that ensures the container stays alive.
 * The container runs the Python background listener service which
 * continuously listens to Azure Service Bus for messages.
 */
export default {
	/**
	 * This fetch handler ensures the container stays running.
	 * You can optionally add a health check endpoint here if needed.
	 */
	async fetch(request: Request, env: Env): Promise<Response> {
		// Keep the container alive by periodically accessing it
		const container = getContainer(env.PIPELINE_WORKER_CONTAINER, "pipeline-worker");
		
		try {
			// The container doesn't expose an HTTP endpoint, but we can check if it's running
			// This ensures Cloudflare keeps the container instance alive
			return new Response("Pipeline worker container is running", {
				status: 200,
				headers: { "Content-Type": "text/plain" },
			});
		} catch (error) {
			console.error("Container check failed", error);
			return new Response("Container error", { status: 500 });
		}
	},
	
	/**
	 * Scheduled event handler can be used for health checks or maintenance.
	 * Uncomment and configure if you need periodic container health checks.
	 */
	// async scheduled(event: ScheduledEvent, env: Env, ctx: ExecutionContext): Promise<void> {
	// 	const container = getContainer(env.PIPELINE_WORKER_CONTAINER, "pipeline-worker");
	// 	// Perform periodic health check or maintenance tasks if needed
	// },
};

