export type DifficultyMode = 'beginner' | 'proficient' | 'challenge';
export type AnswerKey = string;

export interface FontOption { id: string; name: string; fontUrl?: string; minimumDifficulty: number; sortOrder: number; }
export interface OptionGroup { id: string; name: string; sortOrder: number; options: FontOption[]; }

export interface QuizSettings {
  questionCount: number;
  modes: Record<DifficultyMode, number[]>;
  fontPresets: string[];
}

export interface Question {
  id: string;
  text: string;
  imageUrl: string | null;
  difficulty: number;
  options: Record<AnswerKey, string>;
  optionGroups: OptionGroup[];
  correctOptionId?: string;
  correctOption?: FontOption;
  correctGroup?: OptionGroup;
  configurationError?: string;
  answer?: AnswerKey;
  explanation?: string;
  createdAt?: string;
  updatedAt?: string;
}

export interface QuizAttempt {
  id: string;
  token?: string;
  mode: DifficultyMode;
  expiresAt: string;
  submitted: boolean;
  questions: Question[];
}

export interface WrongAnswer {
  questionText: string;
  difficulty: number;
  imageUrl: string | null;
  options: Partial<Record<AnswerKey, string>>;
  selected: AnswerKey | null;
  correct: AnswerKey;
  explanation: string;
}

export interface SubmissionResult {
  submissionId: string;
  displayName: string;
  mode: DifficultyMode;
  score: number;
  correctCount: number;
  totalCount: number;
  submittedAt: string;
  wrongAnswers: WrongAnswer[];
}

export interface PageResult<T> {
  items: T[];
  page: number;
  pageSize: number;
  total: number;
}

export interface SubmissionSummary {
  id: string;
  displayName: string;
  mode: DifficultyMode;
  score: number;
  correctCount: number;
  totalCount: number;
  submittedAt: string;
}

export interface SubmissionDetail extends SubmissionSummary {
  answers: WrongAnswer[];
}

export interface AdminSession {
  username: string;
  expiresAt: string;
}

export interface DifficultyStat { difficulty: number; count: number; }
export interface FontStat { optionId: string; optionName: string; count: number; }
export interface QuestionStats { total: number; byDifficulty: DifficultyStat[]; byFont: FontStat[]; }

export interface QuestionPayload {
  text: string;
  imageUrl: string | null;
  difficulty: number;
  correctOptionId: string;
  explanation: string;
}

export interface FontReferenceSection {
  id: string;
  name: string;
  sortOrder: number;
  cards: FontReference[];
}

export interface FontReference {
  id: string;
  title: string;
  imageUrl: string;
  note: string;
  difficulty: number;
  sortOrder: number;
  createdAt: string;
}
