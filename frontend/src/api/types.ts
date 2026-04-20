export type SessionType = 'chat' | 'tip' | 'stuck' | 'brainstorm' | 'wrapup' | 'intake' | 'collab';

export interface Session {
  session_id: string;
  user_id: string;
  title: string;
  type: SessionType;
  program_week: number;
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
  avatar_url: string;
  location: string;
  start_date: string;
  work_summary: string;
  onboarding_complete: boolean;
  intake_completed_at: string | null;
  intake_skipped: boolean;
  intake_objectives_done: number;
  intake_objectives_total: number;
  intake_weeks: Record<string, string>;  // {"1": "ISO datetime", "2": "ISO datetime"}
  program_week: number;  // Computed by backend: clock-based or per-user override
  products: string[];
  daily_tasks: string;
  core_skills: string[];
  learning_goals: string[];
  ai_tools_used: string[];
  ai_superpower: string;
  intake_summary: string;
  created_at: string;
  updated_at: string;
}

// Activity reports (My Team / Activity Log)
export interface ActivityWeek {
  intake_completed: boolean;
  wrapup_completed: boolean;
  session_count: number;
  other_session_count: number;
  message_count: number;
  ideas_count: number;
  tips_shared: number;
  collabs_started: number;
  tip_titles: string[];
  idea_titles: string[];
  collab_titles: string[];
  plan: string;
  accomplished: string;
  insights: string[];
}

export interface ActivityReport {
  user_id: string;
  name: string;
  title: string;
  department: string;
  team: string;
  manager: string;
  avatar_url: string;
  weeks: Record<string, ActivityWeek>;
  generated_at: string;
  last_activity: string;
  has_report: boolean;
  has_profile?: boolean;
  depth?: number;  // 1 = direct report, 2+ = indirect
}

export interface TeamResponse {
  members: ActivityReport[];
  team_size: number;
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

export interface DepartmentObjective {
  id: string;
  label: string;
  description: string;
  extraction_key: string;
  week_introduced?: number;  // Week this objective becomes active (default: 1)
}

export interface DepartmentConfig {
  prompt: string;
  objectives: DepartmentObjective[];
}

export interface CompanyConfig {
  prompt: string;
  objectives: DepartmentObjective[];
}

export type TipCategory = 'tip' | 'gem' | 'skill';

export interface Tip {
  tip_id: string;
  author_id: string;
  department: string;
  title: string;
  content: string;
  summary: string;
  tags: string[];
  category: TipCategory;
  artifact: string;
  vote_count: number;
  comment_count: number;
  user_has_voted: boolean;
  created_at: string;
}

export interface SimilarMatch {
  tip: Tip;
  explanation: string;
  suggested_comment: string;
  confidence: number;
}

export interface TipComment {
  tip_id: string;
  comment_id: string;
  author_id: string;
  content: string;
  created_at: string;
}

export type CollabStatus = 'open' | 'building' | 'done' | 'archived';

export interface Collaboration {
  collab_id: string;
  author_id: string;
  department: string;
  title: string;
  problem: string;
  needed_skills: string[];
  time_commitment: string;
  status: CollabStatus;
  interested_count: number;
  interested_user_ids?: string[];  // Only populated on detail endpoint
  comment_count: number;
  business_value: string;
  tags: string[];
  user_has_interest: boolean;
  created_at: string;
  updated_at: string;
}

export interface CollabComment {
  collab_id: string;
  comment_id: string;
  author_id: string;
  content: string;
  created_at: string;
}

export interface AdminUserSummary {
  user_id: string;
  email: string;
  name: string;
  title: string;
  department: string;
  team: string;
  avatar_url: string;
  intake_completed_at: string | null;
  intake_skipped: boolean;
  intake_objectives_done: number;
  intake_objectives_total: number;
  intake_weeks: Record<string, string>;
  is_department_admin: boolean;
  is_admin: boolean;
  session_count: number;
  tip_count: number;
  last_active: string | null;
  created_at: string;
  updated_at: string;
}

export interface AdminUserIntake {
  profile: UserProfile;
  intake_responses: Record<string, unknown>;
}

export interface UserIdea {
  user_id: string;
  idea_id: string;
  title: string;
  description: string;
  source: string;
  source_session_id: string;
  source_tool_call_id?: string;
  linked_sessions: string[];
  tags: string[];
  status: string;
  created_at: string;
  updated_at: string;
}

/** Server-computed unpublished preview card, returned by GET /api/sessions/{id}. */
export type ActivePreview =
  | {
      type: 'tip';
      tool_call_id: string;
      title: string;
      content: string;
      tags: string[];
      department: string;
    }
  | {
      type: 'collab';
      tool_call_id: string;
      title: string;
      problem: string;
      needed_skills: string[];
      time_commitment: string;
      tags: string[];
      department: string;
    }
  | {
      type: 'idea';
      tool_call_id: string;
      title: string;
      description: string;
      tags: string[];
    };

/** Shape of GET /api/sessions/{id} response — Session fields plus transcript and optional preview. */
export interface SessionLoadResponse extends Session {
  transcript?: Message[];
  active_preview?: ActivePreview | null;
}
