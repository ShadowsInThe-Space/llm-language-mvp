import { env } from "cloudflare:workers";
import { createDispatcher } from "../../../generated/tasks/server";

export function POST(request: Request): Promise<Response> {
  return createDispatcher(env.DB, {allowedOrigin: env.HOST_ALLOWED_ORIGIN})(request);
}
