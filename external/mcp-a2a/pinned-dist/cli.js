#!/usr/bin/env node
import { P as BUILD_INFO, i as setupInstructions, t as loadConfig } from "./config-B77d6yRo.js";
import { i as createServer } from "./server-Dd272e4l.js";
import { ZodError } from "zod";
import { StdioServerTransport } from "@modelcontextprotocol/server/stdio";
//#region src/cli.ts
const stderrLogger = {
	debug: (...args) => {
		if (process.env.A2A_DEBUG) console.error("[a2a-mcp]", ...args);
	},
	warn: (...args) => console.error("[a2a-mcp]", ...args),
	error: (...args) => console.error("[a2a-mcp]", ...args)
};
/** Show a config mistake as its field messages, not 40 frames of zod internals. */
const describeFatal = (err) => {
	if (err instanceof ZodError) return err.issues.map((issue) => {
		const path = issue.path.join(".");
		return path ? `${path}: ${issue.message}` : issue.message;
	}).join("\n");
	return err instanceof Error ? err.message : String(err);
};
const main = async () => {
	stderrLogger.warn(`${BUILD_INFO.name}@${BUILD_INFO.version} (git ${BUILD_INFO.gitCommit} ${BUILD_INFO.gitCommitDate}, node ${process.version})`);
	const config = loadConfig();
	const { server, channel } = createServer({
		config,
		logger: stderrLogger
	});
	const transport = new StdioServerTransport();
	await server.connect(transport);
	stderrLogger.warn(`a2a-mcp connected (daemon=${config.daemonUrl}, token=${config.token ? "set" : "NONE"}, writes=${config.allowWrites ? "ENABLED" : "disabled"}, channel=${config.channel ? "declared" : "off"}, store=${config.stateDir})`);
	for (const line of setupInstructions(config)) stderrLogger.warn(`  · ${line}`);
	const shutdown = (signal) => {
		stderrLogger.warn(`received ${signal}, shutting down`);
		channel?.stop();
		process.exit(0);
	};
	process.on("SIGINT", () => shutdown("SIGINT"));
	process.on("SIGTERM", () => shutdown("SIGTERM"));
};
main().catch((err) => {
	console.error(`[a2a-mcp] fatal: ${describeFatal(err)}`);
	process.exit(1);
});
//#endregion
export {};

//# sourceMappingURL=cli.js.map