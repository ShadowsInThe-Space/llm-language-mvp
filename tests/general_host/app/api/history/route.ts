import { env } from "cloudflare:workers";
import { createDispatcher } from "../../../generated/history/server";

// Origin and the actual D1 binding come from trusted host configuration only.
export function POST(request: Request): Promise<Response> {
  return createDispatcher(env.DB, {allowedOrigin: env.HOST_ALLOWED_ORIGIN})(request);
}
