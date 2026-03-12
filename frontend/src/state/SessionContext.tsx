import {
  createContext,
  useContext,
  useReducer,
  useCallback,
  useRef,
  type ReactNode,
} from 'react';
import type { Session, Message } from '../api/types';
import {
  listSessions,
  createSession,
  getSession,
  deleteSession,
  renameSession,
} from '../api/client';
import { sendMessage } from '../api/chat';

interface SessionState {
  sessions: Session[];
  activeSessionId: string | null;
  messages: Message[];
  isStreaming: boolean;
  streamingText: string;
}

type SessionAction =
  | { type: 'SET_SESSIONS'; sessions: Session[] }
  | { type: 'SELECT_SESSION'; sessionId: string; messages: Message[] }
  | { type: 'CREATE_SESSION'; session: Session }
  | { type: 'DELETE_SESSION'; sessionId: string }
  | { type: 'RENAME_SESSION'; sessionId: string; title: string }
  | { type: 'ADD_MESSAGE'; message: Message }
  | { type: 'APPEND_STREAMING_TEXT'; text: string }
  | { type: 'SET_STREAMING'; isStreaming: boolean }
  | { type: 'CLEAR_STREAMING_TEXT' };

const initialState: SessionState = {
  sessions: [],
  activeSessionId: null,
  messages: [],
  isStreaming: false,
  streamingText: '',
};

function sessionReducer(state: SessionState, action: SessionAction): SessionState {
  switch (action.type) {
    case 'SET_SESSIONS':
      return { ...state, sessions: action.sessions };

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

    default:
      return state;
  }
}

interface SessionContextType {
  state: SessionState;
  dispatch: React.Dispatch<SessionAction>;
  loadSessions: () => Promise<void>;
  selectSession: (id: string) => Promise<void>;
  newSession: () => Promise<Session>;
  removeSession: (id: string) => Promise<void>;
  updateSessionTitle: (id: string, title: string) => Promise<void>;
  sendChatMessage: (message: string) => void;
  cancelStreaming: () => void;
}

const SessionContext = createContext<SessionContextType | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(sessionReducer, initialState);
  const abortRef = useRef<AbortController | null>(null);

  const loadSessions = useCallback(async () => {
    const sessions = await listSessions();
    dispatch({ type: 'SET_SESSIONS', sessions });
  }, []);

  const selectSession = useCallback(async (id: string) => {
    const data = await getSession(id);
    dispatch({ type: 'SELECT_SESSION', sessionId: id, messages: data.messages });
  }, []);

  const newSession = useCallback(async () => {
    const session = await createSession();
    dispatch({ type: 'CREATE_SESSION', session });
    return session;
  }, []);

  const removeSession = useCallback(async (id: string) => {
    await deleteSession(id);
    dispatch({ type: 'DELETE_SESSION', sessionId: id });
  }, []);

  const updateSessionTitle = useCallback(async (id: string, title: string) => {
    await renameSession(id, title);
    dispatch({ type: 'RENAME_SESSION', sessionId: id, title });
  }, []);

  const sendChatMessage = useCallback(
    (message: string) => {
      // Cancel any in-flight stream
      abortRef.current?.abort();

      const sessionId = state.activeSessionId;

      const userMessage: Message = {
        role: 'user',
        content: message,
        timestamp: new Date().toISOString(),
      };
      dispatch({ type: 'ADD_MESSAGE', message: userMessage });
      dispatch({ type: 'SET_STREAMING', isStreaming: true });
      dispatch({ type: 'CLEAR_STREAMING_TEXT' });

      let accumulatedText = '';

      const controller = sendMessage(sessionId, message, (event) => {
        switch (event.type) {
          case 'text':
            accumulatedText += event.text;
            dispatch({ type: 'APPEND_STREAMING_TEXT', text: event.text });
            break;

          case 'done': {
            // Commit the accumulated assistant message
            if (accumulatedText) {
              const assistantMessage: Message = {
                role: 'assistant',
                content: accumulatedText,
                timestamp: new Date().toISOString(),
              };
              dispatch({ type: 'ADD_MESSAGE', message: assistantMessage });
              dispatch({ type: 'CLEAR_STREAMING_TEXT' });
            }
            dispatch({ type: 'SET_STREAMING', isStreaming: false });

            // Reload sessions to pick up updated title / message count
            listSessions().then((sessions) => {
              dispatch({ type: 'SET_SESSIONS', sessions });
            });
            break;
          }

          case 'error':
            dispatch({ type: 'SET_STREAMING', isStreaming: false });
            dispatch({ type: 'CLEAR_STREAMING_TEXT' });
            break;

          // tool_call and tool_result: no UI state needed at this layer
          default:
            break;
        }
      });

      abortRef.current = controller;
    },
    [state.activeSessionId]
  );

  const cancelStreaming = useCallback(() => {
    abortRef.current?.abort();
    dispatch({ type: 'SET_STREAMING', isStreaming: false });
    dispatch({ type: 'CLEAR_STREAMING_TEXT' });
  }, []);

  return (
    <SessionContext.Provider
      value={{
        state,
        dispatch,
        loadSessions,
        selectSession,
        newSession,
        removeSession,
        updateSessionTitle,
        sendChatMessage,
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
