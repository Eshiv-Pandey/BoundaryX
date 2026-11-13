#!/usr/bin/env node
interface CliArguments {
    configPath: string;
    port: number | undefined;
    host: string | undefined;
}
export declare function parseArguments(argv: readonly string[]): CliArguments;
export {};
