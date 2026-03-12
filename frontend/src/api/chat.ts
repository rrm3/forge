import type { ChatEvent } from './types';

let getTokenFn: (() => Promise<string | null>) | null = null;

// Reuse the same token getter registered in client.ts
// We import and re-export a setter so chat.ts can share the same getter.
export function setChatTokenGetter(fn: () => Promise<string | null>) {
  getTokenFn = fn;
}

const API_BASE = import.meta.env.VITE_API_URL || '';

export function sendMessage(
  sessionId: string | null,
  message: string,
  onEvent: (event: ChatEvent) => void,
): AbortController {
  const controller = new AbortController();

  (async () => {
    const token = await getTokenFn?.();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    let res: Response;
    try {
      res = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ session_id: sessionId, message }),
        signal: controller.signal,
      });
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        onEvent({ type: 'error', error: (err as Error).message });
      }
      return;
    }

    if (!res.ok) {
      const text = await res.text().catch(() => res.statusText);
      onEvent({ type: 'error', error: `API error ${res.status}: ${text}` });
      return;
    }

    const reader = res.body?.getReader();
    if (!reader) {
      onEvent({ type: 'error', error: 'No response body' });
      return;
    }

    const decoder = new TextDecoder();
    let buffer = '';

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // SSE messages are separated by \n\n
        const parts = buffer.split('\n\n');
        // Keep the last (possibly incomplete) part in the buffer
        buffer = parts.pop() ?? '';

        for (const part of parts) {
          if (!part.trim()) continue;

          // Parse SSE block: lines starting with "event:" and "data:"
          const lines = part.split('\n');
          let eventType = '';
          let dataStr = '';

          for (const line of lines) {
            if (line.startsWith('event:')) {
              eventType = line.slice('event:'.length).trim();
            } else if (line.startsWith('data:')) {
              dataStr = line.slice('data:'.length).trim();
            }
          }

          if (!dataStr) continue;

          let parsed: unknown;
          try {
            parsed = JSON.parse(dataStr);
          } catch {
            continue;
          }

          // Build the typed ChatEvent. The event type field comes from the
          // SSE "event:" line; the data payload carries the rest.
          const data = parsed as Record<string, unknown>;
          const type = (eventType || (data['type'] as string)) as ChatEvent['type'];

          try {
            switch (type) {
              case 'text':
                onEvent({ type: 'text', text: data['text'] as string });
                break;
              case 'tool_call':
                onEvent({
                  type: 'tool_call',
                  tool_name: data['tool_name'] as string,
                  tool_call_id: data['tool_call_id'] as string,
                  arguments: (data['arguments'] ?? {}) as Record<string, unknown>,
                });
                break;
              case 'tool_result':
                onEvent({
                  type: 'tool_result',
                  tool_call_id: data['tool_call_id'] as string,
                  result: data['result'] as string,
                });
                break;
              case 'done':
                onEvent({
                  type: 'done',
                  usage: (data['usage'] as ChatEvent & { type: 'done' })['usage'] ?? null,
                });
                break;
              case 'error':
                onEvent({ type: 'error', error: data['error'] as string });
                break;
            }
          } catch {
            // skip malformed event
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        onEvent({ type: 'error', error: (err as Error).message });
      }
    } finally {
      reader.releaseLock();
    }
  })();

  return controller;
}
