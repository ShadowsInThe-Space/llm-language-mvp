/** Preserve the built host while disabling source/module rebuilds in acceptance. */
export function immutableHostConfig(config) {
  const object = value => value !== null && typeof value === "object" && !Array.isArray(value);
  if (!object(config) || typeof config.main !== "string" || !config.main
    || config.no_bundle !== true || !object(config.assets)
    || typeof config.assets.directory !== "string" || !config.assets.directory
    || (config.build !== undefined && !object(config.build))) {
    throw new Error("Acceptance requires a built worker with its client asset directory");
  }
  const copy = structuredClone(config);
  // Wrangler 4.80.0's custom-build path bypasses runBuild's module watcher.
  // Its documented watch_dir array accepts []; the fixed command does no build
  // and changes no generated application files. Config/assets remain watched.
  copy.build = {...copy.build, command: 'node -e ""', watch_dir: []};
  return copy;
}
