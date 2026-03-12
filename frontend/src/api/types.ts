export interface Session {
  session_id: string;
  user_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  summary: string | null;
}

export interface Message {
  role: 'user' | 'assistant' | 'system' | 'tool_call' | 'tool_result';
  content: string;
  timestamp: string;
  tool_name?: string;
  tool_call_id?: string;
}

export interface UserProfile {
  user_id: string;
  email: string;
  name: string;
  title: string;
  department: string;
  manager: string;
  direct_reports: string[];
  team: string;
  ai_experience_level: string;
  interests: string[];
  tools_used: string[];
  goals: string[];
  onboarding_complete: boolean;
  created_at: string;
  updated_at: string;
}

export interface JournalEntry {
  entry_id: string;
  user_id: string;
  content: string;
  tags: string[];
  created_at: string;
}

export interface Idea {
  idea_id: string;
  title: string;
  description: string;
  required_skills: string[];
  proposed_by: string;
  proposed_by_name: string;
  status: string;
  interested_users: string[];
  created_at: string;
}

// SSE event types from backend
export type ChatEvent =
  | { type: 'text'; text: string }
  | { type: 'tool_call'; tool_name: string; tool_call_id: string; arguments: Record<string, unknown> }
  | { type: 'tool_result'; tool_call_id: string; result: string }
  | { type: 'done'; usage: { prompt_tokens: number; completion_tokens: number; total_tokens: number } | null }
  | { type: 'error'; error: string };
