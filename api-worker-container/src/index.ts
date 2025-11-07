import { Container, getContainer } from "@cloudflare/containers";
import { Hono } from "hono";

export class MyContainer extends Container<Env> {
	// FastAPI listens on port 8000 inside the container
	defaultPort = 8000;
	sleepAfter = "2m";
}

// Create Hono app with proper typing for Cloudflare Workers
const app = new Hono<{
	Bindings: Env;
}>();

app.all("*", async (c) => {
	const container = getContainer(c.env.MY_CONTAINER, "fastapi");
	try {
		const requestClone = new Request(c.req.raw);
		return await container.fetch(requestClone);
	} catch (error) {
		console.error("Container fetch failed", error);
		return c.json({ detail: "Upstream container error" }, 500);
	}
});

export default app;
