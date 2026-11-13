import type { Artifact, Message, Part } from "@a2a-js/sdk";
import type { ContentBlock } from "@modelcontextprotocol/server";
/** The _meta key under which the bridge parks everything MCP cannot hold. */
export declare const A2A_META_KEY = "io.github.amirk-s/a2a";
/** Raised when a part or a content block cannot be mapped. */
export declare class InvalidPartError extends Error {
    constructor(message: string);
}
/** The A2A oneof cases, as ts-proto names them. */
export type A2APartKind = "text" | "raw" | "url" | "data";
/** What the bridge parks under A2A_META_KEY on every block it emits. */
export interface A2APartMeta {
    partKind: A2APartKind;
    filename?: string;
    mediaType?: string;
    metadata?: Record<string, unknown>;
    artifactId?: string;
    artifactName?: string;
    artifactDescription?: string;
    messageId?: string;
    contextId?: string;
    taskId?: string;
}
/** Identity of the artifact or message a part was carried in. */
export type A2APartOrigin = Omit<A2APartMeta, "partKind" | "filename" | "mediaType" | "metadata">;
/** Maps one A2A part onto the MCP content block that carries it best. */
export declare function partToContent(part: Part, origin?: A2APartOrigin): ContentBlock;
/** Maps an MCP content block back onto an A2A part. */
export declare function contentToPart(block: ContentBlock): Part;
/** Maps every part of an artifact, keeping order and artifact identity. */
export declare function artifactToContent(artifact: Artifact): ContentBlock[];
/** Maps every part of a message, keeping order and message identity. */
export declare function messageToContent(message: Message): ContentBlock[];
/**
 * The structuredContent of a tool result, taken from the parts.
 *
 * Exactly one data part gives structured content; zero gives none, and several
 * give none either, so that nothing is silently dropped.
 */
export declare function structuredContentFromParts(parts: readonly Part[]): Record<string, unknown> | undefined;
