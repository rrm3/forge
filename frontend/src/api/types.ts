export type SessionType = 'chat' | 'tip' | 'stuck' | 'brainstorm' | 'wrapup' | 'intake';

export interface Session {
  session_id: string;
  user_id: string;
  title: string;
  type: SessionType;
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
  location: string;
  start_date: string;
  work_summary: string;
  onboarding_complete: boolean;
  intake_completed_at: string | null;
  products: string[];
  daily_tasks: string;
  core_skills: string[];
  learning_goals: string[];
  ai_tools_used: string[];
  ai_superpower: string;
  ai_proficiency: {
    operational_fluency: number;
    strategic_delegation: number;
    discernment: number;
    security_awareness: number;
    automation_readiness: number;
  } | null;
  intake_summary: string;
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
