/**
 * Folding of a SendStreamingMessage stream into one A2A Task snapshot.
 *
 * The stream is a four-armed union discriminated on payload.$case (task,
 * message, statusUpdate, artifactUpdate), and payload
 * itself is optional. Only the task and the two update arms carry lifecycle:
 * a message arm on a task stream is a side channel the snapshot ignores.
 *
 * Artifacts arrive in chunks: append says whether the parts extend an artifact
 * already seen or replace it, and lastChunk only marks the end of one artifact,
 * which needs no state of its own since the accumulated parts are already the
 * whole of it.
 */
import { TaskState, type StreamResponse, type Task, type TaskStatusUpdateEvent } from "@a2a-js/sdk";
/** Builds the seed snapshot of a stream that opened on a status update. */
export declare function taskFromStatusUpdate(event: TaskStatusUpdateEvent): Task;
/** The A2A state of a snapshot, unspecified when the agent sent none. */
export declare function stateOf(task: Task): TaskState;
/**
 * Folds one stream event into a snapshot and returns the new one. An event
 * the snapshot has nothing to do with gives the snapshot back unchanged.
 */
export declare function applyStreamEvent(snapshot: Task, event: StreamResponse): Task;
