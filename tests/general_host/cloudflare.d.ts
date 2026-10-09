// The fixture requires exactly the capabilities passed by its trusted local host.
// Generated runtime row validation remains authoritative at the D1 boundary.
declare module "cloudflare:workers" {
  export const env: {
    DB: import("./generated/history/server").D1Database;
    HOST_ALLOWED_ORIGIN: string;
  };
}
