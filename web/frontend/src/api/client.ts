import type {
  AdminSession,
  AnswerKey,
  DifficultyMode,
  FontReference,
  PageResult,
  Question,
  QuestionPayload,
  QuizAttempt,
  QuizSettings,
  SubmissionDetail,
  SubmissionResult,
  SubmissionSummary,
  WrongAnswer,
} from '@/types';

const API_BASE = import.meta.env.VITE_API_BASE ?? '/api/v1';

interface ApiErrorBody {
  code?: string;
  detail?: string | { msg?: string }[];
  message?: string;
  error?: { code?: string; message?: string };
}

interface RawQuestion {
  id: number;
  text: string;
  image_url: string | null;
  difficulty: number;
  options: string[];
  answer?: AnswerKey;
  explanation?: string;
  created_at?: string;
  updated_at?: string;
}

interface RawSettings {
  question_count: number;
  modes: Record<DifficultyMode, number[]>;
  font_presets: string[];
}

interface RawAttempt {
  attempt_token?: string;
  mode: DifficultyMode;
  expires_at: string;
  questions: RawQuestion[];
}

interface RawSubmissionDetail {
  question_id: number | null;
  question_text: string;
  image_url?: string | null;
  options?: string[];
  selected: AnswerKey | null;
  correct_answer: AnswerKey;
  explanation: string;
  is_correct: boolean;
}

interface RawSubmissionResult {
  submission_id: number;
  display_name: string;
  mode: DifficultyMode;
  score: number;
  correct_count: number;
  total: number;
  submitted_at: string;
  details: RawSubmissionDetail[];
}

interface RawSubmissionSummary {
  id: number;
  display_name: string;
  mode: DifficultyMode;
  score: number;
  correct_count: number;
  total: number;
  submitted_at: string;
}

interface RawSession {
  token?: string;
  username: string;
  expires_at: string;
}

interface RawFontReference {
  id: number;
  title: string;
  image_url: string;
  note: string;
  created_at: string;
}

interface RawPage<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code?: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}

function messageFromError(body: ApiErrorBody | null, fallback: string): string {
  if (body?.error?.message) return body.error.message;
  if (typeof body?.detail === 'string') return body.detail;
  if (Array.isArray(body?.detail)) return body.detail[0]?.msg ?? fallback;
  return body?.message ?? fallback;
}

function codeFromError(body: ApiErrorBody | null): string | undefined {
  return body?.error?.code ?? body?.code;
}

function queryString(values: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== '') search.set(key, String(value));
  });
  const rendered = search.toString();
  return rendered ? `?${rendered}` : '';
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  const headers = new Headers(init.headers);
  if (!headers.has('Accept')) headers.set('Accept', 'application/json');
  if (init.body && !headers.has('Content-Type')) {
    if (!(init.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  }
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      credentials: 'same-origin',
      headers,
    });
  } catch {
    throw new ApiError('无法连接服务，请检查网络后重试。', 0, 'NETWORK_ERROR');
  }

  const text = await response.text();
  let data: (T & ApiErrorBody) | null = null;
  if (text) {
    try { data = JSON.parse(text) as T & ApiErrorBody; }
    catch { throw new ApiError('服务返回了无法识别的响应。', response.status, 'INVALID_RESPONSE'); }
  }
  if (!response.ok) throw new ApiError(messageFromError(data, '请求未能完成，请稍后重试。'), response.status, codeFromError(data));
  return data as T;
}

function mapOptions(options: string[]): Record<AnswerKey, string> {
  return { A: options[0] ?? '', B: options[1] ?? '', C: options[2] ?? '', D: options[3] ?? '' };
}

function mapQuestion(question: RawQuestion): Question {
  return {
    id: String(question.id), text: question.text, imageUrl: question.image_url,
    difficulty: question.difficulty, options: mapOptions(question.options), answer: question.answer,
    explanation: question.explanation, createdAt: question.created_at, updatedAt: question.updated_at,
  };
}

function mapSettings(settings: RawSettings): QuizSettings {
  return { questionCount: settings.question_count, modes: settings.modes, fontPresets: settings.font_presets };
}

function mapWrongAnswer(detail: RawSubmissionDetail): WrongAnswer {
  return {
    questionText: detail.question_text, imageUrl: detail.image_url ?? null,
    options: detail.options ? mapOptions(detail.options) : {}, selected: detail.selected,
    correct: detail.correct_answer, explanation: detail.explanation,
  };
}

function mapSubmission(result: RawSubmissionResult): SubmissionResult {
  return {
    submissionId: String(result.submission_id), displayName: result.display_name, mode: result.mode,
    score: result.score, correctCount: result.correct_count, totalCount: result.total,
    submittedAt: result.submitted_at,
    wrongAnswers: result.details.filter((detail) => !detail.is_correct).map(mapWrongAnswer),
  };
}

function mapSummary(item: RawSubmissionSummary): SubmissionSummary {
  return { id: String(item.id), displayName: item.display_name, mode: item.mode, score: item.score, correctCount: item.correct_count, totalCount: item.total, submittedAt: item.submitted_at };
}

function mapDetail(result: RawSubmissionResult): SubmissionDetail {
  const base = mapSubmission(result);
  return { ...base, id: base.submissionId, answers: result.details.map(mapWrongAnswer) };
}

function toQuestionWrite(question: QuestionPayload): object {
  return {
    text: question.text, image_url: question.imageUrl, difficulty: question.difficulty,
    options: [question.options.A, question.options.B, question.options.C, question.options.D],
    answer: question.answer, explanation: question.explanation,
  };
}

function sessionFrom(raw: RawSession): AdminSession {
  return { username: raw.username, expiresAt: raw.expires_at };
}

function mapFontReference(item: RawFontReference): FontReference {
  return {
    id: String(item.id),
    title: item.title,
    imageUrl: item.image_url,
    note: item.note,
    createdAt: item.created_at,
  };
}

export const api = {
  getQuizSettings: async (): Promise<QuizSettings> => mapSettings(await request<RawSettings>('/quiz/settings')),

  listFontReferences: async (): Promise<FontReference[]> =>
    (await request<RawFontReference[]>('/font-references')).map(mapFontReference),

  createAttempt: async (mode: DifficultyMode): Promise<QuizAttempt> => {
    const raw = await request<RawAttempt>('/quiz/attempts', { method: 'POST', body: JSON.stringify({ mode }) });
    if (!raw.attempt_token) throw new ApiError('服务未返回可恢复答题凭据。', 500, 'ATTEMPT_TOKEN_MISSING');
    return { id: 'current', token: raw.attempt_token, mode: raw.mode, expiresAt: raw.expires_at, submitted: false, questions: raw.questions.map(mapQuestion) };
  },

  getCurrentAttempt: async (token: string): Promise<QuizAttempt> => {
    const raw = await request<RawAttempt>('/quiz/attempts/current', { headers: { 'X-Quiz-Attempt': token } });
    return { id: 'current', mode: raw.mode, expiresAt: raw.expires_at, submitted: false, questions: raw.questions.map(mapQuestion) };
  },

  submitAttempt: async (token: string, displayName: string, answers: Record<string, AnswerKey>): Promise<SubmissionResult> =>
    mapSubmission(await request<RawSubmissionResult>('/quiz/attempts/submit', {
      method: 'POST', headers: { 'X-Quiz-Attempt': token },
      body: JSON.stringify({ display_name: displayName, answers }),
    })),

  login: async (username: string, password: string): Promise<AdminSession> => {
    const raw = await request<RawSession>('/admin/web/login', { method: 'POST', body: JSON.stringify({ username, password }) });
    return sessionFrom(raw);
  },

  logout: (): Promise<void> => request<void>('/admin/logout', { method: 'POST' }),

  getAdminSession: async (): Promise<AdminSession> => sessionFrom(await request<RawSession>('/admin/session')),

  listQuestions: async (page: number, query?: string, difficulties?: number[]): Promise<PageResult<Question>> => {
    const search = new URLSearchParams(queryString({ page, query }).slice(1));
    difficulties?.forEach((difficulty) => search.append('difficulty', String(difficulty)));
    const raw = await request<RawPage<RawQuestion>>(`/admin/questions?${search.toString()}`);
    return { items: raw.items.map(mapQuestion), page: raw.page, pageSize: raw.page_size, total: raw.total };
  },

  getQuestion: async (id: string): Promise<Question> => mapQuestion(await request<RawQuestion>(`/admin/questions/${encodeURIComponent(id)}`)),

  createQuestion: async (question: QuestionPayload): Promise<Question> =>
    mapQuestion(await request<RawQuestion>('/admin/questions', { method: 'POST', body: JSON.stringify(toQuestionWrite(question)) })),

  updateQuestion: async (id: string, question: QuestionPayload): Promise<Question> =>
    mapQuestion(await request<RawQuestion>(`/admin/questions/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(toQuestionWrite(question)) })),

  uploadImage: async (file: File): Promise<string> => {
    const form = new FormData();
    form.set('image', file);
    const response = await request<{ image_url: string }>('/admin/images', { method: 'POST', body: form });
    return response.image_url;
  },

  deleteQuestion: (id: string): Promise<void> => request<void>(`/admin/questions/${encodeURIComponent(id)}`, { method: 'DELETE' }),

  createFontReference: async (data: Pick<FontReference, 'title' | 'imageUrl' | 'note'>): Promise<FontReference> =>
    mapFontReference(await request<RawFontReference>('/admin/font-references', {
      method: 'POST',
      body: JSON.stringify({ title: data.title, image_url: data.imageUrl, note: data.note }),
    })),

  deleteFontReference: (id: string): Promise<void> =>
    request<void>(`/admin/font-references/${encodeURIComponent(id)}`, { method: 'DELETE' }),

  getAdminSettings: async (): Promise<QuizSettings> => mapSettings(await request<RawSettings>('/admin/settings')),

  saveStrategy: async (settings: Pick<QuizSettings, 'questionCount' | 'modes'>): Promise<QuizSettings> =>
    mapSettings(await request<RawSettings>('/admin/settings/strategy', { method: 'PUT', body: JSON.stringify({ question_count: settings.questionCount, modes: settings.modes }) })),

  saveFontPresets: async (fontPresets: string[]): Promise<QuizSettings> =>
    mapSettings(await request<RawSettings>('/admin/settings/font-presets', { method: 'PUT', body: JSON.stringify({ font_presets: fontPresets }) })),

  listSubmissions: async (page: number, displayName?: string): Promise<PageResult<SubmissionSummary>> => {
    const raw = await request<RawPage<RawSubmissionSummary>>(`/admin/submissions${queryString({ page, display_name: displayName })}`);
    return { items: raw.items.map(mapSummary), page: raw.page, pageSize: raw.page_size, total: raw.total };
  },

  getSubmission: async (id: string): Promise<SubmissionDetail> => mapDetail(await request<RawSubmissionResult>(`/admin/submissions/${encodeURIComponent(id)}`)),
};
