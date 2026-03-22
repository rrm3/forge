import {
  createContext,
  useContext,
  useReducer,
  useCallback,
  useRef,
  useEffect,
  type ReactNode,
} from 'react';
import type { Session, SessionType, Message } from '../api/types';
import type { ServerMessage, ConnectionStatus } from '../api/websocket';
import {
  listSessions,
  getSession,
  deleteSession,
  renameSession,
} from '../api/client';
import { forgeWs } from '../api/websocket';

export interface IntakeChecklistItem {
  field: string;
  label: string;
  done: boolean;
  value?: string;
}

interface SessionState {
  sessions: Session[];
  sessionsLoaded: boolean;
  activeSessionId: string | null;
  messages: Message[];
  isStreaming: boolean;
  streamingText: string;
  connectionStatus: ConnectionStatus;
  intakeChecklist: IntakeChecklistItem[];
  intakeComplete: boolean;
  intakeSuggestions: string[];
  tipReady: { title: string; content: string; tags: string[]; department: string } | null;
  tipPublished: boolean;
  ideaReady: { title: string; description: string; tags: string[] } | null;
}

type SessionAction =
  | { type: 'SET_SESSIONS'; sessions: Session[] }
  | { type: 'SET_SESSION_ID'; sessionId: string }
  | { type: 'SELECT_SESSION'; sessionId: string; messages: Message[] }
  | { type: 'CREATE_SESSION'; session: Session }
  | { type: 'DELETE_SESSION'; sessionId: string }
  | { type: 'RENAME_SESSION'; sessionId: string; title: string }
  | { type: 'ADD_MESSAGE'; message: Message }
  | { type: 'APPEND_STREAMING_TEXT'; text: string }
  | { type: 'SET_STREAMING'; isStreaming: boolean }
  | { type: 'CLEAR_STREAMING_TEXT' }
  | { type: 'SET_CONNECTION_STATUS'; status: ConnectionStatus }
  | { type: 'SET_INTAKE_CHECKLIST'; checklist: IntakeChecklistItem[] }
  | { type: 'SET_INTAKE_COMPLETE'; suggestions: string[] }
  | { type: 'SET_TIP_READY'; tip: { title: string; content: string; tags: string[]; department: string } }
  | { type: 'SET_TIP_PUBLISHED' }
  | { type: 'SET_IDEA_READY'; idea: { title: string; description: string; tags: string[] } | null }
  | { type: 'DESELECT_SESSION' };

const initialState: SessionState = {
  sessions: [],
  sessionsLoaded: false,
  activeSessionId: null,
  messages: [],
  isStreaming: false,
  streamingText: '',
  connectionStatus: 'disconnected',
  intakeChecklist: [],
  intakeComplete: false,
  intakeSuggestions: [],
  tipReady: null,
  tipPublished: false,
  ideaReady: null,
};

function sessionReducer(state: SessionState, action: SessionAction): SessionState {
  switch (action.type) {
    case 'SET_SESSIONS':
      return { ...state, sessions: action.sessions, sessionsLoaded: true };

    case 'SET_SESSION_ID':
      return { ...state, activeSessionId: action.sessionId };

    case 'SELECT_SESSION':
      return {
        ...state,
        activeSessionId: action.sessionId,
        messages: action.messages,
        streamingText: '',
        isStreaming: false,
      };

    case 'CREATE_SESSION':
      return {
        ...state,
        sessions: [action.session, ...state.sessions],
        activeSessionId: action.session.session_id,
        messages: [],
        streamingText: '',
        isStreaming: false,
      };

    case 'DELETE_SESSION': {
      const sessions = state.sessions.filter((s) => s.session_id !== action.sessionId);
      const activeSessionId =
        state.activeSessionId === action.sessionId ? null : state.activeSessionId;
      const messages = activeSessionId === null ? [] : state.messages;
      return { ...state, sessions, activeSessionId, messages };
    }

    case 'RENAME_SESSION':
      return {
        ...state,
        sessions: state.sessions.map((s) =>
          s.session_id === action.sessionId ? { ...s, title: action.title } : s
        ),
      };

    case 'ADD_MESSAGE':
      return { ...state, messages: [...state.messages, action.message] };

    case 'APPEND_STREAMING_TEXT':
      return { ...state, streamingText: state.streamingText + action.text };

    case 'SET_STREAMING':
      return { ...state, isStreaming: action.isStreaming };

    case 'CLEAR_STREAMING_TEXT':
      return { ...state, streamingText: '' };

    case 'SET_CONNECTION_STATUS':
      return { ...state, connectionStatus: action.status };

    case 'SET_INTAKE_CHECKLIST':
      return { ...state, intakeChecklist: action.checklist };

    case 'SET_INTAKE_COMPLETE':
      return { ...state, intakeComplete: true, intakeSuggestions: action.suggestions };

    case 'SET_TIP_READY':
      return { ...state, tipReady: action.tip, tipPublished: false };

    case 'SET_TIP_PUBLISHED':
      return { ...state, tipPublished: true };

    case 'SET_IDEA_READY':
      return { ...state, ideaReady: action.idea };

    case 'DESELECT_SESSION':
      return { ...state, activeSessionId: null, messages: [], streamingText: '', isStreaming: false, tipReady: null, tipPublished: false, ideaReady: null };

    default:
      return state;
  }
}

interface SessionContextType {
  state: SessionState;
  dispatch: React.Dispatch<SessionAction>;
  loadSessions: () => Promise<void>;
  selectSession: (id: string) => Promise<void>;
  deselectSession: () => void;
  removeSession: (id: string) => Promise<void>;
  updateSessionTitle: (id: string, title: string) => Promise<void>;
  sendChatMessage: (message: string) => void;
  startTypedSession: (type: SessionType) => void;
  cancelStreaming: () => void;
}

const SessionContext = createContext<SessionContextType | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(sessionReducer, initialState);
  const activeSessionIdRef = useRef<string | null>(null);
  const accumulatedTextRef = useRef('');

  // Keep the ref in sync
  activeSessionIdRef.current = state.activeSessionId;

  // Set up WebSocket message handler
  useEffect(() => {
    const unsubMessage = forgeWs.onMessage((msg: ServerMessage) => {
      switch (msg.type) {
        case 'connected': {
          // Connection (re-)established. Sync session state in case we
          // missed messages during a disconnect.
          const activeId = activeSessionIdRef.current;
          if (activeId) {
            getSession(activeId)
              .then((data) => {
                if (data.transcript && data.transcript.length > 0) {
                  dispatch({
                    type: 'SELECT_SESSION',
                    sessionId: activeId,
                    messages: data.transcript,
                  });
                }
              })
              .catch(() => {});
          }
          // Clear any stale streaming state from before disconnect
          if (accumulatedTextRef.current) {
            const recovered: Message = {
              role: 'assistant',
              content: accumulatedTextRef.current,
              timestamp: new Date().toISOString(),
            };
            dispatch({ type: 'ADD_MESSAGE', message: recovered });
            dispatch({ type: 'CLEAR_STREAMING_TEXT' });
            accumulatedTextRef.current = '';
          }
          dispatch({ type: 'SET_STREAMING', isStreaming: false });
          break;
        }

        case 'session': {
          // New session created via start_session
          activeSessionIdRef.current = msg.session_id;
          dispatch({ type: 'SET_SESSION_ID', sessionId: msg.session_id });
          // Add to session list
          const newSession: Session = {
            session_id: msg.session_id,
            user_id: '',
            title: '',
            type: msg.session_type as Session['type'],
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            message_count: 0,
            summary: null,
          };
          dispatch({ type: 'CREATE_SESSION', session: newSession });
          dispatch({ type: 'SET_STREAMING', isStreaming: true });
          dispatch({ type: 'CLEAR_STREAMING_TEXT' });
          accumulatedTextRef.current = '';
          break;
        }

        case 'session_update':
          dispatch({ type: 'RENAME_SESSION', sessionId: msg.session_id, title: msg.title });
          break;

        case 'token':
          if (msg.session_id === activeSessionIdRef.current) {
            accumulatedTextRef.current += msg.content;
            dispatch({ type: 'APPEND_STREAMING_TEXT', text: msg.content });
          }
          break;

        case 'tool_call':
          if (msg.session_id === activeSessionIdRef.current) {
            const toolCallMsg: Message = {
              role: 'tool_call',
              content: JSON.stringify(msg.args),
              tool_name: msg.tool,
              tool_call_id: msg.tool_call_id,
              timestamp: new Date().toISOString(),
            };
            dispatch({ type: 'ADD_MESSAGE', message: toolCallMsg });
          }
          break;

        case 'tool_result':
          if (msg.session_id === activeSessionIdRef.current) {
            const toolResultMsg: Message = {
              role: 'tool_result',
              content: typeof msg.result === 'string' ? msg.result : JSON.stringify(msg.result),
              tool_call_id: msg.tool_call_id,
              timestamp: new Date().toISOString(),
            };
            dispatch({ type: 'ADD_MESSAGE', message: toolResultMsg });
          }
          break;

        case 'done': {
          if (msg.session_id === activeSessionIdRef.current) {
            if (accumulatedTextRef.current) {
              const assistantMessage: Message = {
                role: 'assistant',
                content: accumulatedTextRef.current,
                timestamp: new Date().toISOString(),
              };
              dispatch({ type: 'ADD_MESSAGE', message: assistantMessage });
              dispatch({ type: 'CLEAR_STREAMING_TEXT' });
              accumulatedTextRef.current = '';
            }
            dispatch({ type: 'SET_STREAMING', isStreaming: false });

            // Reload sessions to pick up updated title / message count
            listSessions().then((sessions) => {
              dispatch({ type: 'SET_SESSIONS', sessions });
            });
          }
          break;
        }

        case 'intake_progress':
          if ('checklist' in msg) {
            dispatch({
              type: 'SET_INTAKE_CHECKLIST',
              checklist: (msg as { checklist: IntakeChecklistItem[] }).checklist,
            });
          }
          break;

        case 'intake_complete':
          dispatch({
            type: 'SET_INTAKE_COMPLETE',
            suggestions: (msg as { suggestions: string[] }).suggestions || [],
          });
          break;

        case 'tip_ready':
          dispatch({
            type: 'SET_TIP_READY',
            tip: {
              title: (msg as any).title || '',
              content: (msg as any).content || '',
              tags: (msg as any).tags || [],
              department: (msg as any).department || 'Everyone',
            },
          });
          break;

        case 'idea_ready':
          dispatch({
            type: 'SET_IDEA_READY',
            idea: {
              title: (msg as any).title || '',
              description: (msg as any).description || '',
              tags: (msg as any).tags || [],
            },
          });
          break;

        case 'error':
          if (!msg.session_id || msg.session_id === activeSessionIdRef.current) {
            dispatch({ type: 'SET_STREAMING', isStreaming: false });
            dispatch({ type: 'CLEAR_STREAMING_TEXT' });
            accumulatedTextRef.current = '';
          }
          break;

        default:
          break;
      }
    });

    const unsubStatus = forgeWs.onStatus((status: ConnectionStatus) => {
      dispatch({ type: 'SET_CONNECTION_STATUS', status });
    });

    return () => {
      unsubMessage();
      unsubStatus();
    };
  }, []);

  const loadSessions = useCallback(async () => {
    const sessions = await listSessions();
    dispatch({ type: 'SET_SESSIONS', sessions });
  }, []);

  const selectSession = useCallback(async (id: string) => {
    const data = await getSession(id);
    dispatch({ type: 'SELECT_SESSION', sessionId: id, messages: data.transcript || [] });
  }, []);

  const deselectSession = useCallback(() => {
    dispatch({ type: 'DESELECT_SESSION' });
  }, []);

  const removeSession = useCallback(async (id: string) => {
    await deleteSession(id);
    if (activeSessionIdRef.current === id) {
      activeSessionIdRef.current = null;
    }
    dispatch({ type: 'DELETE_SESSION', sessionId: id });
  }, []);

  const updateSessionTitle = useCallback(async (id: string, title: string) => {
    await renameSession(id, title);
    dispatch({ type: 'RENAME_SESSION', sessionId: id, title });
  }, []);

  const sendChatMessage = useCallback(
    (message: string) => {
      const sessionId = activeSessionIdRef.current;

      // Show user message in UI if there's content
      if (message) {
        const userMessage: Message = {
          role: 'user',
          content: message,
          timestamp: new Date().toISOString(),
        };
        dispatch({ type: 'ADD_MESSAGE', message: userMessage });
      }
      dispatch({ type: 'SET_STREAMING', isStreaming: true });
      dispatch({ type: 'CLEAR_STREAMING_TEXT' });
      accumulatedTextRef.current = '';

      if (sessionId) {
        // Send to existing session
        forgeWs.chat(sessionId, message);
      } else {
        // Create a new session of type 'chat'
        forgeWs.startSession('chat');
      }
    },
    []
  );

  const startTypedSession = useCallback(
    (type: SessionType) => {
      dispatch({ type: 'SET_STREAMING', isStreaming: true });
      dispatch({ type: 'CLEAR_STREAMING_TEXT' });
      accumulatedTextRef.current = '';
      forgeWs.startSession(type);
    },
    []
  );

  const cancelStreaming = useCallback(() => {
    const sessionId = activeSessionIdRef.current;
    if (sessionId) {
      forgeWs.cancel(sessionId);
    }
    dispatch({ type: 'SET_STREAMING', isStreaming: false });
    dispatch({ type: 'CLEAR_STREAMING_TEXT' });
    accumulatedTextRef.current = '';
  }, []);

  return (
    <SessionContext.Provider
      value={{
        state,
        dispatch,
        loadSessions,
        selectSession,
        deselectSession,
        removeSession,
        updateSessionTitle,
        sendChatMessage,
        startTypedSession,
        cancelStreaming,
      }}
    >
      {children}
    </SessionContext.Provider>
  );
}

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) {
    throw new Error('useSession must be used within a SessionProvider');
  }
  return ctx;
}
