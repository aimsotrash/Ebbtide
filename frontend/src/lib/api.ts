import { config } from './config';
import { clearTokens, getAccessToken, refreshAccessToken } from './tokens';
import type {
  Chunk,
  ChunkDetail,
  DiscoveryResponse,
  SearchResponse,
  QuizSession,
  QuizAnswer,
  QuizResults,
  IngestResponse,
  FileIngestResponse,
  FadingResponse,
  ChunksResponse,
  StatsResponse,
  ReviewQueueResponse,
  GradeResponse,
  Grade,
} from './types';

import mockChunks from '@/data/mock_chunks.json';
import mockSearchResults from '@/data/mock_search_results.json';
import mockDiscovery from '@/data/mock_discovery.json';
import mockQuiz from '@/data/mock_quiz.json';

async function doFetch(path: string, init: RequestInit | undefined, token: string | null): Promise<Response> {
  return fetch(`${config.apiBaseUrl}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers ?? {}),
    },
  });
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getAccessToken();
  let res = await doFetch(path, init, token);

  if (res.status === 401 && token) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      res = await doFetch(path, init, newToken);
    } else {
      clearTokens();
      // Bounce to login. Use replace so the dead session isn't in history.
      if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
        window.location.replace('/login');
      }
    }
  }

  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

export async function getDiscovery(): Promise<DiscoveryResponse> {
  if (config.useMocks) {
    await sleep(200);
    return mockDiscovery as DiscoveryResponse;
  }
  return apiFetch<DiscoveryResponse>('/api/discovery');
}

export async function search(query: string): Promise<SearchResponse> {
  if (config.useMocks) {
    await sleep(400);
    const results = (mockChunks as Chunk[]).filter((c) =>
      c.content.toLowerCase().includes(query.toLowerCase()) ||
      (c.tags ?? []).some((t: string) => t.toLowerCase().includes(query.toLowerCase()))
    );
    return {
      results: results.map((c) => ({ chunk: c as SearchResponse['results'][0]['chunk'], score: 0.9, highlight: undefined })),
      query,
      total: results.length,
    };
  }
  return apiFetch<SearchResponse>(`/api/search?q=${encodeURIComponent(query)}`);
}

export async function startQuiz(category?: string): Promise<QuizSession> {
  if (config.useMocks) {
    await sleep(500);
    return mockQuiz as QuizSession;
  }
  const qs = category ? `?category=${category}` : '';
  return apiFetch<QuizSession>(`/api/quiz/start${qs}`, { method: 'POST' });
}

export async function submitQuiz(
  sessionId: string,
  answers: QuizAnswer[]
): Promise<QuizResults> {
  if (config.useMocks) {
    await sleep(600);
    const correct = answers.filter(
      (a, i) => a.selected_index === (mockQuiz as QuizSession).questions[i]?.correct_index
    ).length;
    return {
      session_id: sessionId,
      score: correct,
      total: answers.length,
      results: answers.map((a, i) => ({
        question_id: a.question_id,
        correct: a.selected_index === (mockQuiz as QuizSession).questions[i]?.correct_index,
        selected_index: a.selected_index,
        correct_index: (mockQuiz as QuizSession).questions[i]?.correct_index ?? 0,
        stability_delta: a.selected_index === (mockQuiz as QuizSession).questions[i]?.correct_index ? 12 : -4,
      })),
      xp_earned: correct * 50,
      streaks: correct,
    };
  }
  return apiFetch<QuizResults>(`/api/quiz/${sessionId}/submit`, {
    method: 'POST',
    body: JSON.stringify({ answers }),
  });
}

export async function getFading(limit = 200): Promise<FadingResponse> {
  return apiFetch<FadingResponse>(`/api/fading?limit=${limit}`);
}

export async function getAllChunks(limit = 2000): Promise<ChunksResponse> {
  return apiFetch<ChunksResponse>(`/api/chunks?limit=${limit}`);
}

export async function getStats(): Promise<StatsResponse> {
  return apiFetch<StatsResponse>('/api/stats');
}

export async function ingestText(
  content: string,
  sourceType = 'note',
  sourceName = 'manual_entry'
): Promise<IngestResponse> {
  if (config.useMocks) {
    await sleep(800);
    return {
      chunk_id: `mock_${Date.now()}`,
      category: 'general',
      stability_S: 72,
      complexity_k: 1.0,
      message: 'Chunk ingested successfully (mock)',
    };
  }
  return apiFetch<IngestResponse>('/api/ingest/text', {
    method: 'POST',
    body: JSON.stringify({ content, source_type: sourceType, source_name: sourceName }),
  });
}

export async function getSearchResults(query: string): Promise<SearchResponse> {
  if (config.useMocks && query === 'memory retention') {
    await sleep(300);
    return mockSearchResults as SearchResponse;
  }
  return search(query);
}

export async function ingestFile(file: File): Promise<FileIngestResponse> {
  const form = new FormData();
  form.append('files', file);

  const send = async (tok: string | null) => {
    return fetch(`${config.apiBaseUrl}/api/ingest`, {
      method: 'POST',
      body: form,
      headers: tok ? { Authorization: `Bearer ${tok}` } : {},
    });
  };

  const token = getAccessToken();
  let res = await send(token);
  if (res.status === 401 && token) {
    const newToken = await refreshAccessToken();
    if (newToken) res = await send(newToken);
  }
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<FileIngestResponse>;
}

export async function getChunkDetail(chunkId: string): Promise<ChunkDetail> {
  return apiFetch<ChunkDetail>(`/api/chunks/${chunkId}`);
}

export async function updateChunk(chunkId: string, content: string): Promise<void> {
  await apiFetch(`/api/chunks/${chunkId}`, {
    method: 'PUT',
    body: JSON.stringify({ content }),
  });
}

export async function deleteChunk(chunkId: string): Promise<void> {
  await apiFetch(`/api/chunks/${chunkId}`, { method: 'DELETE' });
}

export async function bulkDeleteChunks(chunkIds: string[]): Promise<void> {
  await apiFetch('/api/chunks/bulk-delete', {
    method: 'POST',
    body: JSON.stringify({ chunk_ids: chunkIds }),
  });
}

export async function moveChunkToFolder(chunkId: string, folder: string | null): Promise<void> {
  await apiFetch(`/api/chunks/${chunkId}/folder`, {
    method: 'PATCH',
    body: JSON.stringify({ folder }),
  });
}

export async function getFolders(): Promise<string[]> {
  const r = await apiFetch<{ folders: string[] }>('/api/folders');
  return r.folders;
}

export async function aiSummarize(content: string): Promise<string> {
  const r = await apiFetch<{ summary: string }>('/api/ai/summarize', {
    method: 'POST',
    body: JSON.stringify({ content }),
  });
  return r.summary;
}

export async function aiExpand(content: string): Promise<string> {
  const r = await apiFetch<{ expanded: string }>('/api/ai/expand', {
    method: 'POST',
    body: JSON.stringify({ content }),
  });
  return r.expanded;
}

export async function aiOptimize(original: string, expanded: string): Promise<string> {
  const r = await apiFetch<{ optimized: string }>('/api/ai/optimize', {
    method: 'POST',
    body: JSON.stringify({ original, expanded }),
  });
  return r.optimized;
}

// ── FSRS review loop ───────────────────────────────────────────────────────

export async function getReviewQueue(limit = 20): Promise<ReviewQueueResponse> {
  return apiFetch<ReviewQueueResponse>(`/api/review/queue?limit=${limit}`);
}

export async function gradeChunk(chunkId: string, grade: Grade): Promise<GradeResponse> {
  return apiFetch<GradeResponse>('/api/review/grade', {
    method: 'POST',
    body: JSON.stringify({ chunk_id: chunkId, grade }),
  });
}
